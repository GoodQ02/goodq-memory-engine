#!/usr/bin/env bash
set -euo pipefail

# Install/enable systemd service for GoodQ WSL2 audio_service.py
# Run inside WSL as joesdomingo (or adjust USER/HOME)

SERVICE_NAME=goodq-audio.service
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"

cat <<'EOF' | sudo tee "$SERVICE_PATH" >/dev/null
[Unit]
Description=GoodQ WSL2 Audio Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=joesdomingo
WorkingDirectory=/home/joesdomingo/goodq_audio
Environment=HOME=/home/joesdomingo
ExecStart=/home/joesdomingo/goodq_audio/venv/bin/python /mnt/l/goodq4all/wsl2_audio/audio_service.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"
sudo systemctl status "$SERVICE_NAME" --no-pager

echo "Service installed: $SERVICE_PATH"
