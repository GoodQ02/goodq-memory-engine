@echo off
:: GoodQ4All - Vision GPU Setup Launcher
:: Installs CUDA PyTorch for vision environments

setlocal EnableDelayedExpansion

echo.
echo ================================================================================
echo   GoodQ4All - Vision GPU Setup
echo ================================================================================
echo.

:: Get Python from base conda environment
for /f "delims=" %%i in ('where conda 2^>nul') do set CONDA_PATH=%%i

if not defined CONDA_PATH (
    echo [ERROR] Conda not found in PATH
    echo Please ensure Conda is installed and in your PATH
    pause
    exit /b 1
)

:: Get conda base path
for %%i in ("%CONDA_PATH%") do set CONDA_BASE=%%~dpi
set CONDA_BASE=%CONDA_BASE:~0,-1%
for %%i in ("%CONDA_BASE%") do set CONDA_ROOT=%%~dpi
set CONDA_ROOT=%CONDA_ROOT:~0,-8%

:: Use base Python to run the installer
set PYTHON_EXE=%CONDA_ROOT%\python.exe

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python not found at: %PYTHON_EXE%
    pause
    exit /b 1
)

echo Using Python: %PYTHON_EXE%
echo.

:: Run the installer
"%PYTHON_EXE%" "%~dp0install_vision_gpu.py"

if errorlevel 1 (
    echo.
    echo [ERROR] Installation failed
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo   Installation Complete!
echo ================================================================================
echo.
pause
