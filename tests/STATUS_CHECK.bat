@echo off
REM Quick status check for GoodQ4All system

title GoodQ4All Status Check

cd /d L:\goodq4all

SET CONDA_PATH=C:\Users\jdben\miniconda3
SET PYTHON_EXE=%CONDA_PATH%\envs\goodq_zenml\python.exe

echo.
echo ================================================================================
echo   GoodQ4All System Status
echo ================================================================================
echo.

"%PYTHON_EXE%" process_manager.py status

echo.
pause
