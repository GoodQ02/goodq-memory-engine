@echo off
REM GoodQ Watchdog Launcher
REM Monitors import_inbox and automatically processes new files

title GoodQ Watchdog - File Ingestion Monitor

echo.
echo ╔═══════════════════════════════════════════════════════════════╗
echo ║              GoodQ Watchdog - Starting...                     ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.

REM Activate conda environment
call conda activate goodq_zenml
if errorlevel 1 (
    echo [ERROR] Failed to activate goodq_zenml environment
    pause
    exit /b 1
)

echo [WATCHDOG] Environment activated: goodq_zenml
echo [WATCHDOG] Monitoring: L:\GoodQ_4_All\import_inbox
echo [WATCHDOG] Log file: L:\GoodQ_4_All\logs\watchdog.log
echo.
echo Drop files into import_inbox to process them automatically!
echo Press Ctrl+C to stop the watchdog
echo.
echo ═══════════════════════════════════════════════════════════════
echo.

REM Run watchdog
python L:\GoodQ_4_All\scripts\watchdog_ingest.py

pause
