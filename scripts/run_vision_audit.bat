@echo off
REM GoodQ4All - Vision Pipeline Audit

echo ================================================================================
echo   GoodQ4All - Vision Pipeline Functionality Audit
echo ================================================================================
echo.
echo This will test all vision processing components:
echo   - Face Detection
echo   - Emotion Classification  
echo   - Object Detection
echo   - Image Embeddings (CLIP + DINO)
echo   - Image Captioning
echo   - GPU Utilization
echo.
echo Estimated time: 5-10 minutes
echo ================================================================================
echo.

cd /d L:\goodq4all

python scripts\audit_vision_pipeline.py

pause
