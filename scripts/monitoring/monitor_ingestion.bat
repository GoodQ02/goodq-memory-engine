@echo off
REM GoodQ4All - Live Ingestion Monitor (Non-Intrusive)
REM Run this to check on active ingestion without starting a new one

setlocal enabledelayedexpansion
call "%~dp0..\\_lib\\interpreter_bindings.bat"

echo.
echo ===============================================================================
echo   GoodQ4All - Live Ingestion Monitor
echo ===============================================================================
echo.

REM Set Python path
set PYTHONPATH=L:\goodq4all

REM Run monitor
"%CONDA_EXE%" run -n goodq_core python L:\goodq4all\cli\monitor_ingestion.py

echo.
echo ===============================================================================
echo Press any key to exit...
pause >nul
