#!/bin/bash
# vLLM systemd service installer for Llama-1B
# Creates a production-grade auto-starting service

set -e

echo "=================================================================="
echo "  vLLM Llama-1B systemd Service Installer"
echo "=================================================================="
echo ""

# Check if running in WSL
if ! grep -qi microsoft /proc/version; then
    echo "ERROR: This script must be run in WSL"
    exit 1
fi

echo "[1/6] Creating systemd service file..."

# Create the service file
sudo tee /etc/systemd/system/vllm-llama1b.service > /dev/null << 'EOF'
[Unit]
Description=vLLM Llama-3.2-1B-Instruct Server
After=network.target

[Service]
Type=simple
User=joesdomingo
WorkingDirectory=/home/joesdomingo/vllm_server
Environment="PATH=/home/joesdomingo/vllm_server/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="CUDA_VISIBLE_DEVICES=0"
ExecStart=/home/joesdomingo/vllm_server/venv/bin/python -m vllm.entrypoints.openai.api_server --model /mnt/l/_DATA/models/llm/huggingface/Llama-3.2-1B-Instruct --host 0.0.0.0 --port 38005 --gpu-memory-utilization 0.7 --max-model-len 8192
Restart=on-failure
RestartSec=10
StandardOutput=append:/home/joesdomingo/vllm_server/logs/vllm-service.log
StandardError=append:/home/joesdomingo/vllm_server/logs/vllm-service-error.log

[Install]
WantedBy=multi-user.target
EOF

echo "✓ Service file created: /etc/systemd/system/vllm-llama1b.service"
echo ""

echo "[2/6] Creating log directory..."
mkdir -p ~/vllm_server/logs
echo "✓ Log directory ready"
echo ""

echo "[3/6] Reloading systemd daemon..."
sudo systemctl daemon-reload
echo "✓ Daemon reloaded"
echo ""

echo "[4/6] Enabling vLLM service (auto-start on boot)..."
sudo systemctl enable vllm-llama1b.service
echo "✓ Service enabled"
echo ""

echo "[5/6] Starting vLLM service..."
sudo systemctl start vllm-llama1b.service
echo "✓ Service started"
echo ""

echo "[6/6] Checking service status..."
sleep 5
sudo systemctl status vllm-llama1b.service --no-pager -l || true
echo ""

echo "=================================================================="
echo "  Installation Complete!"
echo "=================================================================="
echo ""
echo "Service Management Commands:"
echo "  Status:  sudo systemctl status vllm-llama1b"
echo "  Start:   sudo systemctl start vllm-llama1b"
echo "  Stop:    sudo systemctl stop vllm-llama1b"
echo "  Restart: sudo systemctl restart vllm-llama1b"
echo "  Logs:    journalctl -u vllm-llama1b -f"
echo ""
echo "Service will auto-start on WSL boot!"
echo ""
echo "Logs saved to:"
echo "  ~/vllm_server/logs/vllm-service.log"
echo "  ~/vllm_server/logs/vllm-service-error.log"
echo ""
echo "Testing in 30 seconds..."
sleep 30

echo "Testing endpoint..."
if curl -s http://localhost:38005/v1/models > /dev/null 2>&1; then
    echo "✅ vLLM service is responding!"
else
    echo "⚠️  Service may still be loading. Check with:"
    echo "   journalctl -u vllm-llama1b -f"
fi
echo ""
