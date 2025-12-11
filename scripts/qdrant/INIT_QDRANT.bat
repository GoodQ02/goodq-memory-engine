@echo off
REM GoodQ4All - Initialize Qdrant Collections
REM Run this after starting Qdrant for the first time

echo.
echo ========================================
echo   Initialize Qdrant Collections
echo ========================================
echo.

REM Activate conda environment
call conda activate goodq_core 2>nul
if errorlevel 1 (
    echo [ERROR] Could not activate goodq_core environment
    echo Please run: conda activate goodq_core
    pause
    exit /b 1
)

echo [OK] Environment activated: goodq_core
echo.

REM Run initialization script
python scripts\init_qdrant_collections.py

echo.
pause
