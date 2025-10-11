@echo off
REM GoodQ Watchdog Status Check
REM Shows detailed status of file processing

echo ============================================================
echo   GoodQ Watchdog Status
echo ============================================================
echo.

REM Activate environment
call conda activate goodq_zenml 2>nul

REM Run status script
python L:\goodq4all\scripts\check_watchdog_status.py

pause
