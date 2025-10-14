@echo off
REM GoodQ Live Progress Monitor
REM Real-time view of ingestion progress

title GoodQ Live Progress Monitor

echo.
echo ╔═══════════════════════════════════════════════════════════════╗
echo ║     🎬 GoodQ Live Progress Monitor                            ║
echo ║     Real-time ingestion tracking                              ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.
echo Starting live monitor... (Press Ctrl+C to stop)
echo.

REM Activate environment and run monitor
call conda activate goodq_zenml 2>nul
if errorlevel 1 (
    echo [ERROR] Failed to activate goodq_zenml environment
    pause
    exit /b 1
)

python L:\goodq4all\scripts\live_progress.py

pause
