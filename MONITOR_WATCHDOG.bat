@echo off
REM GoodQ Watchdog Live Monitor
REM Continuously updates watchdog status

title GoodQ Watchdog Monitor - Live Updates

powershell -ExecutionPolicy Bypass -File "L:\GoodQ_4_All\scripts\watchdog_status.ps1" -Follow -RefreshSeconds 5
