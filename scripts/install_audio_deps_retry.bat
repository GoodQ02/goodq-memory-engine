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

call "%~dp0_lib\\interpreter_bindings.bat"
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"

echo.
echo [1/4] Attempting to install pyannote.audio...
"%CONDA_EXE%" run -n goodq_audio_diarize pip install --retries 10 --timeout 60 pyannote.audio
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: pyannote.audio installation failed, will retry...
    timeout /t 5 >nul
    "%CONDA_EXE%" run -n goodq_audio_diarize pip install --retries 10 --timeout 60 pyannote.audio
)

echo.
echo [2/4] Attempting to install whisperx...
"%CONDA_EXE%" run -n goodq_audio_diarize pip install --retries 10 --timeout 60 whisperx
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: whisperx installation failed, will retry...
    timeout /t 5 >nul
    "%CONDA_EXE%" run -n goodq_audio_diarize pip install --retries 10 --timeout 60 whisperx
)

echo.
echo [3/4] Attempting to install librosa...
"%CONDA_EXE%" run -n goodq_audio_diarize pip install --retries 10 --timeout 60 librosa
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: librosa installation failed, will retry...
    timeout /t 5 >nul
    "%CONDA_EXE%" run -n goodq_audio_diarize pip install --retries 10 --timeout 60 librosa
)

echo.
echo [4/4] Attempting to install ffmpeg-python...
"%CONDA_EXE%" run -n goodq_audio_diarize pip install --retries 10 --timeout 60 ffmpeg-python

echo.
echo ================================================================================
echo Installation Complete
echo ================================================================================
echo.
echo Verifying installation...
"%CONDA_EXE%" run -n goodq_audio_diarize python "%REPO_ROOT%\tests\test_diarize_status.py"

echo.
pause
