@echo off
REM 🔍 Mission Intel: Validate Ingestion Output
REM Comprehensive analysis to detect silent failures

setlocal enabledelayedexpansion

echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║     🔍 Mission Intel: Output Validation                      ║
echo ║     Analyzing ingestion results for silent failures...       ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

REM Activate conda environment
call conda activate goodq_zenml
if errorlevel 1 (
    echo [ERROR] Failed to activate goodq_zenml environment
    pause
    exit /b 1
)

REM Run validation script
python L:\goodq4all\scripts\validate_ingestion_output.py

REM Check exit code
if errorlevel 1 (
    echo.
    echo [CRITICAL] Validation detected failures!
    echo Review the output above for details.
) else (
    echo.
    echo [SUCCESS] Validation passed!
)

echo.
echo Press any key to exit...
pause >nul
