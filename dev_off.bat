@echo off
REM GoodQ4All - Game Mode (Dev Off)
REM Stops GPU-backed and API services while retaining loopback Qdrant for a fast Dev On return.
set "WSL_DISTRO=Ubuntu-22.04"

echo [DEV OFF] Deactivating local agent services...

REM Stop the GoodQ-owned vLLM service and keepalive anchor first.
set "GOODQ_NO_PAUSE=1"
call "%~dp0scripts\stop_vllm_servers.bat"

REM Force shut down WSL VM to free 100% of memory and GPU VRAM
wsl --shutdown

REM Stop Windows-side API and Ingestion Watchdog processes
powershell -Command "$conn = Get-NetTCPConnection -LocalPort 30000 -ErrorAction SilentlyContinue; if ($conn) { Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue }; Get-CimInstance Win32_Process -Filter 'name=''python.exe''' -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'api.server' -or $_.CommandLine -match 'cli.dog' -or $_.CommandLine -match 'cli.watchdog' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

REM Qdrant remains available on loopback: it uses no GPU and avoids an index-service restart.

echo [DEV OFF] Game mode activated. GPU services stopped, VRAM reclaimed, Qdrant remains available.
ping 127.0.0.1 -n 4 >nul

