@echo off
REM ========================================================================
REM GoodQ Simple Launcher - Just Command Center Dashboard
REM For quick monitoring without API server
REM ========================================================================

cd /d L:\zenml_project

echo.
echo  ╔═══════════════════════════════════════════════════════════════╗
echo  ║                  GoodQ Command Center Only                     ║
echo  ╚═══════════════════════════════════════════════════════════════╝
echo.

REM Launch Command Center only
start "GoodQ Command Center" pwsh -NoExit -Command "cd L:\zenml_project; pwsh scripts\command_center.ps1"

echo  ✓ Command Center launched!
echo.
echo  Press any key to close this window...
pause >nul
