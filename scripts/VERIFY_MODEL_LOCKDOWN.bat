@echo off
REM Verify that all models are properly locked down with exact versions

call "%~dp0_lib\\interpreter_bindings.bat"

echo ========================================
echo  Verify Model Lockdown
echo ========================================
echo.

cd /d "%~dp0.."

echo Running lockdown verification...
"%CONDA_EXE%" run -n goodq_zenml python scripts\verify_model_lockdown.py

echo.
pause
