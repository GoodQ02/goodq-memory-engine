@echo off
REM GoodQ4All - Quick System Test
REM Tests the complete pipeline with sample video

echo.
echo ===============================================================================
echo GOODQ4ALL - QUICK SYSTEM TEST
echo ===============================================================================
echo.

REM Activate goodq_core environment
call conda activate goodq_core
if errorlevel 1 (
    echo ERROR: Failed to activate goodq_core environment
    pause
    exit /b 1
)

REM Set Python path
set PYTHONPATH=L:\goodq4all
echo PYTHONPATH set to: %PYTHONPATH%
echo.

REM Run system status first
echo [1/2] Running System Status Check...
echo -------------------------------------------------------------------------------
python L:\goodq4all\cli\system_status.py
if errorlevel 1 (
    echo.
    echo WARNING: System status check reported issues
    echo.
)

echo.
echo.
echo [2/2] Running End-to-End Ingestion Test...
echo ===============================================================================
python L:\goodq4all\cli\test_ingestion.py

echo.
echo.
echo ===============================================================================
echo TEST COMPLETE
echo ===============================================================================
echo.
pause
