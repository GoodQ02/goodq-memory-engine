@echo off
setlocal enabledelayedexpansion

:LOOP
cls
echo ===============================================================================
echo   GoodQ4All - Live Ingestion Monitor (Real-time)
echo ===============================================================================
echo.
echo [%date% %time%]
echo.

REM Check running processes
echo === RUNNING PROCESSES ===
powershell -Command "Get-Process python -ErrorAction SilentlyContinue | Where-Object {$_.CommandLine -like '*watchdog*' -or $_.CommandLine -like '*ingestion*'} | Format-Table Id, @{N='CPU';E={$_.CPU}}, @{N='Memory(MB)';E={[math]::Round($_.WorkingSet64/1MB,1)}}, @{N='Runtime';E={(Get-Date) - $_.StartTime}} -AutoSize"
echo.

REM Check processing directories
echo === PROCESSING VIDEOS ===
if exist "L:\_DATA\GoodQ_Data\processing" (
    for /d %%D in ("L:\_DATA\GoodQ_Data\processing\*") do (
        echo [%%~nD]
        if exist "%%D\status.json" (
            powershell -Command "Get-Content '%%D\status.json' | ConvertFrom-Json | Select-Object video_id, current_phase, progress_pct | Format-List"
        )
        if exist "%%D\video" (
            powershell -Command "Get-ChildItem '%%D\video' -Recurse -File | Measure-Object -Property Length -Sum | Select-Object @{N='Files';E={$_.Count}}, @{N='Size(MB)';E={[math]::Round($_.Sum/1MB,1)}}"
        )
        echo.
    )
) else (
    echo No processing directory found
)

REM Show recent log activity
echo === RECENT LOG ACTIVITY (last 10 lines) ===
powershell -Command "$log = Get-ChildItem 'L:\goodq4all\logs' -Filter '*.log' | Sort-Object LastWriteTime -Descending | Select-Object -First 1; Write-Host \"Log: $($log.Name) (Updated: $($log.LastWriteTime))\" -ForegroundColor Cyan; Get-Content $log.FullName -Tail 10"
echo.

echo ===============================================================================
echo Press Ctrl+C to exit, or wait 5 seconds for refresh...
timeout /t 5 /nobreak >nul
goto LOOP
