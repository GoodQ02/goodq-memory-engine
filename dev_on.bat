@echo off
REM GoodQ4All - Local Agent Mode (Dev On)
REM Enables WSL keepalive, starts systemd vLLM, starts Qdrant, API Server, and Ingestion Watchdog.
set "WSL_DISTRO=Ubuntu-22.04"

echo [DEV ON] Booting WSL and starting vLLM...

REM Start Windows-side keepalive in the background
start /B wsl -d %WSL_DISTRO% -- sleep infinity

REM Start systemd service inside WSL
wsl -d %WSL_DISTRO% -u root -- systemctl start vllm-llama1b.service

echo [DEV ON] Starting local database services (Qdrant)...
REM Start Qdrant service on Windows if configured as service
net start "GoodQ_Qdrant" >nul 2>&1

echo [DEV ON] Starting API Server and Ingestion Watchdog...

set "PYTHONPATH=%~dp0"
set "PYTHON_EXE=C:\Users\jdben\miniconda3\envs\goodq_core\python.exe"

REM Ensure existing API / Watchdog instances are closed first to prevent conflicts
powershell -Command "Stop-Process -Id (Get-NetTCPConnection -LocalPort 30000 -ErrorAction SilentlyContinue).OwningProcess -Force -ErrorAction SilentlyContinue; Get-CimInstance Win32_Process -Filter 'name=''python.exe''' -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'api.server' -or $_.CommandLine -match 'cli.watchdog' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

REM Start API Server in a separate minimized window
start "GoodQ_API" /min "%PYTHON_EXE%" -m api.server

REM Start Ingestion Watchdog in a separate minimized window
start "GoodQ_Watchdog" /min "%PYTHON_EXE%" -m cli.watchdog

echo [DEV ON] Local agent mode activated.
echo vLLM endpoint:  http://127.0.0.1:38005/v1
echo GoodQ API:      http://127.0.0.1:30000
ping 127.0.0.1 -n 4 >nul

