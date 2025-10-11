@echo off
REM GoodQ Watchdog Live Monitor
REM Continuously updates watchdog status

title GoodQ Watchdog Monitor - Live Updates

:loop
cls

REM Activate environment and run Python status script
call conda activate goodq_zenml 2>nul
python L:\goodq4all\scripts\check_watchdog_status.py

echo.
echo   Refreshing in 5 seconds... (Ctrl+C to stop)
echo.

timeout /t 5 /nobreak >nul
goto loop
