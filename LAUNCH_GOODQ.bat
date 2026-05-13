@echo off
REM GoodQ4All Master Launcher (Batch Wrapper)
REM Double-click this to start GoodQ4All

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"
powershell.exe -ExecutionPolicy Bypass -File "%ROOT_DIR%LAUNCH_GOODQ.ps1"
pause
