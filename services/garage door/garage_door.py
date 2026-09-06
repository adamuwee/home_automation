#!/usr/bin/env python3
"""Monitor a Modbus garage-door sensor and send OTel log alerts."""

import json
import logging
import os
import signal
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, time as datetime_time, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from opentelemetry._logs import LogRecord, SeverityNumber, set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from pymodbus.client import ModbusTcpClient


LOGGER = logging.getLogger("garage_door")


def env_int(name: str, default: int) -> int:
	try:
		return int(os.getenv(name, str(default)))
	except ValueError as error:
		raise ValueError(f"{name} must be an integer") from error


def env_float(name: str, default: float) -> float:
	try:
		return float(os.getenv(name, str(default)))
	except ValueError as error:
		raise ValueError(f"{name} must be a number") from error


@dataclass(frozen=True)
class Settings:
	modbus_host: str
	modbus_port: int
	modbus_unit_id: int
	modbus_input_register_address: int
	garage_door_channel: int
	poll_interval_seconds: int
	timezone_name: str
	door_open_cutoff: datetime_time
	mqtt_host: str
	mqtt_port: int
	mqtt_topic: str
	wind_threshold_mph: float
	wind_stale_seconds: int
	otlp_endpoint: str
	otlp_insecure: bool
	alert_repeat_seconds: int
	health_host: str
	health_port: int

	@classmethod
	def from_environment(cls) -> "Settings":
		env_file = os.getenv("GARAGE_DOOR_ENV_FILE", str(Path(__file__).with_name(".env")))
		load_dotenv(env_file)
		host = os.getenv("MODBUS_HOST")
		if not host:
			raise ValueError("MODBUS_HOST is required")
		cutoff_value = os.getenv("DOOR_OPEN_CUTOFF", "21:05")
		try:
			cutoff = datetime_time.fromisoformat(cutoff_value)
			ZoneInfo(os.getenv("TIMEZONE", "America/New_York"))
		except ValueError as error:
			raise ValueError("DOOR_OPEN_CUTOFF must use HH:MM and TIMEZONE must be valid") from error

		channel = env_int("GARAGE_DOOR_CHANNEL", 6)
		if not 1 <= channel <= 16:
			raise ValueError("GARAGE_DOOR_CHANNEL must be between 1 and 16")

		return cls(
			modbus_host=host,
			modbus_port=env_int("MODBUS_PORT", 502),
			modbus_unit_id=env_int("MODBUS_UNIT_ID", 1),
			modbus_input_register_address=env_int("MODBUS_INPUT_REGISTER_ADDRESS", 21504),
			garage_door_channel=channel,
			poll_interval_seconds=env_int("POLL_INTERVAL_SECONDS", 30),
			timezone_name=os.getenv("TIMEZONE", "America/New_York"),
			door_open_cutoff=cutoff,
			mqtt_host=os.getenv("MQTT_HOST", "debian-openhab"),
			mqtt_port=env_int("MQTT_PORT", 1883),
			mqtt_topic=os.getenv("WIND_MQTT_TOPIC", "acurite_ws/wind_avg"),
			wind_threshold_mph=env_float("WIND_THRESHOLD_MPH", 7),
			wind_stale_seconds=env_int("WIND_STALE_SECONDS", 300),
			otlp_endpoint=os.getenv("OTLP_GRPC_ENDPOINT", "meerkat.home.arpa:4317"),
			otlp_insecure=os.getenv("OTLP_INSECURE", "true").lower() == "true",
			alert_repeat_seconds=env_int("ALERT_REPEAT_SECONDS", 300),
			health_host=os.getenv("HEALTH_HOST", "127.0.0.1"),
			health_port=env_int("HEALTH_PORT", 8088),
		)


def door_is_open(register_value: int, channel: int) -> bool:
	"""Return true when the one-based digital-input channel is OFF."""
	return not bool(register_value & (1 << (channel - 1)))


def parse_wind_speed(payload: bytes) -> float:
	value = float(payload.decode("utf-8").strip())
	if value < 0:
		raise ValueError("wind speed must not be negative")
	return value


@dataclass
class AlertLimiter:
	last_sent: dict[str, datetime] = field(default_factory=dict)

	def should_send(self, condition: str, active: bool, now: datetime, repeat_seconds: int) -> bool:
		if not active:
			self.last_sent.pop(condition, None)
			return False
		last_sent = self.last_sent.get(condition)
		if last_sent is None or (now - last_sent).total_seconds() >= repeat_seconds:
			self.last_sent[condition] = now
			return True
		return False


@dataclass
class ServiceState:
	started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
	last_modbus_success: Optional[datetime] = None
	last_modbus_error: Optional[str] = None
	last_register_value: Optional[int] = None
	door_open: Optional[bool] = None
	mqtt_connected: bool = False
	last_wind_at: Optional[datetime] = None
	wind_speed_mph: Optional[float] = None
	last_mqtt_error: Optional[str] = None
	fatal_error: Optional[str] = None


class Telemetry:
	def __init__(self, settings: Settings) -> None:
		provider = LoggerProvider(resource=Resource.create({"service.name": "garage-door-monitor"}))
		provider.add_log_record_processor(
			BatchLogRecordProcessor(OTLPLogExporter(endpoint=settings.otlp_endpoint, insecure=settings.otlp_insecure))
		)
		set_logger_provider(provider)
		self._provider = provider
		self._logger = provider.get_logger("garage-door-monitor")

	def emit_alert(self, condition: str, attributes: dict[str, object]) -> None:
		self._logger.emit(
			LogRecord(
				severity_number=SeverityNumber.WARN,
				severity_text="WARN",
				body=f"Garage door alert: {condition}",
				attributes={"event.name": "garage_door_alert", "alert.condition": condition, **attributes},
			)
		)

	def shutdown(self) -> None:
		self._provider.shutdown()


class GarageDoorService:
	def __init__(self, settings: Settings, telemetry: Telemetry) -> None:
		self.settings = settings
		self.telemetry = telemetry
		self.state = ServiceState()
		self._state_lock = threading.Lock()
		self._stop_event = threading.Event()
		self._alert_limiter = AlertLimiter()
		self._modbus_client = ModbusTcpClient(settings.modbus_host, port=settings.modbus_port, timeout=5)
		self._mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="garage-door-monitor")
		self._mqtt_client.on_connect = self._on_mqtt_connect
		self._mqtt_client.on_disconnect = self._on_mqtt_disconnect
		self._mqtt_client.on_message = self._on_mqtt_message
		self._health_server: Optional[ThreadingHTTPServer] = None

	def _on_mqtt_connect(self, client, userdata, flags, reason_code, properties) -> None:
		if reason_code.is_failure:
			with self._state_lock:
				self.state.last_mqtt_error = f"MQTT connection refused: {reason_code}"
			return
		client.subscribe(self.settings.mqtt_topic)
		with self._state_lock:
			self.state.mqtt_connected = True
			self.state.last_mqtt_error = None
		LOGGER.info("Subscribed to MQTT topic %s", self.settings.mqtt_topic)

	def _on_mqtt_disconnect(self, client, userdata, disconnect_flags, reason_code, properties) -> None:
		with self._state_lock:
			self.state.mqtt_connected = False
			self.state.last_mqtt_error = f"MQTT disconnected: {reason_code}"

	def _on_mqtt_message(self, client, userdata, message) -> None:
		try:
			wind_speed = parse_wind_speed(message.payload)
		except (UnicodeDecodeError, ValueError) as error:
			LOGGER.warning("Ignored invalid wind speed payload: %s", error)
			return
		with self._state_lock:
			self.state.wind_speed_mph = wind_speed
			self.state.last_wind_at = datetime.now(timezone.utc)
			self.state.last_mqtt_error = None

	def poll_modbus(self) -> bool:
		try:
			if not self._modbus_client.connected and not self._modbus_client.connect():
				raise ConnectionError("could not connect to Modbus/TCP device")
			response = self._modbus_client.read_input_registers(
				address=self.settings.modbus_input_register_address,
				count=1,
				device_id=self.settings.modbus_unit_id,
			)
			if response.isError() or not response.registers:
				raise RuntimeError(f"Modbus input register read failed: {response}")
			register_value = response.registers[0]
			now = datetime.now(timezone.utc)
			with self._state_lock:
				self.state.last_register_value = register_value
				self.state.door_open = door_is_open(register_value, self.settings.garage_door_channel)
				self.state.last_modbus_success = now
				self.state.last_modbus_error = None
			return True
		except Exception as error:
			LOGGER.warning("Modbus poll failed: %s", error)
			with self._state_lock:
				self.state.last_modbus_error = str(error)
			self._modbus_client.close()
			return False

	def _evaluate_alerts(self) -> None:
		now = datetime.now(timezone.utc)
		with self._state_lock:
			door_open = self.state.door_open
			wind_speed = self.state.wind_speed_mph
			wind_at = self.state.last_wind_at
		local_time = now.astimezone(ZoneInfo(self.settings.timezone_name)).time()
		after_cutoff = door_open is True and local_time >= self.settings.door_open_cutoff
		wind_is_fresh = wind_at is not None and (now - wind_at).total_seconds() <= self.settings.wind_stale_seconds
		high_wind = door_open is True and wind_is_fresh and wind_speed is not None and wind_speed > self.settings.wind_threshold_mph

		for condition, active in (("door_open_after_cutoff", after_cutoff), ("door_open_high_wind", high_wind)):
			if self._alert_limiter.should_send(condition, active, now, self.settings.alert_repeat_seconds):
				self.telemetry.emit_alert(
					condition,
					{
						"garage.door.open": door_open,
						"garage.wind_speed_mph": wind_speed,
						"garage.wind_threshold_mph": self.settings.wind_threshold_mph,
						"garage.cutoff": self.settings.door_open_cutoff.isoformat(timespec="minutes"),
						"garage.modbus_host": self.settings.modbus_host,
					},
				)
				LOGGER.warning("Alert emitted: %s", condition)

	def health_payload(self) -> tuple[HTTPStatus, dict[str, object]]:
		now = datetime.now(timezone.utc)
		with self._state_lock:
			state = ServiceState(**asdict(self.state))
		modbus_fresh = state.last_modbus_success is not None and (now - state.last_modbus_success).total_seconds() <= self.settings.poll_interval_seconds * 2
		wind_fresh = state.last_wind_at is not None and (now - state.last_wind_at).total_seconds() <= self.settings.wind_stale_seconds
		status = "error" if state.fatal_error else "running" if modbus_fresh and state.mqtt_connected and wind_fresh else "degraded"
		http_status = HTTPStatus.OK if status == "running" else HTTPStatus.SERVICE_UNAVAILABLE
		return http_status, {
			"status": status,
			"door_open": state.door_open,
			"wind_speed_mph": state.wind_speed_mph,
			"mqtt_connected": state.mqtt_connected,
			"last_modbus_success": state.last_modbus_success.isoformat() if state.last_modbus_success else None,
			"last_modbus_reg_value": state.last_register_value,
			"last_wind_at": state.last_wind_at.isoformat() if state.last_wind_at else None,
			"modbus_fresh": modbus_fresh,
			"wind_fresh": wind_fresh,
		}

	def start_health_server(self) -> None:
		service = self

		class HealthHandler(BaseHTTPRequestHandler):
			def do_GET(self) -> None:
				if self.path != "/health":
					self.send_error(HTTPStatus.NOT_FOUND)
					return
				status, payload = service.health_payload()
				body = json.dumps(payload).encode("utf-8")
				self.send_response(status)
				self.send_header("Content-Type", "application/json")
				self.send_header("Content-Length", str(len(body)))
				self.end_headers()
				self.wfile.write(body)

			def log_message(self, format, *args) -> None:
				LOGGER.debug("Health endpoint: " + format, *args)

		self._health_server = ThreadingHTTPServer((self.settings.health_host, self.settings.health_port), HealthHandler)
		threading.Thread(target=self._health_server.serve_forever, name="health-server", daemon=True).start()
		LOGGER.info("Health endpoint listening on http://%s:%s/health", self.settings.health_host, self.settings.health_port)

	def stop(self) -> None:
		self._stop_event.set()

	def run(self) -> None:
		self.start_health_server()
		try:
			self._mqtt_client.connect_async(self.settings.mqtt_host, self.settings.mqtt_port, keepalive=60)
			self._mqtt_client.loop_start()
			while not self._stop_event.is_set():
				self.poll_modbus()
				self._evaluate_alerts()
				self._stop_event.wait(self.settings.poll_interval_seconds)
		except Exception as error:
			LOGGER.exception("Garage door service stopped unexpectedly")
			with self._state_lock:
				self.state.fatal_error = str(error)
			raise
		finally:
			self._mqtt_client.loop_stop()
			self._mqtt_client.disconnect()
			self._modbus_client.close()
			if self._health_server:
				self._health_server.shutdown()
				self._health_server.server_close()
			self.telemetry.shutdown()


def main() -> None:
	logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
	settings = Settings.from_environment()
	service = GarageDoorService(settings, Telemetry(settings))

	def request_shutdown(signum, frame) -> None:
		LOGGER.info("Received signal %s; shutting down", signum)
		service.stop()

	signal.signal(signal.SIGINT, request_shutdown)
	signal.signal(signal.SIGTERM, request_shutdown)
	service.run()


if __name__ == "__main__":
	main()
