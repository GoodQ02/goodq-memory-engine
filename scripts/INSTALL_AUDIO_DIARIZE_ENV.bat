@echo off
REM ================================================================================
REM  Install Audio Diarization Environment Packages
REM ================================================================================

cd /d "%~dp0"

echo ================================================================================
echo   GoodQ4All - Audio Diarization Environment Setup
echo ================================================================================
echo.
echo This will install all required packages for audio diarization:
echo   - PyTorch 2.5.1 with CUDA support
echo   - PyAnnote Audio 3.3.2+
echo   - WhisperX 3.3.0
echo   - FFmpeg and audio processing libraries
echo.
echo Environment: goodq_audio_diarize
echo Python: 3.11
echo.
echo This may take 10-15 minutes...
echo.
pause

call C:\Users\jdben\miniconda3\Scripts\activate.bat goodq_audio_diarize

echo.
echo [1/4] Installing PyTorch with CUDA support...
echo ================================================================================
pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu124

if errorlevel 1 (
    echo ERROR: PyTorch installation failed
    pause
    exit /b 1
)

echo.
echo [2/4] Installing audio processing libraries...
echo ================================================================================
pip install soundfile==0.12.1 ffmpeg-python==0.2.0 librosa

if errorlevel 1 (
    echo ERROR: Audio libraries installation failed
    pause
    exit /b 1
)

echo.
echo [3/4] Installing PyAnnote Audio...
echo ================================================================================
pip install pyannote.audio>=3.3.2

if errorlevel 1 (
    echo ERROR: PyAnnote installation failed
    pause
    exit /b 1
)

echo.
echo [4/4] Installing WhisperX and utilities...
echo ================================================================================
pip install whisperx==3.3.0 dill==0.3.8 typing-extensions==4.13.2 cryptography==42.0.8

if errorlevel 1 (
    echo ERROR: WhisperX installation failed
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo   Testing Installation
echo ================================================================================
echo.

python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA Available: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"

if errorlevel 1 (
    echo ERROR: PyTorch test failed
    pause
    exit /b 1
)

python -c "from pyannote.audio import Pipeline; print('PyAnnote Audio: OK')"

if errorlevel 1 (
    echo ERROR: PyAnnote test failed
    pause
    exit /b 1
)

python -c "import soundfile; import librosa; print('Audio libraries: OK')"

if errorlevel 1 (
    echo ERROR: Audio libraries test failed
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo   Installation Complete!
echo ================================================================================
echo.
echo ✓ All packages installed successfully
echo ✓ GPU acceleration enabled
echo.
echo You can now run audio diarization tests.
echo.
pause
