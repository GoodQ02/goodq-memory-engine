@echo off
REM GoodQ Environment Setup & Dependency Installer
REM Ensures the configured GoodQ conda env has required packages for the web interface

echo ================================================================================
echo   GoodQ Environment Setup - Installing Missing Dependencies
echo ================================================================================
echo.

call "%~dp0_lib\\interpreter_bindings.bat"
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"
cd /d "%REPO_ROOT%"

REM Check if conda exists
if "%CONDA_EXE%"=="conda" (
    where conda >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Conda not found on PATH
        pause
        exit /b 1
    )
)

echo [1/4] Checking %GOODQ_CONDA_ENV% environment...
"%CONDA_EXE%" run -n %GOODQ_CONDA_ENV% python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to run Python in %GOODQ_CONDA_ENV% environment
    pause
    exit /b 1
)

echo [2/4] Installing FastAPI and dependencies...
"%CONDA_EXE%" run -n %GOODQ_CONDA_ENV% pip install fastapi uvicorn[standard] python-multipart websockets pydantic --quiet
if errorlevel 1 (
    echo [WARNING] Some packages may have failed to install
)

echo [3/4] Verifying installation...
"%CONDA_EXE%" run -n %GOODQ_CONDA_ENV% python -c "import fastapi; print('FastAPI version:', fastapi.__version__)"
if errorlevel 1 (
    echo [ERROR] FastAPI installation failed
    pause
    exit /b 1
)

"%CONDA_EXE%" run -n %GOODQ_CONDA_ENV% python -c "import uvicorn; print('Uvicorn version:', uvicorn.__version__)"
if errorlevel 1 (
    echo [ERROR] Uvicorn installation failed
    pause
    exit /b 1
)

echo.
echo [4/4] Installation complete!
echo.
echo ================================================================================
echo   SUCCESS! Dependencies installed in %GOODQ_CONDA_ENV% environment
echo ================================================================================
echo.
echo You can now run: LAUNCH_WEB_INTERFACE_FIXED.bat
echo.
pause
