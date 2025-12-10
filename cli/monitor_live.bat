@echo off
:: Live Ingestion Monitor - Shows real-time progress
setlocal enabledelayedexpansion

:loop
cls
echo ================================================================================
echo   GoodQ4All - LIVE INGESTION MONITOR
echo ================================================================================
echo.
echo Time: %date% %time%
echo.

:: Find most recent log
for /f "delims=" %%a in ('dir /b /od L:\goodq4all\logs\*.log 2^>nul') do set "LATEST_LOG=%%a"

if defined LATEST_LOG (
    echo Monitoring: L:\goodq4all\logs\!LATEST_LOG!
    echo.
    echo === LAST 40 LINES ===
    powershell -Command "Get-Content L:\goodq4all\logs\!LATEST_LOG! -Tail 40"
) else (
    echo No log files found in L:\goodq4all\logs\
)

echo.
echo ================================================================================
echo Press Ctrl+C to stop monitoring, or wait 10 seconds for refresh...
echo ================================================================================
timeout /t 10 /nobreak >nul
goto loop
