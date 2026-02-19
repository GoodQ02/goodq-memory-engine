# GoodQ Quick Fix - Install Web Dependencies
# Run this in PowerShell if you prefer PowerShell over CMD

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "GoodQ Web Dependencies Installer" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

. (Join-Path $PSScriptRoot "..\\_lib\\interpreter_bindings.ps1")
$condaExe = Get-GoodQCondaExe
$coreEnv = Get-GoodQCondaEnv

Write-Host "[1/4] Checking $coreEnv environment..." -ForegroundColor Yellow

$pyVersion = & $condaExe run -n $coreEnv python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to run Python in $coreEnv environment" -ForegroundColor Red
    exit 1
}

Write-Host "[2/4] Installing FastAPI and dependencies..." -ForegroundColor Yellow
Write-Host "   This may take a minute...`n" -ForegroundColor DarkGray

# Install required packages
& $condaExe run -n $coreEnv pip install fastapi uvicorn[standard] python-multipart websockets pydantic --quiet

Write-Host "`n[3/4] Verifying installation..." -ForegroundColor Yellow

try {
    $fastapiVersion = & $condaExe run -n $coreEnv python -c "import fastapi; print(fastapi.__version__)" 2>&1
    Write-Host "   ✓ FastAPI: $fastapiVersion" -ForegroundColor Green
    
    $uvicornVersion = & $condaExe run -n $coreEnv python -c "import uvicorn; print(uvicorn.__version__)" 2>&1
    Write-Host "   ✓ Uvicorn: $uvicornVersion" -ForegroundColor Green
    
    Write-Host "`n[4/4] Installation complete!" -ForegroundColor Green
    
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "SUCCESS! Dependencies installed." -ForegroundColor Green
    Write-Host "========================================`n" -ForegroundColor Cyan
    
    Write-Host "You can now run:" -ForegroundColor White
    Write-Host "   • LAUNCH_WEB_INTERFACE_FIXED_V2.bat" -ForegroundColor Yellow
    Write-Host "   • Or: python api_server.py`n" -ForegroundColor Yellow
    
} catch {
    Write-Host "`n✗ Installation verification failed: $_" -ForegroundColor Red
    Write-Host "   Try running the batch file version instead`n" -ForegroundColor Yellow
}

Write-Host "Press any key to continue..." -ForegroundColor DarkGray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
