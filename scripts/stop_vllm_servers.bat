@echo off
REM GoodQ4All vLLM Server Stop Script
REM Stops all vLLM servers in WSL

call "%~dp0_lib\\interpreter_bindings.bat"

echo ========================================
echo Stopping vLLM Servers
echo ========================================
echo.

wsl -d %GOODQ_WSL_DISTRO% -- pkill -f vllm.entrypoints

echo.
echo All vLLM servers stopped.
echo Ollama remains running if started separately.
echo.
pause
