@echo off
REM GoodQ4All - WSL2 Audio Setup Launcher
REM This will install audio processing in WSL2 Ubuntu

echo ================================================================================
echo   GoodQ4All - WSL2 Audio Setup
echo ================================================================================
echo.
echo This will set up GPU-accelerated audio processing in WSL2
echo.
echo Requirements:
echo   - WSL2 with Ubuntu installed
echo   - NVIDIA GPU with CUDA support
echo   - sudo password for Ubuntu
echo.
echo Installation will:
echo   1. Install Python venv and dependencies in WSL2
echo   2. Create virtual environment with PyTorch + CUDA
echo   3. Install Whisper and audio libraries
echo   4. Create processing scripts
echo   5. Test GPU availability
echo.
echo Estimated time: 10-15 minutes
echo.
pause

echo.
echo Checking WSL2...
wsl --list --verbose
if errorlevel 1 (
    echo.
    echo ERROR: WSL2 not found or not running
    echo Please install WSL2 and Ubuntu first
    pause
    exit /b 1
)

echo.
echo Launching WSL2 installer...
echo You will be prompted for your Ubuntu password
echo.

wsl -d Ubuntu -- bash /mnt/l/goodq4all/scripts/wsl2_quick_install.sh

if errorlevel 1 (
    echo.
    echo ================================================================================
    echo   Installation Failed
    echo ================================================================================
    echo.
    echo Check the error messages above and try again
    echo Or follow the manual setup guide in:
    echo   L:\goodq4all\docs\WSL2_AUDIO_SETUP.md
    echo.
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo   Testing Bridge
echo ================================================================================
echo.

python L:\goodq4all\wsl2_audio_bridge.py

echo.
echo ================================================================================
echo   Installation Complete!
echo ================================================================================
echo.
echo WSL2 audio processing is now available
echo.
echo Next steps:
echo   1. Test with a sample: python test_wsl2_audio.py
echo   2. Integrate with pipeline steps
echo   3. Run production test
echo.
echo Documentation: L:\goodq4all\docs\WSL2_AUDIO_SETUP.md
echo.
pause
