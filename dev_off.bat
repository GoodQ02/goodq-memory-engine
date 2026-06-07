@echo off
REM GoodQ4All - Game Mode (Dev Off)
REM Stops the vLLM service, kills API and Watchdog, stops Qdrant, and shuts down WSL.
set "WSL_DISTRO=Ubuntu-22.04"

echo [DEV OFF] Deactivating local agent services...

REM Stop the vLLM systemd service cleanly first
wsl -d %WSL_DISTRO% -u root -- systemctl stop vllm-llama1b.service

REM Force shut down WSL VM to free 100% of memory and GPU VRAM
wsl --shutdown

REM Stop Windows-side API and Ingestion Watchdog processes
powershell -Command "Stop-Process -Id (Get-NetTCPConnection -LocalPort 30000 -ErrorAction SilentlyContinue).OwningProcess -Force -ErrorAction SilentlyContinue; Get-CimInstance Win32_Process -Filter 'name=''python.exe''' -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'api.server' -or $_.CommandLine -match 'cli.dog' -or $_.CommandLine -match 'cli.watchdog' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

REM Stop Qdrant service on Windows if running
net stop "GoodQ_Qdrant" >nul 2>&1

echo [DEV OFF] Game mode activated. All dev services stopped and VRAM reclaimed.
timeout /t 3 >nul
