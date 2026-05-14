@echo off
REM GoodQ4All - Uninstall Qdrant Windows Service
REM This requires Administrator privileges
setlocal EnableExtensions
for %%I in ("%~dp0..\\..") do set "REPO_ROOT=%%~fI"
for %%D in ("%REPO_ROOT%") do set "REPO_DRIVE=%%~dD"
if "%GOODQ_DATA_ROOT%"=="" set "GOODQ_DATA_ROOT=%REPO_DRIVE%\_DATA"
set "NSSM_EXE=%REPO_ROOT%\vendor\nssm.exe"
set "QDRANT_DIR=%REPO_ROOT%\vendor\qdrant"

echo.
echo ========================================
echo   Uninstall Qdrant Windows Service
echo ========================================
echo.

REM Check for admin rights
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] This script requires Administrator privileges!
    echo Please right-click and select "Run as Administrator"
    echo.
    pause
    exit /b 1
)

echo Stopping Qdrant service...
net stop GoodQ_Qdrant

echo.
echo Removing Qdrant service...
"%NSSM_EXE%" remove GoodQ_Qdrant confirm

echo.
echo [OK] Qdrant service uninstalled
echo.
echo Note: Qdrant data remains at the resolved qdrant_storage path from canonical config.
echo To completely remove Qdrant, delete the service helper files and the resolved qdrant_storage directory:
echo   - %QDRANT_DIR%
echo   - resolved qdrant_storage path shown by LAUNCH_GOODQ.ps1
echo.
pause
