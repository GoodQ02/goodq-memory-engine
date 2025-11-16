@echo off
REM GoodQ4All vLLM Server Startup Script
REM Starts vLLM servers in WSL for AI orchestration

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

echo WSL is running
echo.
echo Starting vLLM servers...
echo.

REM Start Llama 1B (Speed - Port 8003)
echo [1/2] Starting Llama-3.2-1B (Ultra-Fast: 178 tok/s)...
wsl ~/vllm_server/scripts/start_llama1b.sh
timeout /t 3 /nobreak >nul

REM Start Llama 3B (Balanced - Port 8004)
echo [2/2] Starting Llama-3.2-3B (Balanced: 82 tok/s)...
wsl ~/vllm_server/scripts/start_llama3b.sh
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo vLLM Servers Starting...
echo ========================================
echo.
echo Llama 1B (Speed):     http://localhost:8003/v1
echo Llama 3B (Balanced):  http://localhost:8004/v1
echo Ollama (Fallback):    http://localhost:11434/v1
echo.
echo Servers are starting in the background.
echo It may take 30-60 seconds for models to fully load.
echo.
echo Check status: python L:\goodq4all\scripts\test_llm_client.py
echo.
pause
