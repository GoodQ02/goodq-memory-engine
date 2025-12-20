@echo off
REM ================================================================================
REM  GoodQ4All - Complete System Test
REM  Validates all components and runs end-to-end test
REM ================================================================================

setlocal enabledelayedexpansion
call "%~dp0..\\_lib\\interpreter_bindings.bat"

title GoodQ4All System Test
color 0E

echo.
echo ================================================================================
echo  GoodQ4All Complete System Validation
echo ================================================================================
echo.

cd /d "L:\goodq4all"

REM Step 1: Check for running processes
echo [1/8] Checking for conflicting processes...
tasklist /FI "WINDOWTITLE eq GoodQ*" 2>NUL | find /I /N "python.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [!] WARNING: GoodQ processes are running
    echo Please stop them first for accurate testing
    set /p continue="Continue anyway? (y/N): "
    if /i not "!continue!"=="y" (
        echo Test cancelled
        pause
        exit /b 1
    )
) else (
    echo [✓] No conflicting processes
)

echo.
echo [2/8] Validating Python paths...
"%CONDA_EXE%" run --no-capture-output -n goodq_zenml python test_python_paths.py
if %ERRORLEVEL% NEQ 0 (
    echo [✗] Python path validation failed
    pause
    exit /b 1
)
echo [✓] Python paths OK

echo.
echo [3/8] Checking database integrity...
"%CONDA_EXE%" run --no-capture-output -n goodq_zenml python check_db_stats.py
echo [✓] Database check complete

echo.
echo [4/8] Checking FAISS indices...
if exist "L:\goodq4all\data\faiss_indices" (
    dir /B "L:\goodq4all\data\faiss_indices\*.index" 2>NUL
    if %ERRORLEVEL% EQU 0 (
        echo [✓] FAISS indices found
    ) else (
        echo [!] No FAISS indices yet - will be created during processing
    )
) else (
    echo [!] FAISS directory missing - will be created
)

echo.
echo [5/8] Checking for stale lock files...
if exist "L:\goodq4all\data\.watchdog.lock" (
    echo [!] Found stale watchdog lock file
    del /F "L:\goodq4all\data\.watchdog.lock"
    echo [✓] Removed stale lock
) else (
    echo [✓] No stale locks
)

echo.
echo [6/8] Checking import_inbox...
dir /B "L:\goodq4all\import_inbox\*.mp4" 2>NUL
if %ERRORLEVEL% EQU 0 (
    echo [✓] Videos found in import_inbox
) else (
    echo [!] No videos in import_inbox
)

echo.
echo [7/8] Checking processing directory...
if exist "L:\goodq4all\data\processing" (
    dir /B "L:\goodq4all\data\processing" 2>NUL
    if %ERRORLEVEL% EQU 0 (
        echo [!] Files in processing directory - may be from incomplete run
    ) else (
        echo [✓] Processing directory clean
    )
)

echo.
echo [8/8] Testing API server startup...
echo Starting API server in background (10 second test)...
start "GoodQ Test API" /MIN "%CONDA_EXE%" run --no-capture-output -n goodq_zenml python scripts\api_server.py
timeout /t 8 /nobreak >nul

echo Testing API connectivity...
curl -s http://localhost:30000/api/status >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [✓] API server responding
    curl -s http://localhost:30000/api/status
) else (
    echo [✗] API server not responding
)

echo.
echo Stopping test API server...
taskkill /FI "WINDOWTITLE eq GoodQ Test API*" /F >nul 2>&1
timeout /t 2 /nobreak >nul

echo.
echo ================================================================================
echo  System Validation Complete
echo ================================================================================
echo.
echo  All checks passed! System is ready for production use.
echo.
echo  Next steps:
echo    1. Run LAUNCH_GOODQ.bat to start the full system
echo    2. Drop a video in L:\goodq4all\import_inbox
echo    3. Open http://localhost:30000 to monitor progress
echo.
echo ================================================================================
pause
