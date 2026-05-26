@echo off
REM GoodQ4All - Vision Stack GPU Optimization Launcher

echo ================================================================================
echo   GoodQ4All - Vision Stack GPU Optimization
echo ================================================================================
echo.
echo This will optimize all vision processing for GPU acceleration:
echo   - Face Detection (FaceNet + MTCNN)
echo   - Emotion Classification (RoBERTa)
echo   - Object Detection (YOLO)
echo   - Optical Character Recognition (EasyOCR)
echo.
echo Estimated time: 15-20 minutes
echo ================================================================================
echo.

REM Run optimization script
call "%~dp0_lib\\interpreter_bindings.bat"
for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"
pushd "%REPO_ROOT%" >nul
set "PYTHONPATH=%CD%"
"%CONDA_EXE%" run -n %GOODQ_CONDA_ENV% python scripts\optimize_vision_gpu.py
popd >nul

pause
