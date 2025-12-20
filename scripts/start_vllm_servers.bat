@echo off
REM GoodQ4All vLLM Server Startup Script
REM Starts vLLM servers in WSL for AI orchestration

call "%~dp0_lib\\interpreter_bindings.bat"

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

REM Fallback: only start per-user scripts if systemd service is NOT active
wsl -d %GOODQ_WSL_DISTRO% -- sudo systemctl is-active --quiet vllm-llama1b
if NOT "%ERRORLEVEL%"=="0" (
    echo Systemd not active; starting vLLM via per-user scripts...
    wsl -d %GOODQ_WSL_DISTRO% -- ~/vllm_server/scripts/start_llama1b.sh
    timeout /t 2 /nobreak >nul
    wsl -d %GOODQ_WSL_DISTRO% -- ~/vllm_server/scripts/start_llama3b.sh
    timeout /t 2 /nobreak >nul
)

echo.
echo ========================================
echo vLLM Servers Starting...
echo ========================================
echo.
echo Llama 1B (Speed):     http://localhost:38005/v1
echo Llama 3B (Balanced):  http://localhost:38004/v1
echo Ollama (Fallback):    http://localhost:31434/v1
echo.
echo Servers are starting in the background.
echo It may take 30-60 seconds for models to fully load.
echo.
echo Check status: python L:\goodq4all\scripts\test_llm_client.py
echo.
pause
