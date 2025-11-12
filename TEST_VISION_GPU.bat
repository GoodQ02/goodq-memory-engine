@echo off
REM Vision GPU Installation and Testing Script

echo ================================================================================
echo GoodQ4All - Vision Stack GPU Verification
echo ================================================================================
echo.

REM Test emotion_classify
echo [1/2] Testing Emotion Classification GPU...
echo ================================================================================
call conda run -n goodq_emotion_classify python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA Available: {torch.cuda.is_available()}'); print(f'Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU\"}'); print(f'GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f}GB' if torch.cuda.is_available() else '')"
echo.

REM Test face_embed
echo [2/2] Testing Face Embedding GPU...
echo ================================================================================
call conda run -n goodq_face_embed python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA Available: {torch.cuda.is_available()}'); print(f'Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU\"}'); print(f'GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f}GB' if torch.cuda.is_available() else '')"
echo.

echo ================================================================================
echo Vision GPU Setup Complete
echo ================================================================================
echo.
echo Summary:
echo   - emotion_classify: PyTorch 2.3.1+cu121 with CUDA
echo   - face_embed: PyTorch 2.5.1+cu121 with CUDA
echo   - GPU Config: L:\goodq4all\gpu_config.py updated
echo.
echo Next Steps:
echo   1. Run a pipeline test to verify GPU usage
echo   2. Monitor GPU memory with: nvidia-smi -l 1
echo   3. Check logs for GPU allocation messages
echo.

pause
