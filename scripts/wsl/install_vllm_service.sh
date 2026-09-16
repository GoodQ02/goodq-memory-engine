#!/bin/bash
# vLLM systemd service installer for the local GoodQ primary LLM.
# Installs the on-demand WSL owner used by Dev On/Dev Off, bound to localhost.

set -euo pipefail
WSL_USER="${GOODQ_WSL_USER:-${SUDO_USER:-$(whoami)}}"
WSL_HOME="/home/${WSL_USER}"
VLLM_HOME="${GOODQ_WSL_VLLM_HOME:-${WSL_HOME}/vllm_server}"
MODEL_PATH="${GOODQ_WSL_MODEL_PATH:-${WSL_HOME}/models/Qwen2.5-0.5B-Instruct}"
SERVED_MODEL_NAME="${GOODQ_VLLM_SERVED_MODEL_NAME:-goodq-qwen-speed}"
VLLM_HOST="${GOODQ_WSL_VLLM_HOST:-127.0.0.1}"
VLLM_PORT="${GOODQ_WSL_VLLM_PORT:-38005}"
VLLM_GPU_MEMORY_UTILIZATION="${GOODQ_WSL_VLLM_GPU_MEMORY_UTILIZATION:-0.7}"
VLLM_MAX_MODEL_LEN="${GOODQ_WSL_VLLM_MAX_MODEL_LEN:-8192}"
VLLM_KV_CACHE_DTYPE="${GOODQ_WSL_VLLM_KV_CACHE_DTYPE:-fp8}"
LOG_DIR="${VLLM_HOME}/logs"
if [[ "${EUID}" -eq 0 ]]; then
    SUDO=()
else
    SUDO=(sudo)
fi

if [[ "${WSL_USER}" == "root" ]]; then
    echo "ERROR: set GOODQ_WSL_USER to the non-root WSL user that owns the vLLM environment."
    exit 1
fi

echo "=================================================================="
echo "  GoodQ4All vLLM systemd Service Installer"
echo "=================================================================="
echo ""

# Check if running in WSL
if ! grep -qi microsoft /proc/version; then
    echo "ERROR: This script must be run in WSL"
    exit 1
fi

if [[ ! -x "${VLLM_HOME}/venv/bin/python" ]]; then
    echo "ERROR: vLLM Python not found at ${VLLM_HOME}/venv/bin/python"
    exit 1
fi

if [[ ! -d "${MODEL_PATH}" ]]; then
    echo "ERROR: model path not found: ${MODEL_PATH}"
    exit 1
fi

echo "[1/6] Creating systemd service file..."

# Create the service file
"${SUDO[@]}" tee /etc/systemd/system/vllm-llama1b.service > /dev/null << EOF
[Unit]
Description=GoodQ4All vLLM Primary LLM Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${WSL_USER}
WorkingDirectory=${VLLM_HOME}
Environment="PATH=${VLLM_HOME}/venv/bin:/usr/local/cuda-12.1/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="CUDA_HOME=/usr/local/cuda-12.1"
Environment="CUDA_VISIBLE_DEVICES=0"
ExecStart=${VLLM_HOME}/venv/bin/python -m vllm.entrypoints.openai.api_server --model ${MODEL_PATH} --served-model-name ${SERVED_MODEL_NAME} --host ${VLLM_HOST} --port ${VLLM_PORT} --gpu-memory-utilization ${VLLM_GPU_MEMORY_UTILIZATION} --max-model-len ${VLLM_MAX_MODEL_LEN} --kv-cache-dtype ${VLLM_KV_CACHE_DTYPE}
Restart=on-failure
RestartSec=10
KillMode=mixed
TimeoutStopSec=45
StandardOutput=append:${LOG_DIR}/vllm-service.log
StandardError=append:${LOG_DIR}/vllm-service-error.log

[Install]
WantedBy=multi-user.target
EOF

echo "Service file created: /etc/systemd/system/vllm-llama1b.service"
echo "Service user: ${WSL_USER}"
echo "Model: ${MODEL_PATH}"
echo "Served model name: ${SERVED_MODEL_NAME}"
echo "Endpoint: http://${VLLM_HOST}:${VLLM_PORT}/v1"
echo ""

echo "[2/6] Creating log directory..."
mkdir -p "$LOG_DIR"
echo "Log directory ready"
echo ""

echo "[3/6] Reloading systemd daemon..."
"${SUDO[@]}" systemctl daemon-reload
echo "Daemon reloaded"
echo ""

echo "[4/6] Disabling independent WSL boot startup..."
"${SUDO[@]}" systemctl disable vllm-llama1b.service
echo "Service is on demand; Dev On/Dev Off own its lifecycle"
echo ""

echo "[5/6] Preserving the current running state..."
echo "No model is started or restarted during installation."
echo ""

echo "[6/6] Checking service status..."
"${SUDO[@]}" systemctl show vllm-llama1b.service --property=LoadState,ActiveState,UnitFileState
echo ""

echo "=================================================================="
echo "  Installation Complete!"
echo "=================================================================="
echo ""
echo "Service Management Commands:"
echo "  Status:  systemctl status vllm-llama1b"
echo "  Start:   systemctl start vllm-llama1b"
echo "  Stop:    systemctl stop vllm-llama1b"
echo "  Restart: systemctl restart vllm-llama1b"
echo "  Logs:    journalctl -u vllm-llama1b -f"
echo ""
echo "Service will remain off after WSL boot until explicitly started."
echo "Use Dev On/Dev Off, or scripts/start_vllm_servers.bat and scripts/stop_vllm_servers.bat."
echo ""
echo "Logs saved to:"
echo "  ~/vllm_server/logs/vllm-service.log"
echo "  ~/vllm_server/logs/vllm-service-error.log"
echo ""
echo "The Windows start control performs the bounded model-endpoint readiness check."
echo ""
