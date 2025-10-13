@echo off
REM GoodQ Performance Fix - Apply all optimizations
SETLOCAL EnableDelayedExpansion

echo.
echo ╔═══════════════════════════════════════════════════════════════╗
echo ║          🎯 GoodQ Performance Fix & Optimization              ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.

REM Check if Python processes are running
echo [CHECK] Looking for running ingestion processes...
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /FO CSV /NH 2^>nul ^| find /C "python.exe"') do set PROC_COUNT=%%a

if !PROC_COUNT! GTR 0 (
    echo.
    echo ⚠️  WARNING: Found !PROC_COUNT! Python processes running
    echo    Your current ingestion will take ~77 hours at current rate
    echo.
    choice /C YN /M "Stop running processes and apply fixes"
    if errorlevel 2 (
        echo [CANCELLED] No changes made
        pause
        exit /b 0
    )
    
    echo [STOP] Terminating Python processes...
    taskkill /F /IM python.exe /T >nul 2>&1
    timeout /t 2 /nobreak >nul
    echo ✓ Processes stopped
)

echo.
echo [FIX] Applying performance optimizations...
cd /d L:\goodq4all
call conda activate goodq_zenml
python scripts\apply_performance_fixes.py

if errorlevel 1 (
    echo.
    echo ❌ Failed to apply optimizations
    pause
    exit /b 1
)

echo.
echo ╔═══════════════════════════════════════════════════════════════╗
echo ║                     ✅ FIXES APPLIED!                          ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.
echo 📊 Expected improvements:
echo    • Scenes:     2,729 → ~200-300  (90%% reduction)
echo    • Time:       77h → 5-8h        (90%% faster)
echo    • Processing: 102s → 60s/scene  (40%% faster)
echo.
echo.
choice /C YN /M "Clear databases and start fresh test"
if errorlevel 2 (
    echo.
    echo [INFO] Run CLEAR_AND_REINGEST.bat when ready
    pause
    exit /b 0
)

echo.
echo [CLEAR] Clearing databases...
call L:\goodq4all\CLEAR_AND_REINGEST.bat

echo.
echo ╔═══════════════════════════════════════════════════════════════╗
echo ║                  🚀 Ready for Testing!                        ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.
echo Next: Drop a video in import_inbox or run:
echo.
echo   L:\goodq4all\START_WATCHDOG.bat
echo.
pause
