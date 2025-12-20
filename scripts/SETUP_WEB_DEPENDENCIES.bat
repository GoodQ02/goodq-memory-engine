@echo off
REM GoodQ Environment Setup & Dependency Installer
REM Ensures goodq_zenml has all required packages for the web interface

echo ================================================================================
echo   GoodQ Environment Setup - Installing Missing Dependencies
echo ================================================================================
echo.

cd /d L:\goodq4all

call "%~dp0_lib\\interpreter_bindings.bat"

REM Check if conda exists
if "%CONDA_EXE%"=="conda" (
    where conda >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Conda not found on PATH
        pause
        exit /b 1
    )
)

echo [1/4] Checking goodq_zenml environment...
"%CONDA_EXE%" run -n goodq_zenml python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to run Python in goodq_zenml environment
    pause
    exit /b 1
)

echo [2/4] Installing FastAPI and dependencies...
"%CONDA_EXE%" run -n goodq_zenml pip install fastapi uvicorn[standard] python-multipart websockets pydantic --quiet
if errorlevel 1 (
    echo [WARNING] Some packages may have failed to install
)

echo [3/4] Verifying installation...
"%CONDA_EXE%" run -n goodq_zenml python -c "import fastapi; print('FastAPI version:', fastapi.__version__)"
if errorlevel 1 (
    echo [ERROR] FastAPI installation failed
    pause
    exit /b 1
)

"%CONDA_EXE%" run -n goodq_zenml python -c "import uvicorn; print('Uvicorn version:', uvicorn.__version__)"
if errorlevel 1 (
    echo [ERROR] Uvicorn installation failed
    pause
    exit /b 1
)

echo.
echo [4/4] Installation complete!
echo.
echo ================================================================================
echo   SUCCESS! Dependencies installed in goodq_zenml environment
echo ================================================================================
echo.
echo You can now run: LAUNCH_WEB_INTERFACE_FIXED.bat
echo.
pause
