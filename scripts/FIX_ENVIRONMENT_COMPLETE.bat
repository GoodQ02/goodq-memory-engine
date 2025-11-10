@echo off
REM GoodQ Complete Environment Fix
REM Installs FastAPI in the correct goodq_zenml environment

echo ================================================================================
echo   GoodQ Complete Environment Fix
echo   Installing web dependencies in goodq_zenml environment
echo ================================================================================
echo.

cd /d L:\goodq4all

SET CONDA_PATH=C:\Users\jdben\miniconda3

echo [Step 1/3] Activating goodq_zenml environment...
call "%CONDA_PATH%\Scripts\activate.bat" goodq_zenml

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to activate goodq_zenml
    echo The environment may not exist. Creating it now...
    echo.
    
    REM Create environment if it doesn't exist
    call "%CONDA_PATH%\Scripts\conda.exe" create -n goodq_zenml python=3.10 -y
    
    if errorlevel 1 (
        echo [ERROR] Failed to create environment
        pause
        exit /b 1
    )
    
    echo.
    echo [SUCCESS] Environment created. Activating...
    call "%CONDA_PATH%\Scripts\activate.bat" goodq_zenml
)

echo.
echo [Step 2/3] Installing web server dependencies...
echo This will take 1-2 minutes...
echo.

python -m pip install --upgrade pip --quiet
python -m pip install fastapi uvicorn[standard] python-multipart websockets pydantic --quiet

if errorlevel 1 (
    echo [ERROR] Installation failed
    pause
    exit /b 1
)

echo.
echo [Step 3/3] Verifying installation...

python -c "import fastapi; print('  - FastAPI:', fastapi.__version__)"
python -c "import uvicorn; print('  - Uvicorn:', uvicorn.__version__)"
python -c "import websockets; print('  - WebSockets:', websockets.__version__)"
python -c "import pydantic; print('  - Pydantic:', pydantic.__version__)"

echo.
echo ================================================================================
echo   SUCCESS! Web dependencies installed in goodq_zenml
echo ================================================================================
echo.
echo Next step: Double-click LAUNCH_WEB_INTERFACE_FIXED_V2.bat
echo.
pause
