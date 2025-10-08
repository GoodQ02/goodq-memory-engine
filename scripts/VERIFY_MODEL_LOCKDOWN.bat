@echo off
REM Verify that all models are properly locked down with exact versions

echo ========================================
echo  Verify Model Lockdown
echo ========================================
echo.

cd /d "%~dp0.."

echo Activating goodq_zenml environment...
call conda activate goodq_zenml

echo.
echo Running lockdown verification...
python scripts\verify_model_lockdown.py

echo.
pause
