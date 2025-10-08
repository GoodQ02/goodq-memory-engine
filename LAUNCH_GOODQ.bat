@echo off
REM ========================================================================
REM GoodQ One-Click Launcher
REM Starts Command Center Dashboard + API Server + Optional Services
REM ========================================================================

echo.
echo  ╔═══════════════════════════════════════════════════════════════╗
echo  ║                      GoodQ Mission Launch                      ║
echo  ║           Command Center + API + Local Services                ║
echo  ╚═══════════════════════════════════════════════════════════════╝
echo.

REM Change to zenml_project directory
cd /d L:\GoodQ_4_All
if errorlevel 1 (
    echo [ERROR] Could not change to L:\GoodQ_4_All
    pause
    exit /b 1
)

REM Check for PowerShell
where pwsh >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PowerShell 7+ not found. Please install PowerShell.
    echo Download from: https://github.com/PowerShell/PowerShell/releases
    pause
    exit /b 1
)

REM Check for Conda
where conda >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Conda not found. Please open an Anaconda PowerShell prompt.
    pause
    exit /b 1
)

echo [LAUNCH] Starting GoodQ services...
echo.

REM Stop any existing services on port 8000
echo [LAUNCH] Clearing port 8000 if in use...
pwsh -Command "try { Get-NetTCPConnection -LocalPort 8000 -ErrorAction Stop | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } } catch {}"
timeout /t 2 /nobreak >nul

REM Launch API server in new window
echo [LAUNCH] Starting API server on http://localhost:8000
start "GoodQ API Server" pwsh -NoExit -Command "cd L:\GoodQ_4_All; pwsh scripts\start_api.ps1 -Port 8000"
timeout /t 3 /nobreak >nul

REM Wait a moment for API to initialize
echo [LAUNCH] Waiting for API to initialize...
timeout /t 3 /nobreak >nul

REM Launch Command Center dashboard in new window
echo [LAUNCH] Starting Command Center Dashboard
start "GoodQ Command Center" pwsh -NoExit -Command "cd L:\GoodQ_4_All; pwsh scripts\command_center.ps1"
timeout /t 2 /nobreak >nul

REM Open browser to API docs (optional)
echo [LAUNCH] Opening API documentation...
timeout /t 3 /nobreak >nul
start http://localhost:8000/docs

echo.
echo  ╔═══════════════════════════════════════════════════════════════╗
echo  ║                    ✓ GoodQ Launch Complete!                   ║
echo  ╚═══════════════════════════════════════════════════════════════╝
echo.
echo  Services Running:
echo    • API Server:      http://localhost:8000
echo    • API Docs:        http://localhost:8000/docs
echo    • Command Center:  PowerShell Dashboard
echo.
echo  To stop services: Close the PowerShell windows or run STOP_GOODQ.bat
echo.
echo Press any key to close this launcher window...
pause >nul
