@echo off
REM Test Audio Diarization - Component Breakdown
call "%~dp0_lib\\interpreter_bindings.bat"
echo ================================================================================
echo GoodQ4All - Audio Diarization Component Testing
echo ================================================================================
echo.
echo This will test each component of audio diarization individually
echo to identify performance bottlenecks and stalls.
echo.
echo Tests to run:
echo   1. GPU Detection and Configuration
echo   2. Pipeline Loading (PyAnnote model)
echo   3. Audio Duration Detection
echo   4. Audio Chunk Extraction (FFmpeg)
echo   5. Single Chunk Diarization (short sample)
echo   6. Multi-Chunk Processing (long sample)
echo   7. Speaker Embedding Extraction
echo   8. Segment Merging Logic
echo.
pause
echo.

cd /d L:\goodq4all

"%CONDA_EXE%" run -n goodq_audio_diarize python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to run Python in audio_diarize environment
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo Running Audio Diarization Component Tests
echo ================================================================================
echo.

"%CONDA_EXE%" run -n goodq_audio_diarize python scripts\test_audio_diarize_breakdown.py

echo.
echo ================================================================================
echo Test Complete - Check output above for bottlenecks
echo ================================================================================
echo.
pause
