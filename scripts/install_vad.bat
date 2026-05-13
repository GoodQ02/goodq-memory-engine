@echo off
echo ================================================================================
echo Installing Silero VAD for Audio Diarization
echo ================================================================================
echo.
echo This will install Silero VAD in the audio_diarize environment
echo.
pause

call "%~dp0_lib\\interpreter_bindings.bat"

echo.
echo Installing dependencies...
"%CONDA_EXE%" run -n goodq_audio_diarize pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118

echo.
echo Installing soundfile for audio I/O...
"%CONDA_EXE%" run -n goodq_audio_diarize pip install soundfile

echo.
echo ================================================================================
echo Testing VAD Installation
echo ================================================================================

"%CONDA_EXE%" run -n goodq_audio_diarize python -c "import torch; print('PyTorch:', torch.__version__); print('CUDA available:', torch.cuda.is_available())"
"%CONDA_EXE%" run -n goodq_audio_diarize python -c "import torchaudio; print('TorchAudio:', torchaudio.__version__)"
"%CONDA_EXE%" run -n goodq_audio_diarize python -c "import soundfile; print('SoundFile:', soundfile.__version__)"

echo.
echo Testing Silero VAD model download...
"%CONDA_EXE%" run -n goodq_audio_diarize python -c "model, utils = torch.hub.load('snakers4/silero-vad', 'silero_vad', force_reload=False); print('VAD model loaded successfully')"

echo.
echo ================================================================================
echo Installation Complete!
echo ================================================================================
echo.
echo VAD is now ready to use for audio diarization preprocessing
echo This will dramatically reduce processing time by filtering out silence and noise
echo.
pause
