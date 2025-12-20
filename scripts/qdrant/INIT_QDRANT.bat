@echo off
REM GoodQ4All - Initialize Qdrant Collections
REM Run this after starting Qdrant for the first time

call "%~dp0..\\_lib\\interpreter_bindings.bat"

echo.
echo ========================================
echo   Initialize Qdrant Collections
echo ========================================
echo.

REM Run initialization script
"%CONDA_EXE%" run -n goodq_core python scripts\init_qdrant_collections.py

echo.
pause
