@echo off
REM Refresh Windows->WSL portproxy for vLLM (port 38005)
REM Run this in an elevated (Administrator) prompt whenever the WSL IP changes (e.g., after reboot)

setlocal enabledelayedexpansion
echo [INFO] Detecting WSL IP...
for /f "tokens=1" %%I in ('wsl hostname -I') do (
    set "WSL_IP=%%I"
    goto :got_ip
)

:got_ip
if "%WSL_IP%"=="" (
    echo [ERROR] Could not detect WSL IP. Is WSL running?
    exit /b 1
)
echo [INFO] WSL IP detected: %WSL_IP%

echo [INFO] Resetting portproxy for port 38005...
netsh interface portproxy delete v4tov4 listenport=38005 listenaddress=0.0.0.0 >nul 2>&1
netsh interface portproxy add v4tov4 listenport=38005 listenaddress=0.0.0.0 connectport=38005 connectaddress=%WSL_IP%
if errorlevel 1 (
    echo [ERROR] Failed to add portproxy rule. Try running as Administrator.
    exit /b 1
)

echo [INFO] Ensuring firewall rule for port 38005...
netsh advfirewall firewall show rule name="WSL vLLM 38005" >nul 2>&1
if errorlevel 1 (
    netsh advfirewall firewall add rule name="WSL vLLM 38005" dir=in action=allow protocol=TCP localport=38005 >nul 2>&1
)

echo [DONE] Portproxy refreshed. Test with: curl http://localhost:38005/v1/models
endlocal
