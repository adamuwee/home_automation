import sys
import unittest
from datetime import datetime, time, timedelta, timezone
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from garage_door import AlertLimiter, GarageDoorService, ServiceState, Settings, door_is_open, parse_wind_speed


def settings() -> Settings:
    return Settings(
        modbus_host="moxa4510.home.arpa",
        modbus_port=502,
        modbus_unit_id=1,
        modbus_input_register_address=21504,
        garage_door_channel=6,
        poll_interval_seconds=30,
        timezone_name="America/New_York",
        door_open_cutoff=time(21, 5),
        mqtt_host="debian-openhab",
        mqtt_port=1883,
        mqtt_topic="Environment_Monitoring_Outside_Wind_Speed",
        wind_threshold_mph=7,
        wind_stale_seconds=300,
        otlp_endpoint="meerkat.home.arpa:4317",
        otlp_insecure=True,
        alert_repeat_seconds=300,
        health_host="127.0.0.1",
        health_port=8088,
    )


class FakeTelemetry:
    def __init__(self) -> None:
        self.alerts = []

    def emit_alert(self, condition, attributes) -> None:
        self.alerts.append((condition, attributes))

    def shutdown(self) -> None:
        pass


class GarageDoorLogicTests(unittest.TestCase):
    def test_settings_loads_default_env_file_beside_module(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            configuration = Settings.from_environment()

        self.assertEqual(configuration.modbus_host, "moxa4510.home.arpa")

    def test_channel_six_off_means_door_open(self) -> None:
        self.assertTrue(door_is_open(0b0000000000000000, 6))
        self.assertFalse(door_is_open(0b0000000000100000, 6))

    def test_plain_numeric_wind_payload(self) -> None:
        self.assertEqual(parse_wind_speed(b" 8 "), 8.0)
        with self.assertRaises(ValueError):
            parse_wind_speed(b"-1")

    def test_alert_limiter_sends_on_entry_and_reminder(self) -> None:
        limiter = AlertLimiter()
        now = datetime(2026, 9, 5, tzinfo=timezone.utc)
        self.assertTrue(limiter.should_send("high_wind", True, now, 300))
        self.assertFalse(limiter.should_send("high_wind", True, now + timedelta(seconds=299), 300))
        self.assertTrue(limiter.should_send("high_wind", True, now + timedelta(seconds=300), 300))
        self.assertFalse(limiter.should_send("high_wind", False, now, 300))
        self.assertTrue(limiter.should_send("high_wind", True, now, 300))

    def test_health_is_running_with_fresh_modbus_and_wind(self) -> None:
        service = GarageDoorService(settings(), FakeTelemetry())
        now = datetime.now(timezone.utc)
        service.state = ServiceState(
            last_modbus_success=now,
            mqtt_connected=True,
            last_wind_at=now,
            wind_speed_mph=8,
        )
        status, payload = service.health_payload()
        self.assertEqual(status.value, 200)
        self.assertEqual(payload["status"], "running")

    def test_health_is_degraded_when_wind_is_stale(self) -> None:
        service = GarageDoorService(settings(), FakeTelemetry())
        now = datetime.now(timezone.utc)
        service.state = ServiceState(
            last_modbus_success=now,
            mqtt_connected=True,
            last_wind_at=now - timedelta(seconds=301),
        )
        status, payload = service.health_payload()
        self.assertEqual(status.value, 503)
        self.assertEqual(payload["status"], "degraded")

    def test_open_door_after_cutoff_emits_cutoff_alert(self) -> None:
        configuration = settings()
        configuration = Settings(**{**configuration.__dict__, "door_open_cutoff": time(0, 0)})
        telemetry = FakeTelemetry()
        service = GarageDoorService(configuration, telemetry)
        service.state.door_open = True
        service.state.last_wind_at = datetime.now(timezone.utc)
        service.state.wind_speed_mph = 0

        service._evaluate_alerts()

        self.assertEqual([condition for condition, _ in telemetry.alerts], ["door_open_after_cutoff"])

    def test_open_door_with_high_wind_emits_wind_alert(self) -> None:
        configuration = settings()
        configuration = Settings(**{**configuration.__dict__, "door_open_cutoff": time(23, 59)})
        telemetry = FakeTelemetry()
        service = GarageDoorService(configuration, telemetry)
        service.state.door_open = True
        service.state.last_wind_at = datetime.now(timezone.utc)
        service.state.wind_speed_mph = 8

        service._evaluate_alerts()

        self.assertIn("door_open_high_wind", [condition for condition, _ in telemetry.alerts])


if __name__ == "__main__":
    unittest.main()