@echo off
REM GoodQ4All vLLM Server Stop Script
REM Stops all vLLM servers in WSL

echo ========================================
echo Stopping vLLM Servers
echo ========================================
echo.

wsl pkill -f vllm.entrypoints

echo.
echo All vLLM servers stopped.
echo Ollama remains running if started separately.
echo.
pause
