#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="dpf-mqtt-ingestor.service"
REPO_DIR="${1:-$(pwd)}"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"
ENV_FILE="/etc/dpf-backend.env"
VENV_BIN="${REPO_DIR}/backend/.venv/bin/dpf-mqtt-ingestor"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Create it before installing the service." >&2
  exit 1
fi

if [[ ! -x "${VENV_BIN}" ]]; then
  echo "Missing executable ${VENV_BIN}. Run: backend/.venv/bin/pip install -e backend" >&2
  exit 1
fi

sudo tee "${SERVICE_PATH}" >/dev/null <<SERVICE
[Unit]
Description=DPF tracker MQTT ingestor
After=network-online.target postgresql.service mosquitto.service
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=${REPO_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_BIN} --log-level INFO
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"

echo "Installed ${SERVICE_PATH}"
echo "Start with: sudo systemctl start ${SERVICE_NAME}"
echo "Check with: sudo systemctl status ${SERVICE_NAME}"
