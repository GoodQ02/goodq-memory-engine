@echo off
setlocal
call "%~dp0..\scripts\_lib\interpreter_bindings.bat"
set "CONDA_TARGET_FLAG=-n"
set "CONDA_TARGET_VALUE=%GOODQ_CONDA_ENV%"
if exist "%GOODQ_CONDA_ENV%\python.exe" (
    set "CONDA_TARGET_FLAG=-p"
)

echo.
echo ============================================================================
echo                         SAMPLE FILE INGESTION TEST
echo ============================================================================
echo.

pushd "%~dp0.."
echo [INFO] Starting ingestion...
echo [INFO] Input: samples\ingestion\sample.mp4
echo [INFO] Workspace: logs\test_workspace
echo [INFO] Output: logs\test_results.json
echo [INFO] Env: %GOODQ_CONDA_ENV%
echo.

"%CONDA_EXE%" run %CONDA_TARGET_FLAG% "%CONDA_TARGET_VALUE%" python cli\run_ingestion.py --input-dir samples/ingestion --workspace logs\test_workspace --output logs\test_results.json --verbose --force
set "GOODQ_TEST_EXIT=%ERRORLEVEL%"

echo.
echo ============================================================================
echo                         INGESTION TEST COMPLETE
echo ============================================================================
echo.

popd
exit /b %GOODQ_TEST_EXIT%
