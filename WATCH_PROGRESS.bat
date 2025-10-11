@echo off
REM GoodQ Progress Monitor Launcher
REM Watch ingestion progress in real-time

title GoodQ Progress Monitor

echo.
echo ╔═══════════════════════════════════════════════════════════════╗
echo ║              GoodQ Progress Monitor Starting...               ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.

REM Activate environment and run monitor
call conda activate goodq_zenml
python L:\goodq4all\scripts\watch_progress.py

pause
