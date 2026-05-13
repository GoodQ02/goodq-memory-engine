@echo off
setlocal enabledelayedexpansion
call "%~dp0..\\_lib\\interpreter_bindings.bat"
for %%I in ("%~dp0..\\..") do set "REPO_ROOT=%%~fI"
pushd "%REPO_ROOT%" >nul
set "PYTHONPATH=%CD%"

for /f "delims=" %%I in ('"%CONDA_EXE%" run -n %GOODQ_CONDA_ENV% python -c "from steps.common.config_loader import get_runtime_paths, load_configs; print(get_runtime_paths(load_configs({}))['processing'])"') do set "PROCESSING_DIR=%%I"
for /f "delims=" %%I in ('"%CONDA_EXE%" run -n %GOODQ_CONDA_ENV% python -c "from steps.common.config_loader import get_runtime_paths, load_configs; print(get_runtime_paths(load_configs({}))['log_dir'])"') do set "LOG_DIR=%%I"

if not defined PROCESSING_DIR (
    echo Failed to resolve canonical processing directory.
    popd >nul
    exit /b 1
)
if not defined LOG_DIR (
    echo Failed to resolve canonical log directory.
    popd >nul
    exit /b 1
)

set "GOODQ_PROCESSING_DIR=%PROCESSING_DIR%"
set "GOODQ_LOG_DIR=%LOG_DIR%"

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
if exist "%GOODQ_PROCESSING_DIR%" (
    for /d %%D in ("%GOODQ_PROCESSING_DIR%\*") do (
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
powershell -Command "$logDir = $env:GOODQ_LOG_DIR; $log = Get-ChildItem $logDir -Filter '*.log' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if ($null -eq $log) { Write-Host 'No logs found' -ForegroundColor Yellow } else { Write-Host \"Log: $($log.Name) (Updated: $($log.LastWriteTime))\" -ForegroundColor Cyan; Get-Content $log.FullName -Tail 10 }"
echo.

echo ===============================================================================
echo Press Ctrl+C to exit, or wait 5 seconds for refresh...
timeout /t 5 /nobreak >nul
goto LOOP
