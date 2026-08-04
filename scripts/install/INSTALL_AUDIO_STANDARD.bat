@echo off
setlocal EnableExtensions
title GoodQ4All Audio Standard Provisioning

set "INSTALL_DIR=%~dp0..\.."
for %%I in ("%INSTALL_DIR%") do set "INSTALL_DIR=%%~fI"
set "PYTHON_EXE=%INSTALL_DIR%\runtime\python.exe"
set "BOOTSTRAP_SCRIPT=%INSTALL_DIR%\scripts\bootstrap_models.py"
set "DATA_DIR=%ProgramData%\GoodQ4All"
set "LOG_DIR=%DATA_DIR%\logs"

echo ============================================================
echo   GoodQ4All - Audio Standard Provisioning
echo ============================================================
echo.
echo This optional capability downloads CPU audio models on demand.
echo It does not modify existing scenes or canonical memory.
echo.

if not exist "%PYTHON_EXE%" (
  echo [BLOCKED] Installed GoodQ4All runtime was not found.
  goto :done
)
if not exist "%BOOTSTRAP_SCRIPT%" (
  echo [BLOCKED] Bootstrap script was not found.
  goto :done
)
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

"%PYTHON_EXE%" "%BOOTSTRAP_SCRIPT%" --profile audio_standard --report-path "%LOG_DIR%\audio_standard_report.json" --progress-path "%LOG_DIR%\audio_standard_progress.json"
if errorlevel 1 (
  echo [FAILED] Audio Standard provisioning did not complete.
  echo          See: %LOG_DIR%\audio_standard_report.json
) else (
  echo [READY] Audio Standard provisioning completed.
  echo         Receipt: %LOG_DIR%\audio_standard_report.json
)

:done
echo.
pause
