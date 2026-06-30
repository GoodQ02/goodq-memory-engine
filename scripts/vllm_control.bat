@echo off
setlocal

call "%~dp0_lib\interpreter_bindings.bat"

:menu
cls
echo ========================================
echo GoodQ4All vLLM Control
echo ========================================
echo WSL distro: %GOODQ_WSL_DISTRO%
echo.
echo 1) Status
echo 2) Start vLLM servers
echo 3) Stop vLLM servers
echo 4) Watch vLLM service logs (systemd)
echo 5) Watch vLLM file log (llama-1b)
echo 6) Watch Ollama service logs (systemd)
echo 7) Exit
echo.
set /p choice=Select an option [1-7]: 

if "%choice%"=="1" goto status
if "%choice%"=="2" goto start
if "%choice%"=="3" goto stop
if "%choice%"=="4" goto watch_vllm_systemd
if "%choice%"=="5" goto watch_vllm_file
if "%choice%"=="6" goto watch_ollama
if "%choice%"=="7" goto end
if /I "%choice%"=="q" goto end

goto menu

:status
echo.
echo [INFO] Service status
wsl -d %GOODQ_WSL_DISTRO% -u root -- bash -lc "systemctl is-active vllm-llama1b || true; systemctl is-active ollama || true"
echo.
echo [INFO] Listening ports (WSL)
wsl -d %GOODQ_WSL_DISTRO% -- bash -lc "ss -lntp | grep -E ':38005|:38004|:31434|:11434' || true"
echo.
echo [INFO] WSL keepalive anchor
wsl -d %GOODQ_WSL_DISTRO% -- bash -lc "pgrep -af '[g]oodq-vllm-keepalive' || true"
echo.
pause
goto menu

:start
call "%~dp0start_vllm_servers.bat"
goto menu

:stop
call "%~dp0stop_vllm_servers.bat"
goto menu

:watch_vllm_systemd
echo Launching log follower in a new window.
echo Close that window to stop following logs.
start "GoodQ vLLM (systemd)" wsl -d %GOODQ_WSL_DISTRO% -u root -- journalctl -u vllm-llama1b -f --no-pager
goto menu

:watch_vllm_file
echo Launching log follower in a new window.
echo Close that window to stop following logs.
start "GoodQ vLLM (file)" wsl -d %GOODQ_WSL_DISTRO% -- bash -lc "tail -f ~/vllm_server/logs/vllm-service.log"
goto menu

:watch_ollama
echo Launching log follower in a new window.
echo Close that window to stop following logs.
start "GoodQ Ollama (systemd)" wsl -d %GOODQ_WSL_DISTRO% -u root -- journalctl -u ollama -f --no-pager
goto menu

:end
endlocal
exit /b 0
