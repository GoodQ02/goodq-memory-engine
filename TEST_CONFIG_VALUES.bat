@echo off
REM ============================================================
REM  🔍 Test Configuration Values
REM  Validates that all settings are loaded correctly
REM ============================================================

cd /d L:\goodq4all

echo.
echo ╔═══════════════════════════════════════════════════════════════╗
echo ║          🔍 GoodQ Configuration Values Test                   ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.

REM Activate environment
call conda activate goodq_zenml 2>nul
if errorlevel 1 (
    echo [ERROR] Failed to activate goodq_zenml environment
    pause
    exit /b 1
)

REM Run config test
python scripts\test_config_values.py

echo.
echo ════════════════════════════════════════════════════════════════
echo  Test complete! Review settings above.
echo ════════════════════════════════════════════════════════════════
echo.

pause
