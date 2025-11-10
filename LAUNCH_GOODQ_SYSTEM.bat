@echo off
REM ================================================================================
REM  GoodQ4All - Complete System Launcher
REM  Production-Ready Multi-Modal Memory & Knowledge Interface
REM ================================================================================

setlocal enabledelayedexpansion

echo.
echo ================================================================================
echo   _____                 _  _____ _  _    ___   _ _ 
echo  ^|  __ \               ^| ^|^|  _  ^| ^|^| ^|  / _ \ ^| ^| ^|
echo  ^| ^|  \/ ___   ___   __^| ^|^| ^|/' ^|_^|^|_^| / /_\ \^| ^| ^|
echo  ^| ^| __ / _ \ / _ \ / _` ^|^|  /^| ^| _^| ^|^|  _  ^|^| ^| ^|
echo  ^| ^|_\ \ (_) ^| (_) ^| (_^| ^|\ ^|_/ /^|_^|^|_^|^| ^| ^| ^|^| ^| ^|
echo   \____/\___/ \___/ \__,_^| \___/  \___/\_^| ^|_/\_\_^|
echo.
echo  Personal Memory & Knowledge Assistant
echo  Version 2.0 - Production Ready
echo ================================================================================
echo.

REM Check if running in correct directory
if not exist "L:\goodq4all\api_server.py" (
    echo [ERROR] Please run this from L:\goodq4all directory
    pause
    exit /b 1
)

echo [System Check] Running diagnostics...
echo.

REM Run quick diagnostics
conda run --no-capture-output -n goodq_zenml python diagnose_system.py

echo.
echo ================================================================================
echo  Launch Options
echo ================================================================================
echo.
echo  1. Launch Complete System (API Server + UI + Watchdog)
echo  2. Launch API Server Only
echo  3. Launch Watchdog Only (Auto-Ingestion)
echo  4. View System Status
echo  5. Monitor Progress in Real-Time
echo  6. Run Full Diagnostics
echo  7. Exit
echo.
set /p choice="Select option (1-7): "

if "%choice%"=="1" goto launch_full
if "%choice%"=="2" goto launch_api
if "%choice%"=="3" goto launch_watchdog
if "%choice%"=="4" goto view_status
if "%choice%"=="5" goto monitor_progress
if "%choice%"=="6" goto run_diagnostics
if "%choice%"=="7" goto end

echo [ERROR] Invalid choice
pause
goto end

:launch_full
echo.
echo ================================================================================
echo  Launching Complete System
echo ================================================================================
echo.

echo [1/3] Starting API Server...
start "GoodQ API Server" cmd /k "title GoodQ API Server && conda run --no-capture-output -n goodq_zenml python api_server.py"
timeout /t 5 /nobreak >nul

echo [2/3] Starting Watchdog (Auto-Ingestion)...
start "GoodQ Watchdog" cmd /k "title GoodQ Watchdog && conda run --no-capture-output -n goodq_zenml python scripts/watchdog_ingest.py"
timeout /t 2 /nobreak >nul

echo [3/3] Opening Web Interface...
start http://localhost:3000

echo.
echo ================================================================================
echo  System Launched Successfully!
echo ================================================================================
echo.
echo  Web Interface: http://localhost:3000
echo  API Endpoint:  http://localhost:3000/api
echo  Progress API:  http://localhost:3000/api/progress
echo.
echo  Services Running:
echo    - API Server (Port 3000)
echo    - Watchdog (Auto-Ingestion)
echo    - Web Interface (Browser)
echo.
echo  To monitor progress:
echo    - Open browser to http://localhost:3000
echo    - Or run: python monitor_progress.py
echo.
echo  To stop services:
echo    - Close the API Server window
echo    - Close the Watchdog window
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
echo  Starting server on http://localhost:3000...
echo.

conda run --no-capture-output -n goodq_zenml python api_server.py

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

conda run --no-capture-output -n goodq_zenml python scripts/watchdog_ingest.py

goto end

:view_status
echo.
echo ================================================================================
echo  Current System Status
echo ================================================================================
echo.

REM Check if API server is running
curl -s http://localhost:3000/api/status >nul 2>&1
if errorlevel 1 (
    echo [!] API Server: NOT RUNNING
    echo     Start with: conda run -n goodq_zenml python api_server.py
) else (
    echo [✓] API Server: RUNNING on http://localhost:3000
    echo.
    echo Fetching status...
    curl -s http://localhost:3000/api/status
)

echo.
echo.

REM Check progress
if exist "L:\goodq4all\logs\progress.json" (
    echo [✓] Active Processing Detected
    echo.
    echo Progress Details:
    type "L:\goodq4all\logs\progress.json"
) else (
    echo [!] No Active Processing
)

echo.
echo ================================================================================
pause
goto end

:monitor_progress
echo.
echo ================================================================================
echo  Real-Time Progress Monitor
echo ================================================================================
echo.
echo  Starting live progress monitor...
echo  Press Ctrl+C to stop
echo.
echo ================================================================================
echo.

conda run --no-capture-output -n goodq_zenml python monitor_progress.py

goto end

:run_diagnostics
echo.
echo ================================================================================
echo  Running Full System Diagnostics
echo ================================================================================
echo.

conda run --no-capture-output -n goodq_zenml python diagnose_system.py

echo.
echo ================================================================================
pause
goto end

:end
echo.
echo Thank you for using GoodQ4All!
echo.
endlocal
