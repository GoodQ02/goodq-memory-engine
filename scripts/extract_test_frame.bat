@echo off
REM Extract test frame for vision testing

echo ================================================================================
echo   GoodQ4All - Test Frame Extraction
echo ================================================================================
echo.

cd /d L:\goodq4all

python scripts\extract_test_frame.py

pause
