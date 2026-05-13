@echo off
REM Fetch and pin exact model versions (commit SHAs) from HuggingFace Hub
REM This updates model_registry.yaml with actual commit hashes

call "%~dp0_lib\\interpreter_bindings.bat"
if "%GOODQ_CONDA_ENV%"=="" set "GOODQ_CONDA_ENV=goodq_core"

echo ========================================
echo  Pin Model Versions
echo ========================================
echo.
echo This will fetch the latest commit SHAs for all HuggingFace models
echo and update model_registry.yaml with pinned versions.
echo.
echo Press Ctrl+C to cancel, or
pause

cd /d "%~dp0.."

echo.
echo Running model version pinning...
"%CONDA_EXE%" run -n %GOODQ_CONDA_ENV% python scripts\pin_model_versions.py

echo.
echo ========================================
echo  Complete!
echo ========================================
echo.
echo Review the updated configs\model_registry.yaml file
echo A backup was saved as model_registry.yaml.bak
echo.
pause
