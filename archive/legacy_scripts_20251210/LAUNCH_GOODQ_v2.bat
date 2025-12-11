@echo off
REM GoodQ4All Launcher v2 - Updated 2025-12-09
REM Uses direct_ingestion pipeline with watchdog monitoring

echo ================================================
echo   GoodQ4All Multimodal Ingestion System
echo   Phase 10+ Architecture
echo ================================================
echo.

REM Activate goodq_core environment
call conda activate goodq_core
if errorlevel 1 (
    echo ERROR: Failed to activate goodq_core environment
    pause
    exit /b 1
)

REM Set Python path
set PYTHONPATH=L:\goodq4all

REM Launch watchdog
echo Starting GoodQ4All watchdog...
python -m cli.watchdog

pause
