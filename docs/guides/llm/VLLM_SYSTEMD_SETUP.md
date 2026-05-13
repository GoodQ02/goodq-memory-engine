# vLLM systemd Service Setup - Advanced Operator Reference

**Status:** Advanced operator reference. Prefer `scripts/wsl/install_vllm_service.sh` for the supported setup path when the repo checkout is available from WSL.

**Use this page only for manual recovery or debugging.** Replace `<wsl_user>`, `<wsl_vllm_home>`, and `<wsl_model_path>` before running commands. Windows callers should still test the service via `http://localhost:38005`.

**Network note:** The examples below keep `--host 0.0.0.0` because the current WSL/vLLM service scripts still bind that way for Windows access. That bind is advanced/operator-facing, not part of the canonical bootstrap path.

**Placeholder note:** For mounted Windows models, resolve `<wsl_model_path>` to the WSL-visible model directory, for example `/mnt/<drive>/<goodq_data_root>/models/llm/huggingface/Llama-3.2-1B-Instruct`.

---

## Step 1: Create systemd service file

```bash
sudo tee /etc/systemd/system/vllm-llama1b.service > /dev/null << 'EOF'
[Unit]
Description=vLLM Llama-3.2-1B-Instruct Server
After=network.target

[Service]
Type=simple
User=<wsl_user>
WorkingDirectory=<wsl_vllm_home>
Environment="PATH=<wsl_vllm_home>/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="CUDA_VISIBLE_DEVICES=0"
ExecStart=<wsl_vllm_home>/venv/bin/python -m vllm.entrypoints.openai.api_server --model <wsl_model_path> --host 0.0.0.0 --port 38005 --gpu-memory-utilization 0.7 --max-model-len 8192
Restart=on-failure
RestartSec=10
StandardOutput=append:<wsl_vllm_home>/logs/vllm-service.log
StandardError=append:<wsl_vllm_home>/logs/vllm-service-error.log

[Install]
WantedBy=multi-user.target
EOF
```

---

## Step 2: Create log directory

```bash
mkdir -p <wsl_vllm_home>/logs
```

---

## Step 3: Reload systemd

```bash
sudo systemctl daemon-reload
```

---

## Step 4: Enable auto-start

```bash
sudo systemctl enable vllm-llama1b.service
```

---

## Step 5: Start the service

```bash
sudo systemctl start vllm-llama1b.service
```

---

## Step 6: Check status

```bash
sudo systemctl status vllm-llama1b.service
```

Expected output:
```
vllm-llama1b.service - vLLM Llama-3.2-1B-Instruct Server
   Loaded: loaded (/etc/systemd/system/vllm-llama1b.service; enabled)
   Active: active (running) since ...
```

---

## Step 7: Test from Windows

In PowerShell:

```powershell
curl http://localhost:38005/v1/models
```

---

## Service Management Commands

```bash
# Check status
sudo systemctl status vllm-llama1b

# Start
sudo systemctl start vllm-llama1b

# Stop
sudo systemctl stop vllm-llama1b

# Restart
sudo systemctl restart vllm-llama1b

# View logs (live)
journalctl -u vllm-llama1b -f

# View recent logs
journalctl -u vllm-llama1b -n 100 --no-pager

# Disable auto-start
sudo systemctl disable vllm-llama1b

# Re-enable auto-start
sudo systemctl enable vllm-llama1b
```

---

## Log Files

Service writes to:

- Standard output: `<wsl_vllm_home>/logs/vllm-service.log`
- Error output: `<wsl_vllm_home>/logs/vllm-service-error.log`
- System journal: `journalctl -u vllm-llama1b`

---

## Troubleshooting

### Service will not start

```bash
# Check logs
journalctl -u vllm-llama1b -n 50 --no-pager

# Check if port is in use
lsof -i:38005

# Verify service file
systemctl cat vllm-llama1b
```

### Service crashes on start

```bash
# Check error log
tail -50 <wsl_vllm_home>/logs/vllm-service-error.log

# Check GPU
nvidia-smi

# Try manual start to see error
cd <wsl_vllm_home>
source venv/bin/activate
python -m vllm.entrypoints.openai.api_server \
    --model <wsl_model_path> \
    --host 0.0.0.0 \
    --port 38005 \
    --gpu-memory-utilization 0.7 \
    --max-model-len 8192
```

### Restart after crash

```bash
# Service will auto-restart (RestartSec=10)
# Or manually restart:
sudo systemctl restart vllm-llama1b
```

---

## Why use the systemd service

- Auto-starts on WSL boot
- Runs in background without keeping a terminal open
- Auto-restarts on failure
- Keeps logs in one predictable place
- Uses standard service management commands

---

## Copy-paste all commands at once

```bash
# Replace these placeholders before running
WSL_USER="<wsl_user>"
VLLM_HOME="<wsl_vllm_home>"
MODEL_PATH="<wsl_model_path>"

# Stop any running vLLM first
pkill -f 'vllm.*38005'

# Create service file
sudo tee /etc/systemd/system/vllm-llama1b.service > /dev/null << EOF
[Unit]
Description=vLLM Llama-3.2-1B-Instruct Server
After=network.target

[Service]
Type=simple
User=${WSL_USER}
WorkingDirectory=${VLLM_HOME}
Environment="PATH=${VLLM_HOME}/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="CUDA_VISIBLE_DEVICES=0"
ExecStart=${VLLM_HOME}/venv/bin/python -m vllm.entrypoints.openai.api_server --model ${MODEL_PATH} --host 0.0.0.0 --port 38005 --gpu-memory-utilization 0.7 --max-model-len 8192
Restart=on-failure
RestartSec=10
StandardOutput=append:${VLLM_HOME}/logs/vllm-service.log
StandardError=append:${VLLM_HOME}/logs/vllm-service-error.log

[Install]
WantedBy=multi-user.target
EOF

# Setup and start
mkdir -p "${VLLM_HOME}/logs"
sudo systemctl daemon-reload
sudo systemctl enable vllm-llama1b.service
sudo systemctl start vllm-llama1b.service

# Wait for startup
sleep 30

# Check status
sudo systemctl status vllm-llama1b.service

# Test
curl http://localhost:38005/v1/models
```

---

**After running these commands, vLLM will auto-start every time WSL starts.**
