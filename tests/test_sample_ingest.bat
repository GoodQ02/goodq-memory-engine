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
if "%GOODQ_SAMPLE_INPUT_DIR%"=="" (
    echo [SKIP] Set GOODQ_SAMPLE_INPUT_DIR to a folder containing one small owned media fixture.
    echo [SKIP] No public sample.mp4 fixture is shipped with this repo.
    popd
    exit /b 0
)

if not exist "%GOODQ_SAMPLE_INPUT_DIR%\" (
    echo [FAIL] GOODQ_SAMPLE_INPUT_DIR does not exist: %GOODQ_SAMPLE_INPUT_DIR%
    popd
    exit /b 2
)

echo [INFO] Starting ingestion...
echo [INFO] Input: %GOODQ_SAMPLE_INPUT_DIR%
echo [INFO] Workspace: logs\test_workspace
echo [INFO] Output: logs\test_results.json
echo [INFO] Env: %GOODQ_CONDA_ENV%
echo.

"%CONDA_EXE%" run %CONDA_TARGET_FLAG% "%CONDA_TARGET_VALUE%" python cli\run_ingestion.py --input-dir "%GOODQ_SAMPLE_INPUT_DIR%" --workspace logs\test_workspace --output logs\test_results.json --verbose --force
set "GOODQ_TEST_EXIT=%ERRORLEVEL%"

echo.
echo ============================================================================
echo                         INGESTION TEST COMPLETE
echo ============================================================================
echo.

popd
exit /b %GOODQ_TEST_EXIT%
