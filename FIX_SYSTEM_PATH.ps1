# 🔧 GoodQ System Configuration Fix
# Permanently adds Conda and Python to Windows PATH
# Run this ONCE as Administrator to fix all PATH issues

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "GOODQ SYSTEM PATH CONFIGURATOR" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "⚠️  WARNING: Not running as Administrator" -ForegroundColor Yellow
    Write-Host "   Some changes require admin privileges" -ForegroundColor Yellow
    Write-Host "`n   Right-click this script and select 'Run as Administrator'`n" -ForegroundColor Yellow
}

# Conda installation path
$condaPath = "C:\Users\jdben\miniconda3"

if (-not (Test-Path $condaPath)) {
    Write-Host "❌ ERROR: Conda not found at $condaPath" -ForegroundColor Red
    exit 1
}

Write-Host "✓ Found Conda at: $condaPath`n" -ForegroundColor Green

# Paths to add
$pathsToAdd = @(
    "$condaPath",
    "$condaPath\Scripts",
    "$condaPath\Library\bin",
    "$condaPath\Library\mingw-w64\bin",
    "$condaPath\Library\usr\bin",
    "$condaPath\condabin"
)

# Get current USER PATH
$currentUserPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
$userPathArray = $currentUserPath -split ';' | Where-Object { $_ -ne '' }

Write-Host "[1] ADDING TO USER PATH (persistent across reboots):" -ForegroundColor Yellow
$pathsAdded = @()
$pathsSkipped = @()

foreach ($path in $pathsToAdd) {
    if ($userPathArray -contains $path) {
        Write-Host "  ⊙ Already exists: $path" -ForegroundColor DarkGray
        $pathsSkipped += $path
    } else {
        Write-Host "  + Adding: $path" -ForegroundColor Green
        $userPathArray += $path
        $pathsAdded += $path
    }
}

if ($pathsAdded.Count -gt 0) {
    $newUserPath = $userPathArray -join ';'
    
    try {
        [System.Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
        Write-Host "`n✅ USER PATH UPDATED SUCCESSFULLY" -ForegroundColor Green
        Write-Host "   Added $($pathsAdded.Count) paths" -ForegroundColor Green
    } catch {
        Write-Host "`n❌ ERROR: Failed to update PATH: $_" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "`n⊙ No changes needed - all paths already present" -ForegroundColor Cyan
}

# Initialize conda for PowerShell
Write-Host "`n[2] INITIALIZING CONDA FOR POWERSHELL:" -ForegroundColor Yellow
$condaExe = "$condaPath\Scripts\conda.exe"

if (Test-Path $condaExe) {
    Write-Host "  Running: conda init powershell" -ForegroundColor Cyan
    
    # Run conda init
    & $condaExe init powershell 2>&1 | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ Conda initialized for PowerShell" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  Conda init returned non-zero exit code" -ForegroundColor Yellow
    }
    
    # Also init for cmd
    Write-Host "  Running: conda init cmd.exe" -ForegroundColor Cyan
    & $condaExe init cmd.exe 2>&1 | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ Conda initialized for CMD" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  Conda init for CMD returned non-zero exit code" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ❌ conda.exe not found at $condaExe" -ForegroundColor Red
}

# Update current session PATH
Write-Host "`n[3] UPDATING CURRENT SESSION:" -ForegroundColor Yellow
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "Machine")
Write-Host "  ✅ Current session PATH refreshed" -ForegroundColor Green

# Verify conda is now available
Write-Host "`n[4] VERIFICATION:" -ForegroundColor Yellow
try {
    $condaVersion = & conda --version 2>&1
    Write-Host "  ✅ conda command available: $condaVersion" -ForegroundColor Green
} catch {
    Write-Host "  ⚠️  conda not yet available in this session" -ForegroundColor Yellow
    Write-Host "     (Will be available after restarting terminal)" -ForegroundColor Yellow
}

try {
    $pythonVersion = & python --version 2>&1
    Write-Host "  ✅ python command available: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  ⚠️  python not yet available in this session" -ForegroundColor Yellow
}

# Summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "CONFIGURATION COMPLETE" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "✅ Changes made:" -ForegroundColor Green
Write-Host "   • Added $($pathsAdded.Count) paths to USER environment" -ForegroundColor White
Write-Host "   • Initialized conda for PowerShell" -ForegroundColor White
Write-Host "   • Initialized conda for CMD.exe" -ForegroundColor White
Write-Host "   • Refreshed current session PATH`n" -ForegroundColor White

Write-Host "📝 IMPORTANT NEXT STEPS:" -ForegroundColor Yellow
Write-Host "   1. CLOSE this PowerShell window" -ForegroundColor White
Write-Host "   2. CLOSE any other open terminals" -ForegroundColor White
Write-Host "   3. Open a NEW PowerShell window" -ForegroundColor White
Write-Host "   4. Test: Run 'conda --version' and 'python --version'" -ForegroundColor White
Write-Host "   5. .BAT files should now work when double-clicked`n" -ForegroundColor White

Write-Host "🔄 If still having issues after restart:" -ForegroundColor Cyan
Write-Host "   • Try logging out and back in to Windows" -ForegroundColor White
Write-Host "   • Or restart your computer" -ForegroundColor White
Write-Host "   • This ensures all processes get the new PATH`n" -ForegroundColor White

Write-Host "========================================`n" -ForegroundColor Cyan

# Create a test batch file
$testBat = @"
@echo off
echo ========================================
echo Testing conda availability in CMD
echo ========================================
echo.
conda --version
echo.
python --version
echo.
echo ========================================
echo If you see version numbers above, it works!
echo ========================================
pause
"@

$testBatPath = "L:\goodq4all\TEST_CONDA_PATH.bat"
$testBat | Out-File -FilePath $testBatPath -Encoding ASCII

Write-Host "✅ Created test file: $testBatPath" -ForegroundColor Green
Write-Host "   Double-click this file to verify conda works in .BAT files`n" -ForegroundColor White
