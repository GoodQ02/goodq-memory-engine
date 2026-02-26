@echo off
REM GoodQ4All - Start Qdrant Vector Database
REM This script starts Qdrant as a foreground process for testing
REM For production, use the Windows Service (install via INSTALL_QDRANT_SERVICE.bat)
setlocal EnableExtensions
for %%I in ("%~dp0..\\..") do set "REPO_ROOT=%%~fI"
for %%D in ("%REPO_ROOT%") do set "REPO_DRIVE=%%~dD"
if "%GOODQ_DATA_ROOT%"=="" set "GOODQ_DATA_ROOT=%REPO_DRIVE%\_DATA"
set "QDRANT_STORAGE_PATH=%GOODQ_DATA_ROOT%\qdrant_storage"
if not exist "%QDRANT_STORAGE_PATH%" mkdir "%QDRANT_STORAGE_PATH%"
set "QDRANT__STORAGE__STORAGE_PATH=%QDRANT_STORAGE_PATH%"

echo.
echo ========================================
echo   GoodQ4All - Qdrant Vector Database
echo ========================================
echo.
echo Starting Qdrant on http://localhost:6333...
echo Data directory: %QDRANT_STORAGE_PATH%
echo.
echo Press Ctrl+C to stop Qdrant
echo.

cd /d "%REPO_ROOT%\vendor\qdrant"

REM Start Qdrant with custom config
qdrant.exe --config-path config.yaml

pause
