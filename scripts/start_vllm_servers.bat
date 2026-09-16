@echo off
setlocal
REM Keep the Dev On entrypoint; PowerShell owns explicit WSL and readiness checks.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0start_vllm_servers.ps1" %*
set "VLLM_START_EXIT_CODE=%ERRORLEVEL%"
if /I not "%GOODQ_NO_PAUSE%"=="1" pause
exit /b %VLLM_START_EXIT_CODE%
