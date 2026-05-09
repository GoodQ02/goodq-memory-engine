@echo off
REM Direct environment test for audio diarization
cd /d "%~dp0\.."

echo Testing goodq_audio_diarize environment...
echo.

REM Use the current user's standard Miniconda environment path.
set PYTHON_EXE=%USERPROFILE%\miniconda3\envs\goodq_audio_diarize\python.exe

if not exist "%PYTHON_EXE%" (
    echo ERROR: Environment not found at %PYTHON_EXE%
    pause
    exit /b 1
)

echo Using: %PYTHON_EXE%
echo.

"%PYTHON_EXE%" scripts\test_audio_diarize_breakdown.py

pause
