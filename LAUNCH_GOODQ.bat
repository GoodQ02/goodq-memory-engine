@echo off
REM ================================================================================
REM  GoodQ4All - Master System Launcher
REM  Single Source of Truth for Starting the Complete System
REM ================================================================================

setlocal enabledelayedexpansion

title GoodQ4All Master Launcher
color 0B

echo.
echo ================================================================================
echo   _____                 _  ____    _  _    ___   _ _ 
echo  ^|  __ \               ^| ^|/ __ \  ^| ^|^| ^|  / _ \ ^| ^| ^|
echo  ^| ^|  \/ ___   ___   __^| ^| ^|  ^| ^|_^|^|_^| / /_\ \^| ^| ^|
echo  ^| ^| __ / _ \ / _ \ / _` ^| ^|  ^| ^| _^| ^|^|  _  ^|^| ^| ^|
echo  ^| ^|_\ \ (_) ^| (_) ^| (_^| ^| ^|__^| ^|_^|^|_^|^| ^| ^| ^|^| ^| ^|
echo   \____/\___/ \___/ \__,_^|\____/ \___/\_^| ^|_/\_\_^|
echo.
echo  Personal Memory ^& Knowledge Assistant
echo  Version 2.0 - Production Ready
echo ================================================================================
echo.

REM Navigate to project directory
cd /d "L:\goodq4all"

REM Prefer local virtual environment if present
set "PYTHON_CMD=python"
set "UVICORN_CMD="
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=.venv\Scripts\python.exe"
)

REM Always launch uvicorn via python -m so PATH is not required
set "UVICORN_CMD=%PYTHON_CMD% -m uvicorn"

REM Ensure uvicorn is installed for the selected interpreter
%PYTHON_CMD% -m uvicorn --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] uvicorn missing; installing into the selected Python environment...
    %PYTHON_CMD% -m pip install --upgrade pip >nul 2>&1
    %PYTHON_CMD% -m pip install "uvicorn[standard]" fastapi starlette >nul
)

REM Check for running processes
echo [Checking for running processes...]
tasklist /FI "WINDOWTITLE eq GoodQ API Server*" 2>NUL | find /I /N "python.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo.
    echo [!] WARNING: GoodQ API Server is already running!
    echo.
    set /p continue="Do you want to continue anyway? This may cause issues. (y/N): "
    if /i not "!continue!"=="y" (
        echo.
        echo Launch cancelled. Close existing processes first.
        pause
        exit /b 1
    )
)

tasklist /FI "WINDOWTITLE eq GoodQ Watchdog*" 2>NUL | find /I /N "python.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [!] WARNING: GoodQ Watchdog is already running!
)

echo.
echo ================================================================================
echo  Launch Menu
echo ================================================================================
echo.
echo  1. Launch Complete System (Recommended)
echo     - Unified API Server (all endpoints on port 30000)
echo     - Watchdog (auto-ingestion)
echo     - WSL vLLM Service
echo     - Web Interfaces (2 tabs)
echo.
echo  2. Launch API Server Only
echo     - For manual video processing or UI testing
echo.
echo  3. Launch Watchdog Only
echo     - Auto-ingestion of videos in import_inbox
echo.
echo  4. View System Status
echo     - Check what's running
echo.
echo  5. Stop All Services
echo     - Cleanly shutdown everything
echo.
echo  6. Exit
echo.
echo ================================================================================
set /p choice="Select option (1-6): "

if "%choice%"=="1" goto launch_complete
if "%choice%"=="2" goto launch_api
if "%choice%"=="3" goto launch_watchdog
if "%choice%"=="4" goto status
if "%choice%"=="5" goto stop_all
if "%choice%"=="6" goto end

echo [ERROR] Invalid choice
timeout /t 2 /nobreak >nul
goto end

:launch_complete
echo.
echo ================================================================================
echo  Launching Complete System
echo ================================================================================
echo.

echo [0/4] Ensuring required directories exist...
for %%d in ("L:\goodq4all\logs" "L:\goodq4all\data" "L:\goodq4all\data\processing" "L:\goodq4all\data\processed" "L:\goodq4all\data\databases\chroma") do (
    if not exist %%d (
        mkdir %%d >nul 2>&1
        echo       Created %%d
    )
)
echo       Directories ready.
echo.

echo [1/3] Starting Unified API Server...
start "GoodQ API Server" cmd /k "title GoodQ API Server && cd /d L:\goodq4all\api && %UVICORN_CMD% main:app --host 0.0.0.0 --port 30000 --reload"
echo       Waiting for server to initialize...
timeout /t 8 /nobreak >nul

echo [1a/3] Starting Processing Stats Service...
start "GoodQ Processing Stats" cmd /k "title GoodQ Processing Stats && cd /d L:\goodq4all\api && %PYTHON_CMD% processing_stats.py"
echo       Waiting for stats service...
timeout /t 3 /nobreak >nul

REM Auto-start vLLM services in WSL if available
echo [WSL] Checking WSL/vLLM status...
wsl --status >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    echo       WSL detected, attempting to start vLLM services...
    REM Preferred: start systemd services (passwordless via sudoers for set-and-forget)
    wsl sudo systemctl start vllm-llama1b >nul 2>&1
    wsl sudo systemctl start ollama >nul 2>&1
    REM Fallback: only start per-user scripts if systemd service is NOT active
    wsl sudo systemctl is-active --quiet vllm-llama1b
    if NOT "%ERRORLEVEL%"=="0" (
        echo       Systemd service not active; falling back to user scripts...
        wsl ~/vllm_server/scripts/start_llama1b.sh >nul 2>&1
        wsl ~/vllm_server/scripts/start_llama3b.sh >nul 2>&1
    )
) else (
    echo       WSL not detected; skipping vLLM auto-start
)

echo [2/3] Starting Watchdog (Auto-Ingestion)...
start "GoodQ Watchdog" cmd /k "title GoodQ Watchdog && cd /d L:\goodq4all && %PYTHON_CMD% scripts\watchdog_ingest.py"
echo       Waiting for watchdog to initialize...
timeout /t 3 /nobreak >nul

echo [3/3] Checking WSL vLLM Service Status...
echo       vLLM service managed by systemd (check WSL terminal for status)
timeout /t 1 /nobreak >nul

echo [4/4] Opening Web Interfaces...
start http://localhost:30000
timeout /t 1 /nobreak >nul
start http://localhost:30000/dashboard.html

echo.
echo ================================================================================
echo  System Launched Successfully!
echo ================================================================================
echo.
echo  🌐 Main Interface:      http://localhost:30000
echo  📊 Dashboard:           http://localhost:30000/dashboard.html
echo  🔌 API Endpoint:        http://localhost:30000/api
echo  💚 Health API:          http://localhost:30000/api/health
echo  📈 Processing API:      http://localhost:30000/api/processing/stats
echo  🤖 vLLM (WSL):          http://localhost:38005/v1
echo  🦙 Ollama:              http://localhost:31434/v1
echo.
echo  Active Services:
echo    ✓ Unified API Server  (GoodQ API Server window - port 30000)
echo    ✓ Watchdog            (GoodQ Watchdog window)
echo    ✓ vLLM Server         (WSL - systemd service)
echo    ✓ Web Interfaces      (2 Browser tabs)
echo.
echo  LLM Models Available:
echo    ? Llama-1B-Speed     (vLLM - port 38005)
echo    ? Phi4-Ollama        (Ollama - port 31434)
echo.
echo  Drop videos in: L:\goodq4all\import_inbox
echo  They will be auto-processed by the watchdog
echo.
echo  To Stop Services:
echo    - Run this launcher again and select option 5
echo    - Or close all "GoodQ" windows
echo    - WSL vLLM runs as systemd service (persists)
echo.
echo ================================================================================
echo.
pause
goto end

:launch_api
echo.
echo ================================================================================
echo  Launching API Server Only
echo ================================================================================
echo.
echo  Starting on http://localhost:30000...
echo  Press Ctrl+C to stop
echo.
echo ================================================================================
echo.

cd /d "L:\goodq4all\api"
%UVICORN_CMD% main:app --host 0.0.0.0 --port 30000 --reload

goto end

:launch_watchdog
echo.
echo ================================================================================
echo  Launching Watchdog (Auto-Ingestion)
echo ================================================================================
echo.
echo  Monitoring: L:\goodq4all\import_inbox
echo  Drop videos here for automatic processing
echo.
echo  Press Ctrl+C to stop the watchdog
echo.
echo ================================================================================
echo.

cd /d "L:\goodq4all"
%PYTHON_CMD% scripts\watchdog_ingest.py

goto end

:status
echo.
echo ================================================================================
echo  System Status Check
echo ================================================================================
echo.

echo Checking for running processes...
echo.

tasklist /FI "WINDOWTITLE eq GoodQ API Server*" 2>NUL | find /I /N "python.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [?] API Server:  RUNNING
) else (
    echo [!] API Server:  NOT RUNNING
)

tasklist /FI "WINDOWTITLE eq GoodQ Watchdog*" 2>NUL | find /I /N "python.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [?] Watchdog:    RUNNING
) else (
    echo [!] Watchdog:    NOT RUNNING
)

echo.
echo Checking API server connectivity...
curl -s http://localhost:30000/api/status >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    echo [?] API Server:  RESPONDING at http://localhost:30000
    echo.
    echo Current Status:
    curl -s http://localhost:30000/api/status
) else (
    echo [!] API Server:  NOT RESPONDING
)

echo.
echo.

if exist "L:\goodq4all\logs\progress.json" (
    echo [?] Active Processing Detected
    echo.
    type "L:\goodq4all\logs\progress.json"
) else (
    echo [!] No Active Processing
)

echo.
echo ================================================================================
pause
goto end

:stop_all
echo.
echo ================================================================================
echo  Stopping All GoodQ Services
echo ================================================================================
echo.

echo Stopping Windows processes...

REM Kill processes by window title
taskkill /FI "WINDOWTITLE eq GoodQ API Server*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq GoodQ Watchdog*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq GoodQ Health API*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq GoodQ Processing API*" /F >nul 2>&1

echo.
echo [?] All Windows GoodQ services stopped
echo.
echo NOTE: WSL vLLM service runs independently via systemd
echo       To stop vLLM, run: wsl sudo systemctl stop vllm-llama1b.service
echo.
echo ================================================================================
pause
goto end

:end
endlocal
