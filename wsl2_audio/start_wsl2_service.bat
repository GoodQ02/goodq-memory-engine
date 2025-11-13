@echo off
REM ============================================================================
REM GoodQ4All - Start WSL2 Audio Service
REM ============================================================================

echo ================================================================================
echo   GoodQ4All - Starting WSL2 Audio Service
echo ================================================================================
echo.

REM Check if WSL2 service is already running
wsl pgrep -f audio_service.py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] WSL2 audio service is already running
    echo.
    echo To stop it, run: wsl pkill -f audio_service.py
    echo.
    pause
    exit /b 0
)

echo [INFO] Starting WSL2 audio service...
echo [INFO] This will run in the background
echo.

REM Start the service in WSL2
start "GoodQ WSL2 Audio Service" wsl bash -c "cd ~/goodq_audio && source venv/bin/activate && python3 /mnt/l/goodq4all/wsl2_audio/audio_service.py"

timeout /t 3 /nobreak >nul

REM Check if it started
wsl pgrep -f audio_service.py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ================================================================================
    echo   WSL2 Audio Service Started Successfully!
    echo ================================================================================
    echo.
    echo The service is now running in the background
    echo.
    echo To check logs:
    echo   wsl tail -f ~/goodq_audio/logs/audio_service.log
    echo.
    echo To stop the service:
    echo   wsl pkill -f audio_service.py
    echo.
) else (
    echo ================================================================================
    echo   Failed to Start Service
    echo ================================================================================
    echo.
    echo Please check that:
    echo   1. WSL2 setup was completed: cd ~/goodq_audio ^&^& ./setup_wsl2_audio.sh
    echo   2. HuggingFace token is set in ~/goodq_audio/config.json
    echo.
)

pause
