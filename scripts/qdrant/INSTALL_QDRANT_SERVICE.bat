@echo off
REM GoodQ4All - Install Qdrant as Windows Service
REM This requires Administrator privileges
setlocal EnableExtensions
for %%I in ("%~dp0..\\..") do set "REPO_ROOT=%%~fI"
call "%REPO_ROOT%\scripts\_lib\interpreter_bindings.bat"
pushd "%REPO_ROOT%"
for /f "usebackq tokens=1,* delims==" %%A in (`"%CONDA_EXE%" run -n "%GOODQ_CONDA_ENV%" --no-capture-output python -c "from steps.common.config_loader import load_configs, get_runtime_paths; cfg=load_configs({}); paths=get_runtime_paths(cfg, 'qdrant_storage'); print('QDRANT_STORAGE_PATH=' + paths['qdrant_storage']); print('GOODQ_LOG_DIR=' + paths['log_dir'])"`) do (
  if not "%%A"=="" set "%%A=%%B"
)
popd
if "%QDRANT_STORAGE_PATH%"=="" (
  echo [ERROR] Failed to resolve Qdrant storage path from canonical config.
  exit /b 1
)
if "%GOODQ_LOG_DIR%"=="" (
  echo [ERROR] Failed to resolve Qdrant log directory from canonical config.
  exit /b 1
)
set "NSSM_EXE=%REPO_ROOT%\vendor\nssm.exe"
set "NSSM_ZIP=%REPO_ROOT%\vendor\nssm.zip"
set "NSSM_TMP=%REPO_ROOT%\vendor\nssm_temp"
set "QDRANT_EXE=%REPO_ROOT%\vendor\qdrant\qdrant.exe"
set "QDRANT_CFG=%REPO_ROOT%\vendor\qdrant\config.yaml"
set "QDRANT_APPDIR=%REPO_ROOT%\vendor\qdrant"
set "QDRANT_STDOUT=%GOODQ_LOG_DIR%\qdrant_stdout.log"
set "QDRANT_STDERR=%GOODQ_LOG_DIR%\qdrant_stderr.log"

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

if not exist "%QDRANT_STORAGE_PATH%" mkdir "%QDRANT_STORAGE_PATH%"
if not exist "%GOODQ_LOG_DIR%" mkdir "%GOODQ_LOG_DIR%"

REM Install service
"%NSSM_EXE%" install GoodQ_Qdrant "%QDRANT_EXE%" "--config-path" "%QDRANT_CFG%"

REM Configure service
"%NSSM_EXE%" set GoodQ_Qdrant DisplayName "GoodQ4All - Qdrant Vector Database"
"%NSSM_EXE%" set GoodQ_Qdrant Description "Local vector database for GoodQ4All multimodal search"
"%NSSM_EXE%" set GoodQ_Qdrant Start SERVICE_AUTO_START
"%NSSM_EXE%" set GoodQ_Qdrant AppDirectory "%QDRANT_APPDIR%"
"%NSSM_EXE%" set GoodQ_Qdrant AppStdout "%QDRANT_STDOUT%"
"%NSSM_EXE%" set GoodQ_Qdrant AppStderr "%QDRANT_STDERR%"
"%NSSM_EXE%" set GoodQ_Qdrant AppEnvironmentExtra "QDRANT__STORAGE__STORAGE_PATH=%QDRANT_STORAGE_PATH%"

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
echo - Data: %QDRANT_STORAGE_PATH%
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
