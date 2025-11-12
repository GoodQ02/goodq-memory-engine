@echo off
REM ================================================================================
REM GPU Setup Validation Script
REM Tests CUDA availability in all GPU-capable step environments
REM ================================================================================

setlocal enabledelayedexpansion

echo.
echo ================================================================================
echo  GoodQ4All - GPU Setup Validation
echo ================================================================================
echo.

set PASSED=0
set FAILED=0

REM Test each GPU-capable environment
set "ENVS=audio_diarize audio_transcribe emotion_classify face_embed"

for %%E in (%ENVS%) do (
    echo Testing %%E...
    call conda activate %%E 2>nul
    if errorlevel 1 (
        echo   ❌ Environment not found: %%E
        set /a FAILED+=1
    ) else (
        REM Test PyTorch + CUDA
        python -c "import torch; print(f'  ✓ PyTorch {torch.__version__}'); assert torch.cuda.is_available(), 'CUDA not available'; print(f'  ✓ CUDA {torch.version.cuda}'); print(f'  ✓ GPU: {torch.cuda.get_device_name(0)}'); print(f'  ✓ Memory: {torch.cuda.get_device_properties(0).total_memory/1e9:.1f}GB')" 2>nul
        if errorlevel 1 (
            echo   ❌ CUDA not available in %%E
            set /a FAILED+=1
        ) else (
            set /a PASSED+=1
        )
    )
    echo.
)

echo ================================================================================
echo  Results
echo ================================================================================
echo.
echo Passed: %PASSED%
echo Failed: %FAILED%
echo.

if %FAILED% GTR 0 (
    echo ❌ Some environments failed validation
    echo.
    echo Run scripts\setup_gpu_environments.bat to fix
    exit /b 1
) else (
    echo ✅ All GPU environments validated successfully!
    echo.
    echo GPU acceleration is ready for:
    echo   - Audio diarization (PyAnnote)
    echo   - Audio transcription (Faster Whisper)
    echo   - Face embedding (FaceNet)
    echo   - Emotion classification (RoBERTa)
    echo.
    exit /b 0
)
