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

REM Run validation script using conda run
conda run -n goodq_zenml python L:\goodq4all\scripts\validate_ingestion_output.py
if errorlevel 1 (
    echo [ERROR] Failed to run validation
    pause
    exit /b 1
)

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
