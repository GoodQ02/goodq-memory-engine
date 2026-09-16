@echo off
setlocal
set "DEV_ON_EXIT_CODE=0"
pushd "%~dp0" || exit /b 1
set "GOODQ_MODE_ROOT=%~dp0"
REM GoodQ4All - Local Agent Mode (Dev On)
REM Validates local config, then starts the GoodQ-owned runtime services.
REM Resolve the explicit binding before the legacy helper's discovery fallback.
set "GOODQ_MODE_WSL="
for /f "delims=" %%D in ('powershell -NoProfile -Command ". (Join-Path $env:GOODQ_MODE_ROOT 'scripts\_lib\interpreter_bindings.ps1'); Get-GoodQWslDistro -RequireConfigured"') do set "GOODQ_MODE_WSL=%%D"
if not defined GOODQ_MODE_WSL goto :blocked
set "GOODQ_WSL_DISTRO=%GOODQ_MODE_WSL%"
call "%~dp0scripts\_lib\interpreter_bindings.bat"

call :dashboard -Event start

REM Refuse collisions before loading models or changing WSL worker files.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_goodq_dev.ps1" -CheckStart
if errorlevel 1 goto :blocked

echo [DEV ON] Resolving the same core interpreter as the canonical owner...
set "PYTHONPATH=%~dp0"
set "PYTHON_EXE="
for /f "delims=" %%P in ('powershell -NoProfile -Command ". (Join-Path $env:GOODQ_MODE_ROOT 'scripts\_lib\interpreter_bindings.ps1'); Get-GoodQPythonExe"') do set "PYTHON_EXE=%%P"
if not defined PYTHON_EXE goto :blocked
if not exist "%PYTHON_EXE%" goto :blocked

echo [DEV ON] Validating the resolved configuration...
"%PYTHON_EXE%" -c "from steps.common.config_loader import load_configs, validate_config_mapping; validate_config_mapping(load_configs())"
if errorlevel 1 (
    echo [ERROR] Config validation failed. Local Agent Mode was not started.
    call :dashboard -Event node -Node CONFIG -State blocked -Message "configuration validation failed"
    goto :blocked
)
call :dashboard -Event node -Node CONFIG -State ready -Message "configuration validated"

echo [DEV ON] Synchronizing verified WSL audio worker files...
"%PYTHON_EXE%" scripts\sync_wsl_audio_worker.py --distro "%GOODQ_WSL_DISTRO%"
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

REM This foreground PowerShell process is the one canonical supervisor. Its
REM startup/health/drain receipts own the result; no second API/Watchdog launcher.
echo [DEV ON] Starting the canonical supervised GoodQ runtime...
echo [DEV ON] Keep this supervisor window open. Use Dev Off to drain active work.
echo [DEV ON] Hermes and whole-workstation model readiness require their separate gates.
set "GOODQ_PREWARM_RETRIEVAL_MODELS=1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_goodq_dev.ps1" -Supervise
set "DEV_ON_EXIT_CODE=%ERRORLEVEL%"
set "GOODQ_PREWARM_RETRIEVAL_MODELS="
if not "%DEV_ON_EXIT_CODE%"=="0" goto :blocked
echo [DEV ON] The supervised runtime has stopped. Its receipts retain the outcome.
goto :finish

:blocked
call :dashboard -Event final -State blocked -Message "Build Mode was not activated. See the first blocked node above."
set "DEV_ON_EXIT_CODE=1"
goto :finish

:dashboard
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev_mode_dashboard.ps1" -Mode dev-on %*
exit /b %errorlevel%

:finish
popd
if /i not "%GOODQ_NO_PAUSE%"=="1" pause
exit /b %DEV_ON_EXIT_CODE%

