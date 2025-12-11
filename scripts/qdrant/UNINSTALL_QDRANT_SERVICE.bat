@echo off
REM GoodQ4All - Uninstall Qdrant Windows Service
REM This requires Administrator privileges

echo.
echo ========================================
echo   Uninstall Qdrant Windows Service
echo ========================================
echo.

REM Check for admin rights
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] This script requires Administrator privileges!
    echo Please right-click and select "Run as Administrator"
    echo.
    pause
    exit /b 1
)

echo Stopping Qdrant service...
net stop GoodQ_Qdrant

echo.
echo Removing Qdrant service...
L:\goodq4all\vendor\nssm.exe remove GoodQ_Qdrant confirm

echo.
echo [OK] Qdrant service uninstalled
echo.
echo Note: Data remains at L:\_DATA\qdrant_storage
echo To completely remove Qdrant, delete:
echo   - L:\goodq4all\vendor\qdrant
echo   - L:\_DATA\qdrant_storage
echo.
pause
