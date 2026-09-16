@echo off
setlocal
set "DEV_OFF_EXIT_CODE=0"
pushd "%~dp0" || exit /b 1
set "GOODQ_MODE_ROOT=%~dp0"
REM GoodQ4All - Game Mode (Dev Off)
REM Stops GPU-backed and API services while retaining loopback Qdrant for a fast Dev On return.
REM Never terminate an automatically discovered, potentially unrelated distro.
set "GOODQ_MODE_WSL="
for /f "delims=" %%D in ('powershell -NoProfile -Command ". (Join-Path $env:GOODQ_MODE_ROOT 'scripts\_lib\interpreter_bindings.ps1'); Get-GoodQWslDistro -RequireConfigured"') do set "GOODQ_MODE_WSL=%%D"
if not defined GOODQ_MODE_WSL goto :blocked
set "GOODQ_WSL_DISTRO=%GOODQ_MODE_WSL%"
call "%~dp0scripts\_lib\interpreter_bindings.bat"

call :dashboard -Event start

echo [DEV OFF] Deactivating local agent services...

REM Request the existing owner to drain; never release dependencies first.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_goodq_dev.ps1" -StopCurrent
if errorlevel 1 (
    call :dashboard -Event node -Node RUNTIME -State blocked -Message "drain is unverified; compute dependencies preserved"
    goto :blocked
)
call :dashboard -Event node -Node API -State released -Message "owning runtime drained or already absent"
call :dashboard -Event node -Node WATCHDOG -State released -Message "owning runtime drained or already absent"

REM Only a verified drain permits the GoodQ compute controls below.
set "GOODQ_CALLER_NO_PAUSE=%GOODQ_NO_PAUSE%"
set "GOODQ_NO_PAUSE=1"
call "%~dp0scripts\stop_vllm_servers.bat"
set "VLLM_EXIT_CODE=%ERRORLEVEL%"
set "GOODQ_NO_PAUSE=%GOODQ_CALLER_NO_PAUSE%"
set "GOODQ_CALLER_NO_PAUSE="
if not "%VLLM_EXIT_CODE%"=="0" (
    call :dashboard -Event node -Node vLLM -State blocked -Message "stop control reported a failure"
    goto :blocked
)
call :dashboard -Event node -Node vLLM -State released -Message "service, Linux/Windows endpoint and selected keepalive release verified"

REM Release the configured GoodQ compute extension; other distro owners are separate.
wsl --terminate "%GOODQ_WSL_DISTRO%"
if errorlevel 1 (
    call :dashboard -Event node -Node "WSL AUDIO" -State blocked -Message "WSL shutdown command failed"
    goto :blocked
)
powershell -NoProfile -Command "$running=@(wsl.exe --list --running --quiet); if ($LASTEXITCODE -ne 0) { exit 1 }; $names=@($running | ForEach-Object { ($_ -replace [char]0, '').Trim() }); if ($names -contains $env:GOODQ_WSL_DISTRO) { exit 1 }; exit 0"
if errorlevel 1 (
    call :dashboard -Event node -Node "WSL AUDIO" -State blocked -Message "WSL distribution is still running"
    goto :blocked
)
call :dashboard -Event node -Node "WSL AUDIO" -State released -Message "compute extension is stopped"

REM Qdrant remains available on loopback: it uses no GPU and avoids an index-service restart.
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 http://127.0.0.1:6333/collections | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
    call :dashboard -Event node -Node QDRANT -State blocked -Message "retained loopback store is not reachable"
    goto :blocked
)
call :dashboard -Event node -Node QDRANT -State retained -Message "loopback store remains available"

REM Unload active Ollama models from GPU VRAM if Ollama is running
where ollama >nul 2>&1
if not errorlevel 1 (
    powershell -NoProfile -Command "try { (ollama ps) | Select-Object -Skip 1 | ForEach-Object { $name = ($_ -split '\s+')[0]; if ($name) { ollama stop $name } } } catch {}"
)

REM Display actual GPU process and memory state without treating desktop ownership as failure.
where nvidia-smi >nul 2>&1
if errorlevel 1 (
    call :dashboard -Event node -Node "NVIDIA-SMI" -State warn -Message "GPU telemetry utility is unavailable"
) else (
    call :dashboard -Event node -Node "NVIDIA-SMI" -State check -Message "GPU process and memory snapshot follows"
    nvidia-smi
)

echo [DEV OFF] GoodQ runtime drained and its compute extension stopped.
echo [DEV OFF] Whole-workstation release, including Hermes and both Ollama lanes, remains unverified.
call :dashboard -Event node -Node WORKSTATION -State warn -Message "Hermes and dual-lane model release are not yet qualified; Qdrant retained"
goto :finish

:blocked
call :dashboard -Event final -State blocked -Message "Open Desktop was not fully released. See the first blocked node above."
set "DEV_OFF_EXIT_CODE=1"
goto :finish

:dashboard
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev_mode_dashboard.ps1" -Mode dev-off %*
exit /b %errorlevel%

:finish
popd
if /i not "%GOODQ_NO_PAUSE%"=="1" pause
exit /b %DEV_OFF_EXIT_CODE%

