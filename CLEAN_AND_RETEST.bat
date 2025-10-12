@echo off
REM 🔄 Clean slate test with fixed pipeline
setlocal enabledelayedexpansion

echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║     🔄 MISSION RESTART: Clean Database and Retest            ║
echo ║     Testing with fixed error handling and file persistence   ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

echo ⚠️  WARNING: This will delete all existing scene data!
echo.
set /p CONFIRM="Type YES to continue: "
if /i not "%CONFIRM%"=="YES" (
    echo.
    echo [ABORT] Operation cancelled
    pause
    exit /b 0
)

echo.
echo [1/5] Stopping any running watchdog processes...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *watchdog*" 2>nul

echo [2/5] Clearing memory database...
if exist "L:\goodq4all\data\memory.db" (
    del /F /Q "L:\goodq4all\data\memory.db"
    echo ✓ Memory database cleared
) else (
    echo ℹ No existing memory database
)

echo [3/5] Clearing knowledge graph...
if exist "L:\goodq4all\data\knowledge_graph.db" (
    del /F /Q "L:\goodq4all\data\knowledge_graph.db"
    echo ✓ Knowledge graph cleared
) else (
    echo ℹ No existing knowledge graph
)

echo [4/5] Clearing FAISS indices...
if exist "L:\goodq4all\data\faiss" (
    rmdir /S /Q "L:\goodq4all\data\faiss"
    echo ✓ FAISS indices cleared
) else (
    echo ℹ No existing FAISS indices
)

echo [5/5] Clearing processing temp files...
if exist "L:\goodq4all\data\processing" (
    rmdir /S /Q "L:\goodq4all\data\processing"
    mkdir "L:\goodq4all\data\processing"
    echo ✓ Processing directory cleared
) else (
    mkdir "L:\goodq4all\data\processing"
    echo ℹ Created processing directory
)

echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║     ✓ Database Cleared - Ready for Fresh Test                ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

echo Would you like to start the watchdog to begin processing?
set /p START="Type YES to start watchdog: "
if /i "%START%"=="YES" (
    echo.
    echo [LAUNCH] Starting watchdog...
    start "GoodQ Watchdog" cmd /k "L:\goodq4all\START_WATCHDOG.bat"
    echo.
    echo ✓ Watchdog started in new window
    echo.
    echo Monitor progress with:
    echo   - L:\goodq4all\MONITOR_WATCHDOG.bat
    echo   - L:\goodq4all\VALIDATE_OUTPUT.bat
)

echo.
echo Press any key to exit...
pause >nul
