@echo off
REM Comprehensive Clean Run Monitor
REM Tracks ingestion progress with detailed statistics

title GoodQ Clean Run Monitor

:MONITOR_LOOP
cls
echo.
echo ╔══════════════════════════════════════════════════════════════════════════╗
echo ║                    GOODQ CLEAN RUN - PROGRESS MONITOR                    ║
echo ╚══════════════════════════════════════════════════════════════════════════╝
echo.

REM Get current time
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c-%%a-%%b)
for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a:%%b)
echo [%mydate% %mytime%] Monitoring ingestion progress...
echo.

REM Check watchdog process
echo [1] Checking watchdog status...
tasklist /FI "IMAGENAME eq python.exe" /FO CSV | find /I "python.exe" >nul
if errorlevel 1 (
    echo     [ERROR] Watchdog process not found!
    echo.
    echo     Press any key to restart watchdog...
    pause >nul
    start START_WATCHDOG.bat
    timeout /t 10 /nobreak >nul
    goto MONITOR_LOOP
) else (
    echo     [OK] Watchdog is running
)
echo.

REM Check processing directory
echo [2] Files in processing directory...
if exist "L:\goodq4all\data\processing\*.*" (
    dir "L:\goodq4all\data\processing" /B /S | find /C ":" >nul 2>&1
    if not errorlevel 1 (
        echo     [INFO] Files being processed
        dir "L:\goodq4all\data\processing" /B | find ".mp4"
    )
) else (
    echo     [INFO] Processing directory empty
)
echo.

REM Check import_inbox
echo [3] Files waiting in import_inbox...
if exist "L:\goodq4all\import_inbox\*.mp4" (
    dir "L:\goodq4all\import_inbox\*.mp4" /B
) else (
    echo     [INFO] Inbox empty - all files processed or in progress
)
echo.

REM Check database stats
echo [4] Database statistics...
python -c "import sqlite3; conn=sqlite3.connect('L:/goodq4all/data/memory.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM embeddings'); emb=c.fetchone()[0]; c.execute('SELECT COUNT(*) FROM scenes'); sc=c.fetchone()[0]; c.execute('SELECT COUNT(*) FROM segments'); seg=c.fetchone()[0]; print(f'     Embeddings: {emb}'); print(f'     Scenes: {sc}'); print(f'     Segments: {seg}'); conn.close()" 2>nul
if errorlevel 1 (
    echo     [WARN] Could not read database stats
)
echo.

REM Check latest log entries
echo [5] Latest watchdog log entries...
if exist "L:\goodq4all\logs\watchdog.log" (
    powershell -Command "Get-Content 'L:\goodq4all\logs\watchdog.log' -Tail 5 | ForEach-Object { Write-Host \"     $_\" }"
)
echo.

echo ════════════════════════════════════════════════════════════════════════════
echo.
echo Press Ctrl+C to stop monitoring, or wait for auto-refresh...
echo.

REM Wait 30 seconds before next check
timeout /t 30 /nobreak >nul

goto MONITOR_LOOP
