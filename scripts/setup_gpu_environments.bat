@echo off
REM ================================================================================
REM GPU Environment Setup Script
REM Installs PyTorch with CUDA support in all GPU-capable step environments
REM ================================================================================

echo.
echo ================================================================================
echo  GoodQ4All - GPU Environment Setup
echo ================================================================================
echo.
echo This script will install PyTorch with CUDA 12.4 support in GPU-capable
echo step environments. This will enable GPU acceleration for:
echo   - Audio diarization (PyAnnote)
echo   - Audio transcription (Faster Whisper)
echo   - Face embedding (FaceNet)
echo   - Emotion classification (RoBERTa)
echo   - Image embeddings (CLIP, DINO)
echo   - Object detection/tracking (YOLO)
echo.
echo NOTE: This requires ~5GB download and ~15GB disk space for CUDA libraries
echo.

pause

echo.
echo ================================================================================
echo  Step 1/7: Audio Diarization Environment
echo ================================================================================
echo.
call conda activate goodq_audio_diarize || goto :error

REM Uninstall CPU-only PyTorch
echo Removing CPU-only PyTorch...
pip uninstall -y torch torchaudio torchvision

REM Install CUDA-enabled PyTorch 2.5.1 (matches requirements)
echo Installing PyTorch 2.5.1 with CUDA 12.4...
pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu124

REM Verify CUDA is available
echo Testing CUDA availability...
python -c "import torch; assert torch.cuda.is_available(), 'CUDA not available!'; print(f'✓ CUDA {torch.version.cuda} available on {torch.cuda.get_device_name(0)}')"
if errorlevel 1 goto :error

echo ✓ Audio diarization environment configured
echo.

echo ================================================================================
echo  Step 2/7: Audio Transcription Environment
echo ================================================================================
echo.
call conda activate goodq_audio_transcribe || goto :error

echo Removing CPU-only PyTorch...
pip uninstall -y torch

echo Installing PyTorch 2.3.1 with CUDA 12.1...
pip install torch==2.3.1 --index-url https://download.pytorch.org/whl/cu121

echo Testing CUDA availability...
python -c "import torch; assert torch.cuda.is_available(), 'CUDA not available!'; print(f'✓ CUDA {torch.version.cuda} available on {torch.cuda.get_device_name(0)}')"
if errorlevel 1 goto :error

echo ✓ Audio transcription environment configured
echo.

echo ================================================================================
echo  Step 3/7: Emotion Classification Environment
echo ================================================================================
echo.
call conda activate goodq_emotion_classify || goto :error

echo Removing CPU-only PyTorch...
pip uninstall -y torch torchvision

echo Installing PyTorch 2.3.1 with CUDA 12.1...
pip install torch==2.3.1 torchvision==0.18.1 --index-url https://download.pytorch.org/whl/cu121

echo Testing CUDA availability...
python -c "import torch; assert torch.cuda.is_available(), 'CUDA not available!'; print(f'✓ CUDA {torch.version.cuda} available on {torch.cuda.get_device_name(0)}')"
if errorlevel 1 goto :error

echo ✓ Emotion classification environment configured
echo.

echo ================================================================================
echo  Step 4/7: Face Embedding Environment
echo ================================================================================
echo.
call conda activate goodq_face_embed || goto :error

echo Removing CPU-only PyTorch...
pip uninstall -y torch torchvision

echo Installing PyTorch 2.3.1 with CUDA 12.1...
pip install torch==2.3.1 torchvision==0.18.1 --index-url https://download.pytorch.org/whl/cu121

echo Testing CUDA availability...
python -c "import torch; assert torch.cuda.is_available(), 'CUDA not available!'; print(f'✓ CUDA {torch.version.cuda} available on {torch.cuda.get_device_name(0)}')"
if errorlevel 1 goto :error

echo ✓ Face embedding environment configured
echo.

echo ================================================================================
echo  Step 5/7: Text Embedding Environment
echo ================================================================================
echo.
call conda activate goodq_text_embed || goto :error

REM Check if torch is in requirements
pip list | findstr torch
if errorlevel 1 (
    echo PyTorch not required for this step, skipping...
) else (
    echo Removing CPU-only PyTorch...
    pip uninstall -y torch torchvision
    
    echo Installing PyTorch 2.3.1 with CUDA 12.1...
    pip install torch==2.3.1 torchvision==0.18.1 --index-url https://download.pytorch.org/whl/cu121
    
    echo Testing CUDA availability...
    python -c "import torch; assert torch.cuda.is_available(), 'CUDA not available!'; print(f'✓ CUDA {torch.version.cuda} available on {torch.cuda.get_device_name(0)}')"
    if errorlevel 1 goto :error
)

echo ✓ Text embedding environment configured
echo.

echo ================================================================================
echo  Step 6/7: Object Detection Environment
echo ================================================================================
echo.
call conda activate goodq_object_detect || goto :error

pip list | findstr torch
if errorlevel 1 (
    echo PyTorch not required for this step, skipping...
) else (
    echo Removing CPU-only PyTorch...
    pip uninstall -y torch torchvision
    
    echo Installing PyTorch 2.3.1 with CUDA 12.1...
    pip install torch==2.3.1 torchvision==0.18.1 --index-url https://download.pytorch.org/whl/cu121
    
    echo Testing CUDA availability...
    python -c "import torch; assert torch.cuda.is_available(), 'CUDA not available!'; print(f'✓ CUDA {torch.version.cuda} available on {torch.cuda.get_device_name(0)}')"
    if errorlevel 1 goto :error
)

echo ✓ Object detection environment configured
echo.

echo ================================================================================
echo  Step 7/7: Object Tracking Environment
echo ================================================================================
echo.
call conda activate object_track_yolo || goto :error

pip list | findstr torch
if errorlevel 1 (
    echo PyTorch not required for this step, skipping...
) else (
    echo Removing CPU-only PyTorch...
    pip uninstall -y torch torchvision
    
    echo Installing PyTorch 2.3.1 with CUDA 12.1...
    pip install torch==2.3.1 torchvision==0.18.1 --index-url https://download.pytorch.org/whl/cu121
    
    echo Testing CUDA availability...
    python -c "import torch; assert torch.cuda.is_available(), 'CUDA not available!'; print(f'✓ CUDA {torch.version.cuda} available on {torch.cuda.get_device_name(0)}')"
    if errorlevel 1 goto :error
)

echo ✓ Object tracking environment configured
echo.

echo ================================================================================
echo  GPU SETUP COMPLETE!
echo ================================================================================
echo.
echo All GPU-capable environments have been configured with CUDA support.
echo.
echo Next steps:
echo   1. Run validation script to test all environments
echo   2. Start pipeline to begin GPU-accelerated processing
echo.
echo Validation: scripts\validate_gpu_setup.bat
echo.
pause
exit /b 0

:error
echo.
echo ❌ ERROR: Setup failed at step above
echo.
echo Troubleshooting:
echo   - Ensure NVIDIA drivers are installed (ver 581.80 or newer)
echo   - Check CUDA is accessible: nvidia-smi
echo   - Verify conda environments exist
echo.
pause
exit /b 1
