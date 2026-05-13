@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM ================================================================================
REM  GPU-Optimized Pipeline Test
REM  Tests the complete pipeline with GPU allocation system
REM ================================================================================

call "%~dp0_lib\\interpreter_bindings.bat"
for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"
for %%D in ("%REPO_ROOT%") do set "REPO_DRIVE=%%~dD"
if "%GOODQ_DATA_ROOT%"=="" set "GOODQ_DATA_ROOT=%REPO_DRIVE%\_DATA"
if "%GOODQ_CONDA_ENV%"=="" set "GOODQ_CONDA_ENV=goodq_core"

title GoodQ GPU Pipeline Test
color 0E

echo.
echo ================================================================================
echo   GPU-Optimized Pipeline Test
echo ================================================================================
echo.
echo  This will:
echo    1. Check GPU status and availability
echo    2. Clear any stuck processes
echo    3. Run a test video through the pipeline
echo    4. Monitor GPU usage throughout
echo.
echo ================================================================================
echo.

cd /d "%REPO_ROOT%"

for /f "usebackq tokens=1,* delims==" %%A in (`"%CONDA_EXE%" run -n %GOODQ_CONDA_ENV% --no-capture-output python -c "from steps.common.config_loader import get_runtime_paths, load_configs; paths=get_runtime_paths(load_configs({}),'watchdog_lock_file'); print('IMPORT_INBOX=' + paths['import_inbox']); print('PROCESSING_DIR=' + paths['processing']); print('DB_PATH=' + paths['db_path']); print('WATCHDOG_LOCK_FILE=' + paths['watchdog_lock_file'])"`) do (
    set "%%A=%%B"
)

if not defined IMPORT_INBOX (
    echo [ERROR] Failed to resolve canonical import inbox
    pause
    exit /b 1
)
if not defined PROCESSING_DIR (
    echo [ERROR] Failed to resolve canonical processing directory
    pause
    exit /b 1
)
if not defined DB_PATH (
    echo [ERROR] Failed to resolve canonical database path
    pause
    exit /b 1
)

REM Step 1: Diagnostic
echo [1/5] Running diagnostics...
"%CONDA_EXE%" run --no-capture-output -n %GOODQ_CONDA_ENV% python -m cli.goodq_doctor
if errorlevel 1 (
    echo.
    echo [ERROR] Diagnostics failed
    pause
    exit /b 1
)

echo.
echo [2/5] Checking for stuck processes...
REM Clean up any lock files
if exist "%WATCHDOG_LOCK_FILE%" (
    echo   Removing watchdog lock...
    del /f "%WATCHDOG_LOCK_FILE%" 2>nul
)

REM Clear processing directory
if exist "%PROCESSING_DIR%\*" (
    echo   Clearing processing directory...
    del /f "%PROCESSING_DIR%\*" 2>nul
    for /d %%I in ("%PROCESSING_DIR%\*") do rd /s /q "%%~fI" 2>nul
)

echo   [OK] Ready to process

echo.
echo [3/5] Checking import inbox...
dir /b "%IMPORT_INBOX%\*.mp4" 2>nul
if errorlevel 1 (
    echo.
    echo [!] No videos in import inbox
    echo.
    echo   Provide a local sample video path or press Enter to cancel.
    set /p test_video="Test video path: "
    if defined test_video (
        copy "!test_video!" "%IMPORT_INBOX%\" >nul
        echo   [OK] Copied test video
    ) else (
        echo.
        echo   Cancelled
        pause
        exit /b 0
    )
)

echo.
echo [4/5] Starting pipeline with GPU optimization...
echo.
echo ================================================================================
echo  IMPORTANT: Monitor GPU usage in another terminal
echo ================================================================================
echo  Open a new PowerShell window and run:
echo    nvidia-smi -l 1
echo.
echo  This will show real-time GPU memory usage
echo ================================================================================
echo.

set /p start_pipeline="Start processing? (y/N): "
if /i not "%start_pipeline%"=="y" (
    echo.
    echo Cancelled
    pause
    exit /b 0
)

echo.
echo ================================================================================
echo  Starting Pipeline
echo ================================================================================
echo.
echo   Watch for:
echo     • GPU memory allocation per step
echo     • Cache clearing between steps
echo     • Performance (realtime factor)
echo     • No OOM errors
echo.
echo   Press Ctrl+C to stop processing
echo.
echo ================================================================================
echo.

REM Start the watchdog in current window to see output
"%CONDA_EXE%" run --no-capture-output -n %GOODQ_CONDA_ENV% python -m cli.watchdog

echo.
echo ================================================================================
echo  Processing Complete
echo ================================================================================
echo.

echo [5/5] Checking results...
"%CONDA_EXE%" run --no-capture-output -n %GOODQ_CONDA_ENV% python -c "import sqlite3; conn = sqlite3.connect(r'%DB_PATH%'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM scenes'); print(f'Scenes created: {cursor.fetchone()[0]}'); conn.close()"

echo.
echo ================================================================================
echo  Test Complete
echo ================================================================================
echo.
echo  Check the logs for:
echo    • GPU memory usage stayed within limits
echo    • No OOM errors
echo    • Processing completed successfully
echo    • All steps used GPU when available
echo.

pause
