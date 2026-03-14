@echo off
REM GoodQ4All vLLM Service Startup Script
REM Starts the current systemd-backed vLLM primary + Ollama fallback services

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
    pause
    exit /b 1
)

REM Preferred: systemd services (ensure sudoers allows NOPASSWD for these commands)
echo WSL is running
echo Starting vLLM via systemd (if available)...
wsl -d %GOODQ_WSL_DISTRO% -- sudo systemctl start vllm-llama1b
wsl -d %GOODQ_WSL_DISTRO% -- sudo systemctl start ollama

REM Fail visibly if the expected systemd service is not active.
wsl -d %GOODQ_WSL_DISTRO% -- sudo systemctl is-active --quiet vllm-llama1b
if errorlevel 1 (
    echo ERROR: vllm-llama1b systemd service is not active.
    echo Expected path: scripts/wsl/install_vllm_service.sh inside the repo checkout.
    echo Check status: wsl -d %GOODQ_WSL_DISTRO% -- sudo systemctl status vllm-llama1b --no-pager
    pause
    exit /b 1
)

echo.
echo ========================================
echo vLLM Services Starting...
echo ========================================
echo.
echo Llama 1B (Speed):     http://localhost:38005/v1
echo Ollama (Fallback):    http://localhost:31434/v1
echo.
echo Services are starting in the background.
echo It may take 30-60 seconds for the primary model to fully load.
echo.
echo Check status: "%REPO_ROOT%\\scripts\\status_vllm_servers.bat"
echo.
pause
