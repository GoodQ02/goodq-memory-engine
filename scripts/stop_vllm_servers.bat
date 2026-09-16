@echo off
setlocal
REM Keep the existing stop entrypoint; PowerShell performs structured owner checks.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0stop_vllm_servers.ps1" %*
set "VLLM_STOP_EXIT_CODE=%ERRORLEVEL%"
if /I not "%GOODQ_NO_PAUSE%"=="1" pause
exit /b %VLLM_STOP_EXIT_CODE%
