@echo off
REM GoodQ4All - Start Qdrant Vector Database
REM This script starts Qdrant as a foreground process for testing
REM For production, use the Windows Service (install via INSTALL_QDRANT_SERVICE.bat)

echo.
echo ========================================
echo   GoodQ4All - Qdrant Vector Database
echo ========================================
echo.
echo Starting Qdrant on http://localhost:6333...
echo Data directory: L:\_DATA\qdrant_storage
echo.
echo Press Ctrl+C to stop Qdrant
echo.

cd /d L:\goodq4all\vendor\qdrant

REM Start Qdrant with custom config
qdrant.exe --config-path config.yaml

pause
