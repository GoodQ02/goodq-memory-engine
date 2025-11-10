@echo off
title GoodQ4All - Production System Launcher
color 0A

echo ================================================================================
echo   GoodQ4All Production System
echo ================================================================================
echo.

cd /d "%~dp0"

echo [1/3] Activating conda environment...
call conda activate goodq_zenml
if errorlevel 1 (
    echo ERROR: Failed to activate conda environment 'goodq_zenml'
    echo Please run: conda env create -f environment.yml
    pause
    exit /b 1
)

echo [2/3] Starting API server...
start "GoodQ API Server" /MIN cmd /c "conda activate goodq_zenml && python api_server.py"
timeout /t 3 /nobreak >nul

echo [3/3] Starting watchdog monitor...
start "GoodQ Watchdog" /MIN cmd /c "conda activate goodq_zenml && python scripts\watchdog_ingest.py"
timeout /t 2 /nobreak >nul

echo.
echo ================================================================================
echo   System Started Successfully!
echo ================================================================================
echo   Web UI:      http://localhost:3000
echo   API Server:  http://localhost:3000/api
echo   Watchdog:    Monitoring import_inbox
echo ================================================================================
echo.
echo Opening web interface...
timeout /t 2 /nobreak >nul
start http://localhost:3000

echo.
echo System is running. Close this window to stop all services.
echo Press any key to open process manager...
pause >nul
python process_manager.py
