# Garage Door Monitor Deployment

Deploy `scripts/oh_analytics/garage_door.py` as a systemd service on a Linux
host. The service reads the Modbus garage-door input, subscribes to MQTT wind
data, sends OTLP alerts, and serves a local health endpoint.

## Prerequisites

Install the repository on the target host at `/opt/home_automation` and create
a dedicated, non-login service account:

```sh
sudo useradd --system --user-group --home-dir /opt/home_automation garage-door
sudo chown -R garage-door:garage-door /opt/home_automation
```

Create a virtual environment and install the project dependencies:

```sh
cd /opt/home_automation
sudo -u garage-door python3 -m venv .venv
sudo -u garage-door .venv/bin/python -m pip install --upgrade pip
sudo -u garage-door .venv/bin/python -m pip install -r requirements.txt
```

## Configuration

Store the service configuration outside the repository so its hosts and
deployment-specific values are not committed:

```sh
sudo install --directory --owner=root --group=garage-door --mode=750 /etc/garage-door
sudo install --owner=root --group=garage-door --mode=640 \
  /opt/home_automation/scripts/oh_analytics/.env /etc/garage-door/garage-door.env
```

Edit `/etc/garage-door/garage-door.env` and set at least `MODBUS_HOST`. Verify
`MODBUS_INPUT_REGISTER_ADDRESS` with a known door state before relying on
alerts. The service reads input channel 6 as open when the channel is OFF.

## Systemd Service

Create `/etc/systemd/system/garage-door.service` with this sample service
description. Adjust the installation path or Python executable if the host
uses a different layout.

```ini
[Unit]
Description=Garage door Modbus monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=garage-door
Group=garage-door
WorkingDirectory=/opt/home_automation/scripts/oh_analytics
EnvironmentFile=/etc/garage-door/garage-door.env
ExecStart=/opt/home_automation/.venv/bin/python /opt/home_automation/scripts/oh_analytics/garage_door.py
Restart=on-failure
RestartSec=10
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

The repository also includes this baseline unit at
`scripts/oh_analytics/garage-door.service`; the sample above uses the virtual
environment created during deployment.

Enable and start the service:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now garage-door.service
sudo systemctl status garage-door.service
```

## Verification and Operations

The health endpoint binds to `127.0.0.1:8088` by default. A successful,
fully-connected monitor returns HTTP 200 and `"status": "running"`:

```sh
curl --fail http://127.0.0.1:8088/health
sudo journalctl --unit=garage-door.service --follow
```

After updating the code, reinstall dependencies when `requirements.txt`
changes, then restart the service:

```sh
cd /opt/home_automation
sudo -u garage-door .venv/bin/python -m pip install -r requirements.txt
sudo systemctl restart garage-door.service
```

Do not expose the health port publicly unless an authenticated monitoring
system requires it. Keep `/etc/garage-door/garage-door.env` readable only by
root and the `garage-door` group.