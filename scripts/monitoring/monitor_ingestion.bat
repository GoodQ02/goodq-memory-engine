@echo off
REM GoodQ4All - Live Ingestion Monitor (Non-Intrusive)
REM Run this to check on active ingestion without starting a new one

setlocal enabledelayedexpansion
call "%~dp0..\\_lib\\interpreter_bindings.bat"
for %%I in ("%~dp0..\\..") do set "REPO_ROOT=%%~fI"

echo.
echo ===============================================================================
echo   GoodQ4All - Live Ingestion Monitor
echo ===============================================================================
echo.

pushd "%REPO_ROOT%" >nul
set "PYTHONPATH=%CD%"

REM Run monitor
"%CONDA_EXE%" run -n %GOODQ_CONDA_ENV% python -m cli.monitor_ingestion
popd >nul

echo.
echo ===============================================================================
echo Press any key to exit...
pause >nul
