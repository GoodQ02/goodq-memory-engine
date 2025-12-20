@echo off
REM =============================================================================
REM  Audio GPU Optimization Test Suite
REM  Quick launcher for GPU-accelerated audio pipeline testing
REM =============================================================================

call "%~dp0_lib\\interpreter_bindings.bat"

cd /d L:\goodq4all

echo.
echo ================================================================================
echo   Audio GPU Optimization Test Suite
echo ================================================================================
echo.
echo This will test GPU-accelerated audio processing (diarization + transcription)
echo.
echo Available tests:
echo   1. Full pipeline test with GPU monitoring
echo   2. Audio step unit tests
echo   3. Performance report generation
echo   4. Real-time GPU monitor
echo.
pause

"%CONDA_EXE%" run -n goodq_zenml python scripts\test_audio_gpu_optimization.py

echo.
echo ================================================================================
echo   Test Complete
echo ================================================================================
echo.
pause
