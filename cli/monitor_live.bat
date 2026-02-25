@echo off
:: Live Ingestion Monitor - Shows real-time progress
setlocal enabledelayedexpansion
set "REPO_ROOT=%~dp0.."
if defined GOODQ_LOG_DIR (
    set "LOG_DIR=%GOODQ_LOG_DIR%"
) else (
    set "LOG_DIR=%REPO_ROOT%\logs"
)

:loop
cls
echo ================================================================================
echo   GoodQ4All - LIVE INGESTION MONITOR
echo ================================================================================
echo.
echo Time: %date% %time%
echo.

:: Find most recent log
for /f "delims=" %%a in ('dir /b /od "%LOG_DIR%\*.log" 2^>nul') do set "LATEST_LOG=%%a"

if defined LATEST_LOG (
    echo Monitoring: %LOG_DIR%\!LATEST_LOG!
    echo.
    echo === LAST 40 LINES ===
    powershell -Command "Get-Content '%LOG_DIR%\!LATEST_LOG!' -Tail 40"
) else (
    echo No log files found in %LOG_DIR%\
)

echo.
echo ================================================================================
echo Press Ctrl+C to stop monitoring, or wait 10 seconds for refresh...
echo ================================================================================
timeout /t 10 /nobreak >nul
goto loop
