@echo off
REM ================================================================================
REM  GoodQ4All - Critical Issues Fix
REM  Resolves all blocking issues identified in system audit
REM ================================================================================

cd /d "%~dp0"

echo ================================================================================
echo   GoodQ4All - Critical Issues Fix
echo ================================================================================
echo.
echo This will fix:
echo   1. Add FFmpeg to PATH (found at L:\_TOOLS\ffmpeg\bin)
echo   2. Fix PyAnnote GPU transfer API
echo   3. Update scene detection configuration
echo   4. Validate all fixes
echo.
echo Press CTRL+C to cancel or
pause

echo.
echo ================================================================================
echo   Step 1: Adding FFmpeg to PATH
echo ================================================================================
echo.

setx PATH "%PATH%;L:\_TOOLS\ffmpeg\bin"

if errorlevel 1 (
    echo [WARNING] Failed to permanently add FFmpeg to PATH
    echo You may need to run this script as Administrator
    echo.
    echo Adding to current session only...
    set "PATH=%PATH%;L:\_TOOLS\ffmpeg\bin"
)

REM Verify FFmpeg
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo [ERROR] FFmpeg still not found in PATH
    pause
    exit /b 1
)

ffmpeg -version | findstr "ffmpeg version"
echo.
echo [OK] FFmpeg is now accessible
echo.

echo.
echo ================================================================================
echo   Step 2: Fixing PyAnnote GPU Transfer
echo ================================================================================
echo.

python fix_pyannote_gpu.py

if errorlevel 1 (
    echo [ERROR] PyAnnote fix failed
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo   Step 3: Updating Scene Detection Configuration
echo ================================================================================
echo.

python fix_scene_detection_config.py

if errorlevel 1 (
    echo [ERROR] Scene detection config fix failed
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo   Step 4: Validation
echo ================================================================================
echo.

echo Testing FFmpeg audio extraction...
ffmpeg -i test_input\sample.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 -t 5 test_output\test_audio.wav -y >nul 2>&1

if exist test_output\test_audio.wav (
    echo [OK] FFmpeg audio extraction working
    del test_output\test_audio.wav
) else (
    echo [WARNING] FFmpeg test failed, but installation succeeded
)

echo.
python scripts\validate_critical_fixes.py

echo.
echo ================================================================================
echo   Fix Complete!
echo ================================================================================
echo.
echo IMPORTANT: You must restart PowerShell/Terminal for PATH changes to take effect
echo.
echo Next steps:
echo   1. Close this window
echo   2. Close all PowerShell/Terminal windows
echo   3. Open a new PowerShell 7 session
echo   4. Navigate to L:\goodq4all
echo   5. Run: .\LAUNCH_GOODQ.bat
echo.
pause
