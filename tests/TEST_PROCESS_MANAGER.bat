@echo off
REM Quick Test of Process Management System

title GoodQ Process Management Test

echo.
echo ================================================================================
echo   GoodQ4All Process Management System - Quick Test
echo ================================================================================
echo.

cd /d L:\goodq4all

SET PYTHON_EXE=C:\Users\jdben\miniconda3\envs\goodq_zenml\python.exe

echo [TEST 1] Checking Python environment...
"%PYTHON_EXE%" --version
if errorlevel 1 (
    echo [FAIL] Python not found
    pause
    exit /b 1
)
echo [PASS] Python environment OK
echo.

echo [TEST 2] Checking psutil dependency...
"%PYTHON_EXE%" -c "import psutil; print('psutil version:', psutil.__version__)"
if errorlevel 1 (
    echo [FAIL] psutil not installed
    echo Installing psutil...
    "%PYTHON_EXE%" -m pip install psutil --quiet
    if errorlevel 1 (
        echo [FAIL] Could not install psutil
        pause
        exit /b 1
    )
    echo [PASS] psutil installed
) else (
    echo [PASS] psutil available
)
echo.

echo [TEST 3] Testing process manager CLI...
"%PYTHON_EXE%" process_manager.py status
if errorlevel 1 (
    echo [FAIL] Process manager CLI failed
    pause
    exit /b 1
)
echo [PASS] Process manager CLI working
echo.

echo [TEST 4] Checking batch scripts exist...
if not exist "START_GOODQ_SYSTEM.bat" (
    echo [FAIL] START_GOODQ_SYSTEM.bat not found
    pause
    exit /b 1
)
if not exist "STOP_GOODQ_SYSTEM.bat" (
    echo [FAIL] STOP_GOODQ_SYSTEM.bat not found
    pause
    exit /b 1
)
if not exist "STATUS_CHECK.bat" (
    echo [FAIL] STATUS_CHECK.bat not found
    pause
    exit /b 1
)
echo [PASS] All batch scripts found
echo.

echo [TEST 5] Checking log directory...
if not exist "logs" (
    mkdir logs
    echo Created logs directory
)
if not exist "logs\pids" (
    mkdir logs\pids
    echo Created logs\pids directory
)
echo [PASS] Log directories OK
echo.

echo [TEST 6] Verifying API server file...
if not exist "api_server.py" (
    echo [FAIL] api_server.py not found
    pause
    exit /b 1
)
echo [PASS] API server file found
echo.

echo [TEST 7] Checking process manager integration...
"%PYTHON_EXE%" -c "from process_manager import create_goodq_manager; m = create_goodq_manager(); print('Processes registered:', len(m.processes))"
if errorlevel 1 (
    echo [FAIL] Process manager integration error
    pause
    exit /b 1
)
echo [PASS] Process manager integration OK
echo.

echo ================================================================================
echo   ALL TESTS PASSED!
echo ================================================================================
echo.
echo Process Management System is ready to use:
echo.
echo   Start System:  START_GOODQ_SYSTEM.bat
echo   Stop System:   STOP_GOODQ_SYSTEM.bat  
echo   Check Status:  STATUS_CHECK.bat
echo   Web UI:        http://localhost:3000 (after starting)
echo.
echo ================================================================================

pause
