@echo off
REM GoodQ Watchdog Status Checker
REM Quick dashboard to see watchdog activity

title GoodQ Watchdog Status

powershell -ExecutionPolicy Bypass -File "L:\zenml_project\scripts\watchdog_status.ps1"

pause
