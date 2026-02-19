@echo off
REM GoodQ4All - WSL2 Audio Setup Launcher
REM This will install audio processing in WSL2 Ubuntu

call "%~dp0_lib\\interpreter_bindings.bat"
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"
for /f "delims=" %%I in ('powershell -NoProfile -Command "$p=$env:REPO_ROOT.TrimEnd('\\');$d=$p.Substring(0,1).ToLower();$rest=$p.Substring(2).Replace('\\','/');Write-Output ('/mnt/' + $d + $rest)"') do set "WSL_REPO_ROOT=%%I"

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

wsl -d %GOODQ_WSL_DISTRO% -- bash "%WSL_REPO_ROOT%/scripts/wsl2_quick_install.sh"

if errorlevel 1 (
    echo.
    echo ================================================================================
    echo   Installation Failed
    echo ================================================================================
    echo.
    echo Check the error messages above and try again
    echo Or follow the manual setup guide in:
    echo   %REPO_ROOT%\docs\WSL2_AUDIO_SETUP.md
    echo.
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo   Testing Bridge
echo ================================================================================
echo.

"%CONDA_EXE%" run -n %GOODQ_CONDA_ENV% python "%SCRIPT_DIR%wsl2_audio_bridge.py"

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
echo Documentation: %REPO_ROOT%\docs\WSL2_AUDIO_SETUP.md
echo.
pause
