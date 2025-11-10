@echo off
title GoodQ4All - Python Path Validation
color 0E

echo ================================================================================
echo   GoodQ4All Python Path Configuration Validation
echo ================================================================================
echo.

cd /d "%~dp0"

echo [Step 1/3] Activating conda environment...
call conda activate goodq_zenml
if errorlevel 1 (
    echo ERROR: Failed to activate conda environment 'goodq_zenml'
    echo.
    echo Please ensure Conda is installed and the environment exists.
    echo Run: conda env create -f environment.yml
    pause
    exit /b 1
)
echo ? Environment activated
echo.

echo [Step 2/3] Running Python path configuration test...
python test_python_paths.py
set TEST_RESULT=%ERRORLEVEL%
echo.

if %TEST_RESULT% EQU 0 (
    echo [Step 3/3] Validation Result
    echo ================================================================================
    echo   ? ALL PYTHON PATHS CONFIGURED CORRECTLY
    echo ================================================================================
    echo.
    echo The centralized Python path configuration is working properly.
    echo All conda environments are accessible.
    echo.
) else (
    echo [Step 3/3] Validation Result
    echo ================================================================================
    echo   ? CONFIGURATION ISSUES DETECTED
    echo ================================================================================
    echo.
    echo Please review the test output above for details.
    echo Some conda environments may be missing or inaccessible.
    echo.
)

echo Documentation: L:\goodq4all\docs\PYTHON_PATH_CONFIGURATION.md
echo.
pause
