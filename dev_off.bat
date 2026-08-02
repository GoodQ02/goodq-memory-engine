@echo off
REM GoodQ4All - Game Mode (Dev Off)
REM Stops GPU-backed and API services while retaining loopback Qdrant for a fast Dev On return.
set "WSL_DISTRO=Ubuntu-22.04"

call :dashboard -Event start

echo [DEV OFF] Deactivating local agent services...

REM Stop the GoodQ-owned vLLM service and keepalive anchor first.
set "GOODQ_CALLER_NO_PAUSE=%GOODQ_NO_PAUSE%"
set "GOODQ_NO_PAUSE=1"
call "%~dp0scripts\stop_vllm_servers.bat"
set "VLLM_EXIT_CODE=%ERRORLEVEL%"
set "GOODQ_NO_PAUSE=%GOODQ_CALLER_NO_PAUSE%"
set "GOODQ_CALLER_NO_PAUSE="
if not "%VLLM_EXIT_CODE%"=="0" (
    call :dashboard -Event node -Node vLLM -State blocked -Message "stop control reported a failure"
    goto :blocked
)
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 http://127.0.0.1:38005/v1/models | Out-Null; exit 1 } catch { exit 0 }"
if errorlevel 1 (
    call :dashboard -Event node -Node vLLM -State blocked -Message "speed endpoint is still reachable"
    goto :blocked
)
call :dashboard -Event node -Node vLLM -State released -Message "speed endpoint is stopped"

REM Force shut down WSL VM to free 100% of memory and GPU VRAM
wsl --shutdown
if errorlevel 1 (
    call :dashboard -Event node -Node "WSL AUDIO" -State blocked -Message "WSL shutdown command failed"
    goto :blocked
)
wsl --list --running | findstr /i /c:"%WSL_DISTRO%" >nul
if not errorlevel 1 (
    call :dashboard -Event node -Node "WSL AUDIO" -State blocked -Message "WSL distribution is still running"
    goto :blocked
)
call :dashboard -Event node -Node "WSL AUDIO" -State released -Message "compute extension is stopped"

REM Stop Windows-side API and Ingestion Watchdog processes
powershell -NoProfile -Command "$conn = Get-NetTCPConnection -LocalPort 30000 -ErrorAction SilentlyContinue; if ($conn) { Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue }; Get-CimInstance Win32_Process -Filter 'name=''python.exe''' -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'api.server' -or $_.CommandLine -match 'cli.dog' -or $_.CommandLine -match 'cli.watchdog' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
powershell -NoProfile -Command "$apiPort = Get-NetTCPConnection -LocalPort 30000 -ErrorAction SilentlyContinue; $services = Get-CimInstance Win32_Process -Filter 'name=''python.exe''' -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'api.server' -or $_.CommandLine -match 'cli.watchdog' }; if (-not $apiPort -and -not $services) { exit 0 }; exit 1"
if errorlevel 1 (
    call :dashboard -Event node -Node API -State blocked -Message "API process is still active"
    goto :blocked
)
call :dashboard -Event node -Node API -State released -Message "API process is stopped"
call :dashboard -Event node -Node WATCHDOG -State released -Message "ingestion monitor is stopped"

REM Qdrant remains available on loopback: it uses no GPU and avoids an index-service restart.
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 http://127.0.0.1:6333/collections | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
    call :dashboard -Event node -Node QDRANT -State blocked -Message "retained loopback store is not reachable"
    goto :blocked
)
call :dashboard -Event node -Node QDRANT -State retained -Message "loopback store remains available"

REM Display actual GPU process and memory state without treating desktop ownership as failure.
where nvidia-smi >nul 2>&1
if errorlevel 1 (
    call :dashboard -Event node -Node "NVIDIA-SMI" -State warn -Message "GPU telemetry utility is unavailable"
) else (
    call :dashboard -Event node -Node "NVIDIA-SMI" -State check -Message "GPU process and memory snapshot follows"
    nvidia-smi
)

echo [DEV OFF] Game mode activated. GPU services stopped, VRAM reclaimed, Qdrant remains available.
call :dashboard -Event final -State ready -Message "Qdrant retained on loopback."
goto :finish

:blocked
call :dashboard -Event final -State blocked -Message "Open Desktop was not fully released. See the first blocked node above."
set "DEV_OFF_EXIT_CODE=1"
goto :finish

:dashboard
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev_mode_dashboard.ps1" -Mode dev-off %*
exit /b %errorlevel%

:finish
if /i not "%GOODQ_NO_PAUSE%"=="1" pause
exit /b %DEV_OFF_EXIT_CODE%

