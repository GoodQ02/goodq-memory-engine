@echo off
REM ================================================================================
REM  GoodQ4All - Complete Environment Fix
REM  This script fixes all environment naming and path issues
REM ================================================================================

cd /d "%~dp0"

echo ================================================================================
echo   GoodQ4All - Environment Configuration Fix
echo ================================================================================
echo.
echo This will:
echo   1. Verify all conda environments exist
echo   2. Test environment activation in PowerShell
echo   3. Update all scripts to use correct environment names
echo   4. Configure proper execution paths
echo.
echo Press CTRL+C to cancel or
pause

REM Activate conda for this session
call C:\Users\jdben\miniconda3\Scripts\activate.bat

echo.
echo ================================================================================
echo   Step 1: Verifying Conda Environments
echo ================================================================================
echo.

conda env list

echo.
echo ================================================================================
echo   Step 2: Running Comprehensive Fix Script
echo ================================================================================
echo.

python scripts\fix_all_environments.py

if errorlevel 1 (
    echo.
    echo [ERROR] Fix script failed
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo   Step 3: Validation
echo ================================================================================
echo.

python scripts\validate_environment_fix.py

echo.
echo ================================================================================
echo   Fix Complete!
echo ================================================================================
echo.
echo Next steps:
echo   1. Close all terminals
echo   2. Open a new PowerShell 7 session
echo   3. Navigate to L:\goodq4all
echo   4. Run: .\LAUNCH_GOODQ.bat
echo.
pause
