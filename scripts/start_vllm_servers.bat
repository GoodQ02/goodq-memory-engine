@echo off
REM GoodQ4All vLLM Service Startup Script
REM Starts the current systemd-backed vLLM primary and keeps WSL alive for it.

call "%~dp0_lib\\interpreter_bindings.bat"
for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"

echo ========================================
echo GoodQ4All vLLM Server Startup
echo ========================================
echo.

echo Checking WSL status...
wsl --status >nul 2>&1
if errorlevel 1 (
    echo ERROR: WSL is not running or not installed
    echo Please start WSL first
    if /I not "%GOODQ_NO_PAUSE%"=="1" pause
    exit /b 1
)

echo WSL is running
echo Starting vLLM via systemd...
wsl -d %GOODQ_WSL_DISTRO% -u root -- systemctl start vllm-llama1b

REM WSL tears down the VM when its last Windows wsl.exe client exits. Keep one
REM lightweight Windows-side anchor alive so systemd vLLM can finish warmup.
echo Starting WSL keepalive anchor...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter 'Name=''wsl.exe''' | Where-Object { $_.CommandLine -match 'goodq-vllm-keepalive' } | Select-Object -First 1 | ForEach-Object { exit 0 }; exit 1"
if errorlevel 1 (
    start "GoodQ WSL keepalive" /min wsl -d %GOODQ_WSL_DISTRO% -- bash -lc "exec -a goodq-vllm-keepalive sleep infinity"
) else (
    echo Reusing existing WSL keepalive anchor.
)

REM Ollama is an optional fallback. Start it when installed, but do not make the
REM primary vLLM path depend on it.
wsl -d %GOODQ_WSL_DISTRO% -u root -- bash -lc "systemctl list-unit-files ollama.service >/dev/null 2>&1 && systemctl start ollama || true"

REM Fail visibly if the expected systemd service is not active.
wsl -d %GOODQ_WSL_DISTRO% -u root -- systemctl is-active --quiet vllm-llama1b
if errorlevel 1 (
    echo ERROR: vllm-llama1b systemd service is not active.
    echo Expected path: scripts/wsl/install_vllm_service.sh inside the repo checkout.
    echo Check status: wsl -d %GOODQ_WSL_DISTRO% -u root -- systemctl status vllm-llama1b --no-pager
    if /I not "%GOODQ_NO_PAUSE%"=="1" pause
    exit /b 1
)

echo Waiting up to 90 seconds for the vLLM speed endpoint...
powershell -NoProfile -Command "$deadline=(Get-Date).AddSeconds(90); do { try { $response=Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 http://127.0.0.1:38005/v1/models; if ($response.StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep -Seconds 2 } while ((Get-Date) -lt $deadline); exit 1"
if errorlevel 1 (
    echo ERROR: vLLM speed endpoint did not become ready on http://127.0.0.1:38005/v1/models.
    echo Check status: "%REPO_ROOT%\scripts\status_vllm_servers.bat"
    if /I not "%GOODQ_NO_PAUSE%"=="1" pause
    exit /b 1
)

echo.
echo ========================================
echo vLLM Services Ready...
echo ========================================
echo.
echo vLLM Primary:         http://127.0.0.1:38005/v1
echo Ollama (Fallback):    http://localhost:11434/v1 (or fallback: http://localhost:31434/v1)
echo.
echo The primary endpoint responded after its bounded readiness check.
echo.
echo Check status: "%REPO_ROOT%\\scripts\\status_vllm_servers.bat"
echo.
if /I not "%GOODQ_NO_PAUSE%"=="1" pause
