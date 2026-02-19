#!/usr/bin/env bash
set -euo pipefail

# Install/enable systemd service for GoodQ WSL2 audio_service.py
# Run inside WSL and optionally set:
#   GOODQ_WSL_USER, GOODQ_WSL_WORKSPACE, GOODQ_WSL_PROJECT_ROOT

SERVICE_NAME=goodq-audio.service
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"
WSL_USER="${GOODQ_WSL_USER:-$(whoami)}"
WSL_HOME="/home/${WSL_USER}"
WSL_WORKSPACE="${GOODQ_WSL_WORKSPACE:-${WSL_HOME}/goodq_audio}"
WSL_PROJECT_ROOT="${GOODQ_WSL_PROJECT_ROOT:-/mnt/l/goodq4all}"

cat <<EOF | sudo tee "$SERVICE_PATH" >/dev/null
[Unit]
Description=GoodQ WSL2 Audio Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${WSL_USER}
WorkingDirectory=${WSL_WORKSPACE}
Environment=HOME=${WSL_HOME}
ExecStart=${WSL_WORKSPACE}/venv/bin/python ${WSL_PROJECT_ROOT}/wsl2_audio/audio_service.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"
sudo systemctl status "$SERVICE_NAME" --no-pager

echo "Service installed: $SERVICE_PATH"
