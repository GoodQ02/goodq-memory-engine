@echo off
echo ================================================================================
echo GoodQ4All - Audio Pipeline Dependency Install (Network Retry)
echo ================================================================================
echo.
echo This script will retry installing audio diarization dependencies.
echo It will attempt multiple times with delays if network issues occur.
echo.
echo Press CTRL+C to cancel, or
pause

call conda activate goodq_audio_diarize

echo.
echo [1/4] Attempting to install pyannote.audio...
pip install --retries 10 --timeout 60 pyannote.audio
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: pyannote.audio installation failed, will retry...
    timeout /t 5 >nul
    pip install --retries 10 --timeout 60 pyannote.audio
)

echo.
echo [2/4] Attempting to install whisperx...
pip install --retries 10 --timeout 60 whisperx
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: whisperx installation failed, will retry...
    timeout /t 5 >nul
    pip install --retries 10 --timeout 60 whisperx
)

echo.
echo [3/4] Attempting to install librosa...
pip install --retries 10 --timeout 60 librosa
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: librosa installation failed, will retry...
    timeout /t 5 >nul
    pip install --retries 10 --timeout 60 librosa
)

echo.
echo [4/4] Attempting to install ffmpeg-python...
pip install --retries 10 --timeout 60 ffmpeg-python

echo.
echo ================================================================================
echo Installation Complete
echo ================================================================================
echo.
echo Verifying installation...
python L:\goodq4all\tests\test_diarize_status.py

echo.
pause
