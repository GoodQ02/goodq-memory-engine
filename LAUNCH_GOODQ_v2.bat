@echo off
REM ================================================================================
REM  GoodQ4All - Modern System Launcher (v2.0)
REM  Updated: 2025-12-09
REM  Architecture: Direct Ingestion Pipeline (ZenML removed)
REM ================================================================================

setlocal enabledelayedexpansion

title GoodQ4All Launcher v2.0
color 0B

echo.
echo ================================================================================
echo   GoodQ4All - Personal Memory Engine
echo   Version 2.0 - Production Ready
echo ================================================================================
echo.

REM Navigate to project root
cd /d "L:\goodq4all"

REM Set Python path
set "PYTHONPATH=L:\goodq4all"
set "PYTHON_CMD=python"

REM Check for conda environment (goodq_core recommended)
where conda >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    echo [INFO] Conda detected - using goodq_core environment
    call conda activate goodq_core
    set "PYTHON_CMD=python"
) else (
    echo [INFO] Using system Python
)

REM Verify Python is available
%PYTHON_CMD% --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Please install Python or activate conda environment
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo  Launch Options
echo ================================================================================
echo.
echo  1. Launch Complete System (API + Watchdog + WSL)
echo  2. Launch API Server Only
echo  3. Launch Watchdog Only (Auto-Ingestion)
echo  4. Run Single Video Ingestion (Test)
echo  5. Check System Status
echo  6. Stop All Services
echo  7. Exit
echo.
echo ================================================================================
set /p choice="Select option (1-7): "

if "%choice%"=="1" goto launch_complete
if "%choice%"=="2" goto launch_api
if "%choice%"=="3" goto launch_watchdog
if "%choice%"=="4" goto test_ingestion
if "%choice%"=="5" goto status
if "%choice%"=="6" goto stop_all
if "%choice%"=="7" goto end

echo [ERROR] Invalid choice
timeout /t 2 /nobreak >nul
goto end

:launch_complete
echo.
echo ================================================================================
echo  Launching Complete System
echo ================================================================================
echo.

echo [1/4] Ensuring directories exist...
for %%d in (logs data\processing data\processed import_inbox) do (
    if not exist "%%d" mkdir "%%d" >nul 2>&1
)
echo       ✓ Directories ready

echo [2/4] Starting API Server (port 8000)...
start "GoodQ API Server" cmd /k "title GoodQ API && cd /d L:\goodq4all && set PYTHONPATH=L:\goodq4all && %PYTHON_CMD% -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 5 /nobreak >nul

echo [3/4] Starting Watchdog (Auto-Ingestion)...
start "GoodQ Watchdog" cmd /k "title GoodQ Watchdog && cd /d L:\goodq4all && set PYTHONPATH=L:\goodq4all && %PYTHON_CMD% -m cli.watchdog"
timeout /t 3 /nobreak >nul

echo [4/4] Starting WSL vLLM (if available)...
wsl --status >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    wsl sudo systemctl start vllm-llama1b >nul 2>&1
    echo       ✓ WSL vLLM started
) else (
    echo       ⚠ WSL not available
)

echo.
echo ================================================================================
echo  System Launched Successfully!
echo ================================================================================
echo.
echo  🌐 API Server:          http://localhost:8000
echo  📊 API Docs:            http://localhost:8000/docs
echo  📁 Drop videos in:      L:\goodq4all\import_inbox
echo.
echo  To stop: Run this script and select option 6
echo.
echo ================================================================================
pause
goto end

:launch_api
echo.
echo ================================================================================
echo  Launching API Server Only
echo ================================================================================
echo.

cd /d "L:\goodq4all"
set PYTHONPATH=L:\goodq4all
%PYTHON_CMD% -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

goto end

:launch_watchdog
echo.
echo ================================================================================
echo  Launching Watchdog (Auto-Ingestion)
echo ================================================================================
echo.
echo  Monitoring: L:\goodq4all\import_inbox
echo  Press Ctrl+C to stop
echo.

cd /d "L:\goodq4all"
set PYTHONPATH=L:\goodq4all
%PYTHON_CMD% -m cli.watchdog

goto end

:test_ingestion
echo.
echo ================================================================================
echo  Test Single Video Ingestion
echo ================================================================================
echo.

set /p video_path="Enter full path to video file: "
if not exist "%video_path%" (
    echo [ERROR] File not found: %video_path%
    pause
    goto end
)

echo.
echo [INFO] Running ingestion on: %video_path%
echo.

cd /d "L:\goodq4all"
set PYTHONPATH=L:\goodq4all
%PYTHON_CMD% -c "from cli.run_ingestion import main; main('%video_path%')"

echo.
echo [INFO] Ingestion complete
pause
goto end

:status
echo.
echo ================================================================================
echo  System Status
echo ================================================================================
echo.

tasklist /FI "WINDOWTITLE eq GoodQ API*" 2>NUL | find /I "python" >NUL
if "%ERRORLEVEL%"=="0" (
    echo ✓ API Server:  RUNNING
) else (
    echo ✗ API Server:  STOPPED
)

tasklist /FI "WINDOWTITLE eq GoodQ Watchdog*" 2>NUL | find /I "python" >NUL
if "%ERRORLEVEL%"=="0" (
    echo ✓ Watchdog:    RUNNING
) else (
    echo ✗ Watchdog:    STOPPED
)

echo.
curl -s http://localhost:8000/api/system/status >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    echo ✓ API responding at http://localhost:8000
) else (
    echo ✗ API not responding
)

echo.
echo ================================================================================
pause
goto end

:stop_all
echo.
echo ================================================================================
echo  Stopping All Services
echo ================================================================================
echo.

taskkill /FI "WINDOWTITLE eq GoodQ*" /F >nul 2>&1
echo ✓ All GoodQ services stopped

echo.
echo ================================================================================
pause
goto end

:end
endlocal
