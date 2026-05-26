@echo off
REM GoodQ4All - Start Qdrant Vector Database
REM This script starts Qdrant as a foreground process for testing
REM For production, use the Windows Service (install via INSTALL_QDRANT_SERVICE.bat)
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
if not exist "%QDRANT_STORAGE_PATH%" mkdir "%QDRANT_STORAGE_PATH%"
set "QDRANT__STORAGE__STORAGE_PATH=%QDRANT_STORAGE_PATH%"
if not exist "%REPO_ROOT%\vendor\qdrant\qdrant.exe" (
  echo [ERROR] Missing Qdrant binary at "%REPO_ROOT%\vendor\qdrant\qdrant.exe"
  echo [INFO] Preferred fix: run scripts\qdrant\INSTALL_QDRANT_SERVICE.bat
  exit /b 1
)

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
