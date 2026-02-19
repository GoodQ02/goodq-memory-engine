@echo off
REM GoodQ4All - Install Qdrant as Windows Service
REM This requires Administrator privileges
setlocal EnableExtensions
for %%I in ("%~dp0..\\..") do set "REPO_ROOT=%%~fI"
for %%D in ("%REPO_ROOT%") do set "REPO_DRIVE=%%~dD"
if "%GOODQ_DATA_ROOT%"=="" set "GOODQ_DATA_ROOT=%REPO_DRIVE%\_DATA"
set "NSSM_EXE=%REPO_ROOT%\vendor\nssm.exe"
set "NSSM_ZIP=%REPO_ROOT%\vendor\nssm.zip"
set "NSSM_TMP=%REPO_ROOT%\vendor\nssm_temp"
set "QDRANT_EXE=%REPO_ROOT%\vendor\qdrant\qdrant.exe"
set "QDRANT_CFG=%REPO_ROOT%\vendor\qdrant\config.yaml"
set "QDRANT_APPDIR=%REPO_ROOT%\vendor\qdrant"
set "QDRANT_STDOUT=%REPO_ROOT%\logs\qdrant_stdout.log"
set "QDRANT_STDERR=%REPO_ROOT%\logs\qdrant_stderr.log"

echo.
echo ========================================
echo   Install Qdrant as Windows Service
echo ========================================
echo.
echo This will install Qdrant to run automatically on system startup.
echo You need Administrator privileges to continue.
echo.
pause

REM Check for admin rights
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo [ERROR] This script requires Administrator privileges!
    echo Please right-click and select "Run as Administrator"
    echo.
    pause
    exit /b 1
)

echo.
echo [1/3] Creating NSSM service manager...

REM Download NSSM (Non-Sucking Service Manager) if not present
if not exist "%NSSM_EXE%" (
    echo Downloading NSSM...
    powershell -Command "Invoke-WebRequest -Uri 'https://nssm.cc/ci/nssm-2.24-101-g897c7ad.zip' -OutFile '%NSSM_ZIP%'"
    powershell -Command "Expand-Archive -Path '%NSSM_ZIP%' -DestinationPath '%NSSM_TMP%' -Force"
    copy "%NSSM_TMP%\nssm-2.24-101-g897c7ad\win64\nssm.exe" "%NSSM_EXE%"
    rmdir /s /q "%NSSM_TMP%"
    del "%NSSM_ZIP%"
)

echo [OK] NSSM ready
echo.
echo [2/3] Installing Qdrant service...

REM Install service
"%NSSM_EXE%" install GoodQ_Qdrant "%QDRANT_EXE%" "--config-path" "%QDRANT_CFG%"

REM Configure service
"%NSSM_EXE%" set GoodQ_Qdrant DisplayName "GoodQ4All - Qdrant Vector Database"
"%NSSM_EXE%" set GoodQ_Qdrant Description "Local vector database for GoodQ4All multimodal search"
"%NSSM_EXE%" set GoodQ_Qdrant Start SERVICE_AUTO_START
"%NSSM_EXE%" set GoodQ_Qdrant AppDirectory "%QDRANT_APPDIR%"
"%NSSM_EXE%" set GoodQ_Qdrant AppStdout "%QDRANT_STDOUT%"
"%NSSM_EXE%" set GoodQ_Qdrant AppStderr "%QDRANT_STDERR%"

echo [OK] Service installed
echo.
echo [3/3] Starting Qdrant service...

net start GoodQ_Qdrant

echo.
echo ========================================
echo   Installation Complete!
echo ========================================
echo.
echo Qdrant is now running as a Windows Service
echo - Service Name: GoodQ_Qdrant
echo - HTTP API: http://localhost:6333
echo - gRPC API: http://localhost:6334
echo - Data: %GOODQ_DATA_ROOT%\qdrant_storage
echo - Logs: %REPO_ROOT%\logs\qdrant_*.log
echo.
echo The service will start automatically on system boot.
echo.
echo To manage the service:
echo   - Start:   net start GoodQ_Qdrant
echo   - Stop:    net stop GoodQ_Qdrant
echo   - Remove:  %NSSM_EXE% remove GoodQ_Qdrant confirm
echo.
pause
