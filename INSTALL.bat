@echo off
REM ================================================================================
REM GoodQ4All Automated Installer
REM ================================================================================

echo.
echo ================================================================================
echo   GoodQ4All Installation
echo ================================================================================
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [WARNING] Not running as administrator
    echo Some features may require admin privileges
    echo.
    pause
)

REM Get the script directory
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Check if Python is available
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Python not found in PATH
    echo.
    echo Please install Python 3.9+ or Miniconda and try again
    echo Visit: https://docs.conda.io/en/latest/miniconda.html
    pause
    exit /b 1
)

REM Check if conda is available
conda --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [WARNING] Conda not found in PATH
    echo.
    echo The installation will continue, but you may need to manually
    echo create the conda environment later using:
    echo   conda env create -f envs\goodq_zenml.yaml
    echo.
    pause
)

REM Run the Python installer
echo.
echo Running Python installer...
echo.

python scripts\setup\install_goodq.py

if %errorLevel% neq 0 (
    echo.
    echo [ERROR] Installation failed
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo   Installation Complete!
echo ================================================================================
echo.
echo Next steps:
echo   1. Review .env.local and update settings if needed
echo   2. Start LM Studio with a model loaded
echo   3. Run LAUNCH_GOODQ.bat to start the system
echo   4. Open http://localhost:3000 in your browser
echo.

pause
