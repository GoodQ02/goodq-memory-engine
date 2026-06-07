@echo off
REM GoodQ4All - Game Mode (Dev Off)
REM Stops the vLLM service and shuts down WSL completely to reclaim all VRAM.
set "WSL_DISTRO=Ubuntu-22.04"

echo [DEV OFF] Deactivating local agent and shutting down WSL...

REM Stop the vLLM systemd service cleanly first
wsl -d %WSL_DISTRO% -u root -- systemctl stop vllm-llama1b.service

REM Force shut down WSL VM to free 100% of memory and GPU VRAM
wsl --shutdown

echo [DEV OFF] Game mode activated. 100%% VRAM reclaimed.
timeout /t 3 >nul
