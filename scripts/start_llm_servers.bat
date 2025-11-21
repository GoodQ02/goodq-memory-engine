@echo off
REM ============================================================================
REM GoodQ4All - Start All LLM Servers (Windows Launcher)
REM ============================================================================
REM Starts all vLLM servers in WSL and verifies connectivity
REM Usage: start_llm_servers.bat
REM ============================================================================

setlocal EnableDelayedExpansion

echo.
echo ========================================================================
echo  GoodQ4All - Starting LLM Server Infrastructure
echo ========================================================================
echo.

REM Check if WSL is available
wsl --list >nul 2>&1
if errorlevel 1 (
    echo [ERROR] WSL not found! Please install WSL first.
    pause
    exit /b 1
)

echo [1/4] Copying startup script to WSL...
wsl bash -c "mkdir -p ~/goodq4all/scripts/wsl"
wsl bash -c "cp /mnt/l/goodq4all/scripts/wsl/start_all_vllm.sh ~/goodq4all/scripts/wsl/"
wsl bash -c "chmod +x ~/goodq4all/scripts/wsl/start_all_vllm.sh"

echo [2/4] Starting vLLM servers in WSL...
echo.
wsl bash -c "~/goodq4all/scripts/wsl/start_all_vllm.sh"

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start vLLM servers
    pause
    exit /b 1
)

echo.
echo [3/4] Waiting for services to stabilize...
timeout /t 5 /nobreak >nul

echo [4/4] Testing connectivity from Windows...
echo.

python L:\goodq4all\scripts\test_llm_connectivity.py

if errorlevel 1 (
    echo.
    echo [WARNING] Some connectivity tests failed
    echo Check the output above for details
) else (
    echo.
    echo [SUCCESS] All LLM servers are online and accessible!
)

echo.
echo ========================================================================
echo  LLM Infrastructure Ready
echo ========================================================================
echo.
echo  Available Endpoints:
echo    - Llama 1B (Speed):      http://localhost:8005/v1/
echo    - Llama 3B (Balanced):   http://localhost:8004/v1/
echo    - Phi-3.5 (Long Context): http://localhost:8001/v1/
echo    - Ollama (Fallback):     http://localhost:11434/v1/
echo.
echo  Monitor:  wsl bash -c "watch -n 2 'nvidia-smi'"
echo  Logs:     wsl bash -c "tail -f ~/vllm_server/logs/*.log"
echo  Stop All: wsl bash -c "pkill -f 'vllm.entrypoints'"
echo.
echo ========================================================================

pause
