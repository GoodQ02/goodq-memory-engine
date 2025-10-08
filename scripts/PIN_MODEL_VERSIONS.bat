@echo off
REM Fetch and pin exact model versions (commit SHAs) from HuggingFace Hub
REM This updates model_registry.yaml with actual commit hashes

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
echo Activating goodq_zenml environment...
call conda activate goodq_zenml

echo.
echo Running model version pinning...
python scripts\pin_model_versions.py

echo.
echo ========================================
echo  Complete!
echo ========================================
echo.
echo Review the updated configs\model_registry.yaml file
echo A backup was saved as model_registry.yaml.bak
echo.
pause
