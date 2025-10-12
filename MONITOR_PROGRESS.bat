@echo off
REM ============================================================================
REM GoodQ Mission Progress Monitor
REM Real-time tracking of ingestion operations
REM ============================================================================

title GoodQ Mission Progress Monitor

echo.
echo ╔═══════════════════════════════════════════════════════════════╗
echo ║              GoodQ Mission Progress Monitor                   ║
echo ║           Live tracking of ingestion operations               ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.

cd /d L:\goodq4all

REM Activate base environment and run monitor
conda run -n goodq_zenml python scripts\monitor_ingestion_progress.py --refresh 5

pause
