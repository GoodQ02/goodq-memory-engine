@echo off
REM ============================================================================
REM GoodQ4All - Start WSL2 Audio Service
REM ============================================================================

call "%~dp0..\\scripts\\_lib\\interpreter_bindings.bat"
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"
for /f "delims=" %%I in ('powershell -NoProfile -Command "$p=$env:REPO_ROOT.TrimEnd('\\');$d=$p.Substring(0,1).ToLower();$rest=$p.Substring(2).Replace('\\','/');Write-Output ('/mnt/' + $d + $rest)"') do set "WSL_REPO_ROOT=%%I"
if "%GOODQ_WSL_WORKSPACE%"=="" set "GOODQ_WSL_WORKSPACE=~/goodq_audio"
set "WSL_AUDIO_SCRIPT=%WSL_REPO_ROOT%/wsl2_audio/audio_service.py"

echo ================================================================================
echo   GoodQ4All - Starting WSL2 Audio Service
echo ================================================================================
echo.

REM Check if WSL2 service is already running
wsl -d %GOODQ_WSL_DISTRO% -- pgrep -f audio_service.py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] WSL2 audio service is already running
    echo.
    echo To stop it, run: wsl -d %GOODQ_WSL_DISTRO% -- pkill -f audio_service.py
    echo.
    pause
    exit /b 0
)

echo [INFO] Starting WSL2 audio service...
echo [INFO] This will run in the background
echo.

REM Start the service in WSL2
start "GoodQ WSL2 Audio Service" wsl -d %GOODQ_WSL_DISTRO% -- bash -c "cd %GOODQ_WSL_WORKSPACE% && source setup_cuda_env.sh && python3 %WSL_AUDIO_SCRIPT%"

timeout /t 3 /nobreak >nul

REM Check if it started
wsl -d %GOODQ_WSL_DISTRO% -- pgrep -f audio_service.py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ================================================================================
    echo   WSL2 Audio Service Started Successfully!
    echo ================================================================================
    echo.
    echo The service is now running in the background
    echo.
    echo To check logs:
    echo   wsl tail -f %GOODQ_WSL_WORKSPACE%/logs/audio_service.log
    echo.
    echo To stop the service:
    echo   wsl -d %GOODQ_WSL_DISTRO% -- pkill -f audio_service.py
    echo.
) else (
    echo ================================================================================
    echo   Failed to Start Service
    echo ================================================================================
    echo.
    echo Please check that:
    echo   1. WSL2 setup was completed: cd %GOODQ_WSL_WORKSPACE% ^&^& ./setup_wsl2_audio.sh
    echo   2. HuggingFace token is set in %GOODQ_WSL_WORKSPACE%/config.json
    echo.
)

pause
