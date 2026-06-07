@echo off
REM Verify that all models are properly locked down with exact versions

call "%~dp0_lib\\interpreter_bindings.bat"
if "%GOODQ_CONDA_ENV%"=="" set "GOODQ_CONDA_ENV=goodq_core"

echo ========================================
echo  Verify Model Lockdown
echo ========================================
echo.

cd /d "%~dp0.."

echo Running lockdown verification...
"%CONDA_EXE%" run -n %GOODQ_CONDA_ENV% python scripts\utils\verify_model_lockdown.py

echo.
pause
