@echo off
setlocal ENABLEDELAYEDEXPANSION

REM Golden launcher: prepares envs, runs health check, starts API, pipeline, dashboard, and UI.

REM Resolve repo root (one level up from this script)
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%.." >NUL
set "REPO=%CD%"

REM Pick PowerShell (prefer pwsh, fallback to Windows PowerShell)
where pwsh >NUL 2>&1 && (set "PS_EXE=pwsh") || (set "PS_EXE=powershell")

echo [golden] Repo: %REPO%

echo [golden] Preparing step envs (link project if needed)...
"%PS_EXE%" -NoProfile -ExecutionPolicy Bypass -File "scripts\prepare_step_envs.ps1" -EnvPrefix goodq -LinkProject
if errorlevel 1 (
  echo [golden] prepare_step_envs failed. Check conda install / envs. & goto :done
)

echo [golden] Health check...
"%PS_EXE%" -NoProfile -ExecutionPolicy Bypass -File "scripts\mission_health_check.ps1" -EnvPrefix goodq

echo [golden] Starting Retrieval API on 127.0.0.1:8000 ...
start "GoodQ Retrieval API" "%PS_EXE%" -NoProfile -ExecutionPolicy Bypass -File "scripts\start_api.ps1" -BindAddress 127.0.0.1 -Port 8000

echo [golden] Launching ZenML pipeline and dashboard...
start "ZenML Launch" "%PS_EXE%" -NoProfile -ExecutionPolicy Bypass -File "scripts\mission_launch.ps1" -Mode pipeline -EnvPrefix goodq -OpenDashboard

REM Optional: start Memory Explorer UI if present
if exist "L:\memory-explorer-ui\package.json" (
  echo [golden] Starting Memory Explorer UI...
  start "Memory Explorer UI" cmd /c "cd /d L:\memory-explorer-ui && npm run dev"
) else (
  echo [golden] UI folder not found at L:\memory-explorer-ui (skipping UI)
)

echo [golden] Opening GoodQ Command Center...
start "GoodQ Command Center" "%PS_EXE%" -NoProfile -ExecutionPolicy Bypass -File "scripts\command_center.ps1" -Refresh



echo [golden] Creating memory backup snapshot...
conda run -n goodq_text_embed python -m goodq4all.cli.memory backup

echo [golden] Generating final memory health report...
for /f "delims=" %%R in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TS=%%R
set REPORT=L:\GoodQ_Data\logs\memory_health_report_%%TS%%.json
conda run -n goodq_text_embed python -m goodq4all.cli.memory health-check --output-file "%REPORT%"
echo [golden] All systems go. Windows will stay open for each service.

:done
popd >NUL
exit /b 0


