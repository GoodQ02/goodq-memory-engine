@echo off
REM Extract test frame for vision testing

call "%~dp0_lib\\interpreter_bindings.bat"

echo ================================================================================
echo   GoodQ4All - Test Frame Extraction
echo ================================================================================
echo.

cd /d L:\goodq4all

"%CONDA_EXE%" run -n goodq_core python scripts\extract_test_frame.py

pause
