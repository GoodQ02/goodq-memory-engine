@echo off
echo ================================================================================
echo Installing Silero VAD for Audio Diarization
echo ================================================================================
echo.
echo This will install Silero VAD in the audio_diarize environment
echo.
pause

call conda activate goodq_audio_diarize

echo.
echo Installing dependencies...
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118

echo.
echo Installing soundfile for audio I/O...
pip install soundfile

echo.
echo ================================================================================
echo Testing VAD Installation
echo ================================================================================

python -c "import torch; print('PyTorch:', torch.__version__); print('CUDA available:', torch.cuda.is_available())"
python -c "import torchaudio; print('TorchAudio:', torchaudio.__version__)"
python -c "import soundfile; print('SoundFile:', soundfile.__version__)"

echo.
echo Testing Silero VAD model download...
python -c "model, utils = torch.hub.load('snakers4/silero-vad', 'silero_vad', force_reload=False); print('VAD model loaded successfully')"

echo.
echo ================================================================================
echo Installation Complete!
echo ================================================================================
echo.
echo VAD is now ready to use for audio diarization preprocessing
echo This will dramatically reduce processing time by filtering out silence and noise
echo.
pause
