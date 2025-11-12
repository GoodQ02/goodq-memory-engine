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

cd /d L:\goodq4all

REM Run optimization script
python scripts\optimize_vision_gpu.py

pause
