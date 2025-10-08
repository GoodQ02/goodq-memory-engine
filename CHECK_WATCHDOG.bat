@echo off
REM GoodQ Watchdog Status Checker
REM Quick dashboard to see watchdog activity

title GoodQ Watchdog Status

powershell -ExecutionPolicy Bypass -File "L:\GoodQ_4_All\scripts\watchdog_status.ps1"

pause
