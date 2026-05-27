@echo off
REM GoodQ4All LLM Services Restart Wrapper
REM Executes the PowerShell recycle script to safely release and restart LLM workloads.

call "%~dp0_lib\interpreter_bindings.bat"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0restart_llm_services.ps1"

if /I not "%GOODQ_NO_PAUSE%"=="1" pause
