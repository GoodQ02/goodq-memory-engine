@echo off
REM GoodQ4All - Install Qdrant as Windows Service
REM This requires Administrator privileges

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
if not exist "L:\goodq4all\vendor\nssm.exe" (
    echo Downloading NSSM...
    powershell -Command "Invoke-WebRequest -Uri 'https://nssm.cc/ci/nssm-2.24-101-g897c7ad.zip' -OutFile 'L:\goodq4all\vendor\nssm.zip'"
    powershell -Command "Expand-Archive -Path 'L:\goodq4all\vendor\nssm.zip' -DestinationPath 'L:\goodq4all\vendor\nssm_temp' -Force"
    copy "L:\goodq4all\vendor\nssm_temp\nssm-2.24-101-g897c7ad\win64\nssm.exe" "L:\goodq4all\vendor\nssm.exe"
    rmdir /s /q "L:\goodq4all\vendor\nssm_temp"
    del "L:\goodq4all\vendor\nssm.zip"
)

echo [OK] NSSM ready
echo.
echo [2/3] Installing Qdrant service...

REM Install service
L:\goodq4all\vendor\nssm.exe install GoodQ_Qdrant "L:\goodq4all\vendor\qdrant\qdrant.exe" "--config-path" "L:\goodq4all\vendor\qdrant\config.yaml"

REM Configure service
L:\goodq4all\vendor\nssm.exe set GoodQ_Qdrant DisplayName "GoodQ4All - Qdrant Vector Database"
L:\goodq4all\vendor\nssm.exe set GoodQ_Qdrant Description "Local vector database for GoodQ4All multimodal search"
L:\goodq4all\vendor\nssm.exe set GoodQ_Qdrant Start SERVICE_AUTO_START
L:\goodq4all\vendor\nssm.exe set GoodQ_Qdrant AppDirectory "L:\goodq4all\vendor\qdrant"
L:\goodq4all\vendor\nssm.exe set GoodQ_Qdrant AppStdout "L:\goodq4all\logs\qdrant_stdout.log"
L:\goodq4all\vendor\nssm.exe set GoodQ_Qdrant AppStderr "L:\goodq4all\logs\qdrant_stderr.log"

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
echo - Data: L:\_DATA\qdrant_storage
echo - Logs: L:\goodq4all\logs\qdrant_*.log
echo.
echo The service will start automatically on system boot.
echo.
echo To manage the service:
echo   - Start:   net start GoodQ_Qdrant
echo   - Stop:    net stop GoodQ_Qdrant
echo   - Remove:  L:\goodq4all\vendor\nssm.exe remove GoodQ_Qdrant confirm
echo.
pause
