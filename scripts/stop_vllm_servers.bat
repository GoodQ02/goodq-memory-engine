@echo off
REM GoodQ4All vLLM Server Stop Script
REM Stops the canonical systemd vLLM service, its keepalive anchor, and stale manual vLLM processes.

call "%~dp0_lib\\interpreter_bindings.bat"

echo ========================================
echo Stopping vLLM Servers
echo ========================================
echo.

wsl -d %GOODQ_WSL_DISTRO% -u root -- systemctl stop vllm-llama1b
wsl -d %GOODQ_WSL_DISTRO% -u root -- pkill -KILL -f "[v]llm.entrypoints.openai.api_server"
wsl -d %GOODQ_WSL_DISTRO% -u root -- pkill -KILL -f "[V]LLM::EngineCore"
wsl -d %GOODQ_WSL_DISTRO% -- pkill -KILL -f "[g]oodq-vllm-keepalive"

echo.
echo vLLM systemd service, keepalive anchor, and stale manual vLLM processes cleared.
echo Ollama remains running if started separately.
echo.
if /I not "%GOODQ_NO_PAUSE%"=="1" pause
