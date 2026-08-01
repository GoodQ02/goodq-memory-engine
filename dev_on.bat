@echo off
REM GoodQ4All - Local Agent Mode (Dev On)
REM Validates local config, then starts the GoodQ-owned runtime services.
set "WSL_DISTRO=Ubuntu-22.04"

echo [DEV ON] Resolving the GoodQ Python environment...

set "PYTHONPATH=%~dp0"
set "PYTHON_EXE="
if exist "%USERPROFILE%\miniconda3\envs\goodq_core\python.exe" set "PYTHON_EXE=%USERPROFILE%\miniconda3\envs\goodq_core\python.exe"
if not defined PYTHON_EXE if exist "%USERPROFILE%\anaconda3\envs\goodq_core\python.exe" set "PYTHON_EXE=%USERPROFILE%\anaconda3\envs\goodq_core\python.exe"
if not defined PYTHON_EXE if exist "C:\ProgramData\miniconda3\envs\goodq_core\python.exe" set "PYTHON_EXE=C:\ProgramData\miniconda3\envs\goodq_core\python.exe"
if not defined PYTHON_EXE if exist "C:\ProgramData\anaconda3\envs\goodq_core\python.exe" set "PYTHON_EXE=C:\ProgramData\anaconda3\envs\goodq_core\python.exe"
if not defined PYTHON_EXE set "PYTHON_EXE=python"

echo [DEV ON] Validating the resolved configuration...
"%PYTHON_EXE%" -c "from steps.common.config_loader import load_configs, validate_config_mapping; validate_config_mapping(load_configs())"
if errorlevel 1 (
    echo [ERROR] Config validation failed. Local Agent Mode was not started.
    exit /b 1
)

echo [DEV ON] Synchronizing verified WSL audio worker files...
"%PYTHON_EXE%" scripts\sync_wsl_audio_worker.py --distro "%WSL_DISTRO%"
if errorlevel 1 (
    echo [ERROR] WSL audio worker deployment is not verified. Local Agent Mode was not started.
    exit /b 1
)

echo [DEV ON] Starting canonical vLLM control...
set "GOODQ_NO_PAUSE=1"
call "%~dp0scripts\start_vllm_servers.bat"
if errorlevel 1 (
    echo [ERROR] vLLM did not reach its required active state.
    exit /b 1
)

echo [DEV ON] Starting local database services (Qdrant)...
net start "GoodQ_Qdrant" >nul 2>&1
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 http://127.0.0.1:6333/collections | Out-Null; exit 0 } catch { Write-Error $_; exit 1 }"
if errorlevel 1 (
    echo [ERROR] Qdrant is not reachable on 127.0.0.1:6333.
    exit /b 1
)

echo [DEV ON] Starting API Server and Ingestion Watchdog...

REM Ensure existing API / Watchdog instances are closed first to prevent conflicts
powershell -Command "Stop-Process -Id (Get-NetTCPConnection -LocalPort 30000 -ErrorAction SilentlyContinue).OwningProcess -Force -ErrorAction SilentlyContinue; Get-CimInstance Win32_Process -Filter 'name=''python.exe''' -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'api.server' -or $_.CommandLine -match 'cli.watchdog' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

REM Start API Server in a separate minimized window
set "GOODQ_PREWARM_RETRIEVAL_MODELS=1"
start "GoodQ_API" /min cmd.exe /c "C:\Users\jdben\miniconda3\condabin\conda.bat" run --no-capture-output -n goodq_core python -m api.server
set "GOODQ_PREWARM_RETRIEVAL_MODELS="

REM Start Ingestion Watchdog in a separate minimized window
start "GoodQ_Watchdog" /min cmd.exe /c "C:\Users\jdben\miniconda3\condabin\conda.bat" run --no-capture-output -n goodq_core python -m cli.watchdog

echo [DEV ON] Local agent mode activated.
echo vLLM endpoint:  http://127.0.0.1:38005/v1
echo GoodQ API:      http://127.0.0.1:30000
ping 127.0.0.1 -n 4 >nul

