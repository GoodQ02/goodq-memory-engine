@echo off
REM ================================================================================
REM  GPU-Optimized Pipeline Test
REM  Tests the complete pipeline with GPU allocation system
REM ================================================================================

call "%~dp0_lib\\interpreter_bindings.bat"

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

cd /d "L:\goodq4all"

REM Step 1: Diagnostic
echo [1/5] Running diagnostics...
"%CONDA_EXE%" run --no-capture-output -n goodq_zenml python scripts\diagnose_gpu_issue.py
if errorlevel 1 (
    echo.
    echo [ERROR] Diagnostics failed
    pause
    exit /b 1
)

echo.
echo [2/5] Checking for stuck processes...
REM Clean up any lock files
if exist "L:\goodq4all\data\.watchdog.lock" (
    echo   Removing watchdog lock...
    del /f "L:\goodq4all\data\.watchdog.lock" 2>nul
)

REM Clear processing directory
if exist "L:\goodq4all\data\processing\*.mp4" (
    echo   Clearing processing directory...
    del /f "L:\goodq4all\data\processing\*.mp4" 2>nul
)

echo   [OK] Ready to process

echo.
echo [3/5] Checking import inbox...
dir /b "L:\goodq4all\import_inbox\*.mp4" 2>nul
if errorlevel 1 (
    echo.
    echo [!] No videos in import inbox
    echo.
    set /p copy_video="Copy test video? (y/N): "
    if /i "!copy_video!"=="y" (
        copy "L:\_DATA\FAMILY_FEAST\09. 2002 - 2003.mp4" "L:\goodq4all\import_inbox\" >nul
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
"%CONDA_EXE%" run --no-capture-output -n goodq_zenml python scripts/watchdog_ingest.py

echo.
echo ================================================================================
echo  Processing Complete
echo ================================================================================
echo.

echo [5/5] Checking results...
"%CONDA_EXE%" run --no-capture-output -n goodq_zenml python -c "import sqlite3; conn = sqlite3.connect('output/knowledge.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM scenes'); print(f'Scenes created: {cursor.fetchone()[0]}'); conn.close()"

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
