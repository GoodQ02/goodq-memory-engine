# vLLM systemd Service Setup - Manual Instructions

**Run these commands in your WSL terminal (where vLLM is currently stopped)**

---

## Step 1: Create systemd service file

```bash
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
ExecStart=/home/joesdomingo/vllm_server/venv/bin/python -m vllm.entrypoints.openai.api_server --model /mnt/l/_DATA/models/llm/huggingface/Llama-3.2-1B-Instruct --host 0.0.0.0 --port 8003 --gpu-memory-utilization 0.7 --max-model-len 8192
Restart=on-failure
RestartSec=10
StandardOutput=append:/home/joesdomingo/vllm_server/logs/vllm-service.log
StandardError=append:/home/joesdomingo/vllm_server/logs/vllm-service-error.log

[Install]
WantedBy=multi-user.target
EOF
```

---

## Step 2: Create log directory

```bash
mkdir -p ~/vllm_server/logs
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
● vllm-llama1b.service - vLLM Llama-3.2-1B-Instruct Server
     Loaded: loaded (/etc/systemd/system/vllm-llama1b.service; enabled)
     Active: active (running) since ...
```

---

## Step 7: Test from Windows

In PowerShell:
```powershell
curl http://localhost:8003/v1/models
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
- **Standard output**: `~/vllm_server/logs/vllm-service.log`
- **Error output**: `~/vllm_server/logs/vllm-service-error.log`
- **System journal**: `journalctl -u vllm-llama1b`

---

## Troubleshooting

### Service won't start
```bash
# Check logs
journalctl -u vllm-llama1b -n 50 --no-pager

# Check if port is in use
lsof -i:8003

# Verify service file
systemctl cat vllm-llama1b
```

### Service crashes on start
```bash
# Check error log
tail -50 ~/vllm_server/logs/vllm-service-error.log

# Check GPU
nvidia-smi

# Try manual start to see error
cd ~/vllm_server
source venv/bin/activate
python -m vllm.entrypoints.openai.api_server \
    --model /mnt/l/_DATA/models/llm/huggingface/Llama-3.2-1B-Instruct \
    --host 0.0.0.0 \
    --port 8003 \
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

## Benefits of systemd Service

✅ **Auto-starts on WSL boot**
✅ **Runs in background** (no terminal needed)
✅ **Auto-restarts on failure**
✅ **Proper logging**
✅ **Standard management commands**
✅ **Survives terminal closing**
✅ **Just like Ollama!**

---

## Copy-Paste All Commands at Once

```bash
# Stop any running vLLM first
pkill -f 'vllm.*8003'

# Create service file
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
ExecStart=/home/joesdomingo/vllm_server/venv/bin/python -m vllm.entrypoints.openai.api_server --model /mnt/l/_DATA/models/llm/huggingface/Llama-3.2-1B-Instruct --host 0.0.0.0 --port 8003 --gpu-memory-utilization 0.7 --max-model-len 8192
Restart=on-failure
RestartSec=10
StandardOutput=append:/home/joesdomingo/vllm_server/logs/vllm-service.log
StandardError=append:/home/joesdomingo/vllm_server/logs/vllm-service-error.log

[Install]
WantedBy=multi-user.target
EOF

# Setup and start
mkdir -p ~/vllm_server/logs
sudo systemctl daemon-reload
sudo systemctl enable vllm-llama1b.service
sudo systemctl start vllm-llama1b.service

# Wait for startup
sleep 30

# Check status
sudo systemctl status vllm-llama1b.service

# Test
curl http://localhost:8003/v1/models
```

---

**After running these commands, vLLM will auto-start every time WSL starts, just like Ollama!**
