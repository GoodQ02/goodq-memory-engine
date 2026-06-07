@echo off
REM GoodQ4All - Local Agent Mode (Dev On)
REM Enables WSL keepalive and starts systemd vLLM service for local LLM inference.
set "WSL_DISTRO=Ubuntu-22.04"

echo [DEV ON] Booting WSL and starting vLLM...

REM Start Windows-side keepalive in the background
start /B wsl -d %WSL_DISTRO% -- sleep infinity

REM Start systemd service inside WSL
wsl -d %WSL_DISTRO% -u root -- systemctl start vllm-llama1b.service

echo [DEV ON] Local agent mode activated.
echo vLLM endpoint: http://127.0.0.1:38005/v1
timeout /t 3 >nul
