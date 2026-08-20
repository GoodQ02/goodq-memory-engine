@echo off
REM GoodQ4All - Local Agent Mode (Dev On)
REM Validates local config, then starts the GoodQ-owned runtime services.
call "%~dp0scripts\_lib\interpreter_bindings.bat"
if "%WSL_DISTRO%"=="" set "WSL_DISTRO=%GOODQ_WSL_DISTRO%"
if "%WSL_DISTRO%"=="" set "WSL_DISTRO=Ubuntu-22.04"
set "GOODQ_WSL_DISTRO=%WSL_DISTRO%"

call :dashboard -Event start

echo [DEV ON] Resolving the GoodQ Python environment...

set "PYTHONPATH=%~dp0"
set "PYTHON_EXE="
if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PYTHON_EXE=%CONDA_PREFIX%\python.exe"
if not defined PYTHON_EXE if defined CONDA_EXE for %%I in ("%CONDA_EXE%") do if exist "%%~dpI..\envs\%GOODQ_CONDA_ENV%\python.exe" set "PYTHON_EXE=%%~dpI..\envs\%GOODQ_CONDA_ENV%\python.exe"
if not defined PYTHON_EXE if exist "%USERPROFILE%\miniconda3\envs\goodq_core\python.exe" set "PYTHON_EXE=%USERPROFILE%\miniconda3\envs\goodq_core\python.exe"
if not defined PYTHON_EXE if exist "%USERPROFILE%\anaconda3\envs\goodq_core\python.exe" set "PYTHON_EXE=%USERPROFILE%\anaconda3\envs\goodq_core\python.exe"
if not defined PYTHON_EXE if exist "C:\ProgramData\miniconda3\envs\goodq_core\python.exe" set "PYTHON_EXE=C:\ProgramData\miniconda3\envs\goodq_core\python.exe"
if not defined PYTHON_EXE if exist "C:\ProgramData\anaconda3\envs\goodq_core\python.exe" set "PYTHON_EXE=C:\ProgramData\anaconda3\envs\goodq_core\python.exe"
if not defined PYTHON_EXE set "PYTHON_EXE=python"

echo [DEV ON] Validating the resolved configuration...
"%PYTHON_EXE%" -c "from steps.common.config_loader import load_configs, validate_config_mapping; validate_config_mapping(load_configs())"
if errorlevel 1 (
    echo [ERROR] Config validation failed. Local Agent Mode was not started.
    call :dashboard -Event node -Node CONFIG -State blocked -Message "configuration validation failed"
    goto :blocked
)
call :dashboard -Event node -Node CONFIG -State ready -Message "configuration validated"

echo [DEV ON] Synchronizing verified WSL audio worker files...
"%PYTHON_EXE%" scripts\sync_wsl_audio_worker.py --distro "%WSL_DISTRO%"
if errorlevel 1 (
    echo [ERROR] WSL audio worker deployment is not verified. Local Agent Mode was not started.
    call :dashboard -Event node -Node "WSL AUDIO" -State blocked -Message "worker deployment is not verified"
    goto :blocked
)
call :dashboard -Event node -Node "WSL AUDIO" -State ready -Message "worker hashes verified"

echo [DEV ON] Starting canonical vLLM control...
set "GOODQ_CALLER_NO_PAUSE=%GOODQ_NO_PAUSE%"
set "GOODQ_NO_PAUSE=1"
call "%~dp0scripts\start_vllm_servers.bat"
set "VLLM_EXIT_CODE=%ERRORLEVEL%"
set "GOODQ_NO_PAUSE=%GOODQ_CALLER_NO_PAUSE%"
set "GOODQ_CALLER_NO_PAUSE="
if not "%VLLM_EXIT_CODE%"=="0" (
    echo [ERROR] vLLM did not reach its required active state.
    call :dashboard -Event node -Node vLLM -State blocked -Message "speed endpoint did not become ready"
    goto :blocked
)
call :dashboard -Event node -Node vLLM -State ready -Message "speed endpoint is available"

echo [DEV ON] Starting local database services (Qdrant)...
net start "GoodQ_Qdrant" >nul 2>&1
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 http://127.0.0.1:6333/collections | Out-Null; exit 0 } catch { Write-Error $_; exit 1 }"
if errorlevel 1 (
    echo [ERROR] Qdrant is not reachable on 127.0.0.1:6333.
    call :dashboard -Event node -Node QDRANT -State blocked -Message "loopback health check failed"
    goto :blocked
)
call :dashboard -Event node -Node QDRANT -State ready -Message "loopback store is available"

echo [DEV ON] Starting API Server and Ingestion Watchdog...

REM Ensure existing API / Watchdog instances are closed first to prevent conflicts
powershell -NoProfile -Command "$conn = Get-NetTCPConnection -LocalPort 30000 -ErrorAction SilentlyContinue; if ($conn) { Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue }; Get-CimInstance Win32_Process -Filter 'name=''python.exe''' -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'api.server' -or $_.CommandLine -match 'cli.watchdog' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; $deadline = (Get-Date).AddSeconds(3); do { if (-not (Get-NetTCPConnection -LocalPort 30000 -ErrorAction SilentlyContinue)) { exit 0 }; Start-Sleep -Milliseconds 200 } while ((Get-Date) -lt $deadline)"

REM Start API Server in a separate minimized window
set "GOODQ_PREWARM_RETRIEVAL_MODELS=1"
set "API_LAUNCH_LOG=%TEMP%\goodq_api_launch.log"
del /q "%API_LAUNCH_LOG%" >nul 2>&1
start "GoodQ_API" /min cmd.exe /d /c ""%PYTHON_EXE%" -m api.server 1>> "%API_LAUNCH_LOG%" 2>&1"
set "GOODQ_PREWARM_RETRIEVAL_MODELS="

echo [DEV ON] Local agent mode activated.
echo vLLM endpoint:  http://127.0.0.1:38005/v1
echo GoodQ API:      http://127.0.0.1:30000
powershell -NoProfile -Command "$deadline = (Get-Date).AddSeconds(60); do { try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 http://127.0.0.1:30000/ | Out-Null; exit 0 } catch { Start-Sleep -Seconds 1 } } while ((Get-Date) -lt $deadline); Write-Error ('API did not become ready. launch_log=' + $env:API_LAUNCH_LOG); if (Test-Path -LiteralPath $env:API_LAUNCH_LOG) { Get-Content -LiteralPath $env:API_LAUNCH_LOG -Tail 12 | ForEach-Object { Write-Error $_ } }; exit 1"
if errorlevel 1 (
    call :dashboard -Event node -Node API -State blocked -Message "loopback endpoint did not become ready; launch log is shown above"
    goto :blocked
)
call :dashboard -Event node -Node API -State ready -Message "loopback endpoint is available"

REM Start the watchdog only after API readiness to avoid concurrent conda-run temp-file contention.
set "WATCHDOG_LAUNCH_LOG=%TEMP%\goodq_watchdog_launch.log"
del /q "%WATCHDOG_LAUNCH_LOG%" >nul 2>&1
start "GoodQ_Watchdog" /min cmd.exe /d /c ""%PYTHON_EXE%" -m cli.watchdog 1>> "%WATCHDOG_LAUNCH_LOG%" 2>&1"

powershell -NoProfile -Command "$deadline = (Get-Date).AddSeconds(15); do { if (Get-CimInstance Win32_Process -Filter 'name=''python.exe''' -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'cli.watchdog' }) { exit 0 }; Start-Sleep -Seconds 1 } while ((Get-Date) -lt $deadline); Write-Error ('Watchdog did not stay running. launch_log=' + $env:WATCHDOG_LAUNCH_LOG); if (Test-Path -LiteralPath $env:WATCHDOG_LAUNCH_LOG) { Get-Content -LiteralPath $env:WATCHDOG_LAUNCH_LOG -Tail 12 | ForEach-Object { Write-Error $_ } }; exit 1"
if errorlevel 1 (
    call :dashboard -Event node -Node WATCHDOG -State blocked -Message "process did not stay running; launch log is shown above"
    goto :blocked
)
call :dashboard -Event node -Node WATCHDOG -State ready -Message "ingestion monitor is running"
call :dashboard -Event final -State ready -Message "All verified services are available."
goto :finish

:blocked
call :dashboard -Event final -State blocked -Message "Build Mode was not activated. See the first blocked node above."
set "DEV_ON_EXIT_CODE=1"
goto :finish

:dashboard
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev_mode_dashboard.ps1" -Mode dev-on %*
exit /b %errorlevel%

:finish
if /i not "%GOODQ_NO_PAUSE%"=="1" pause
exit /b %DEV_ON_EXIT_CODE%

