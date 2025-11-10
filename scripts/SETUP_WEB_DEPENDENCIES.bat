@echo off
REM GoodQ Environment Setup & Dependency Installer
REM Ensures goodq_zenml has all required packages for the web interface

echo ================================================================================
echo   GoodQ Environment Setup - Installing Missing Dependencies
echo ================================================================================
echo.

cd /d L:\goodq4all

SET CONDA_PATH=C:\Users\jdben\miniconda3
SET CONDA_EXE=%CONDA_PATH%\Scripts\conda.exe

REM Check if conda exists
if not exist "%CONDA_EXE%" (
    echo [ERROR] Conda not found at: %CONDA_EXE%
    pause
    exit /b 1
)

echo [1/4] Activating goodq_zenml environment...
call "%CONDA_PATH%\Scripts\activate.bat" goodq_zenml
if errorlevel 1 (
    echo [ERROR] Failed to activate goodq_zenml environment
    pause
    exit /b 1
)

echo [2/4] Installing FastAPI and dependencies...
pip install fastapi uvicorn[standard] python-multipart websockets pydantic --quiet
if errorlevel 1 (
    echo [WARNING] Some packages may have failed to install
)

echo [3/4] Verifying installation...
python -c "import fastapi; print('FastAPI version:', fastapi.__version__)"
if errorlevel 1 (
    echo [ERROR] FastAPI installation failed
    pause
    exit /b 1
)

python -c "import uvicorn; print('Uvicorn version:', uvicorn.__version__)"
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
