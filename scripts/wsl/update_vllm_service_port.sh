#!/bin/bash
# Helper to retarget the vllm-llama1b systemd unit to the normalized port (38005).
# Usage: sudo scripts/wsl/update_vllm_service_port.sh

set -euo pipefail

SERVICE_FILE="/etc/systemd/system/vllm-llama1b.service"
TARGET_PORT="38005"

if [[ $EUID -ne 0 ]]; then
  echo "[ERROR] Please run this script with sudo inside WSL." >&2
  exit 1
fi

if [[ ! -f "${SERVICE_FILE}" ]]; then
  echo "[ERROR] Service file not found at ${SERVICE_FILE}" >&2
  exit 1
fi

if ! grep -q -- "--port ${TARGET_PORT}" "${SERVICE_FILE}"; then
  sed -i "s/--port [0-9]\\+/--port ${TARGET_PORT}/" "${SERVICE_FILE}"
  echo "[INFO] Updated ${SERVICE_FILE} to use port ${TARGET_PORT}"
else
  echo "[INFO] Service already configured for port ${TARGET_PORT}"
fi

systemctl daemon-reload
systemctl restart vllm-llama1b

echo "[INFO] vLLM service restarted on port ${TARGET_PORT}"
echo "[INFO] Current status:"
systemctl status vllm-llama1b --no-pager | head -20
