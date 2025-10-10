#!/usr/bin/env pwsh
# Emergency Conda Repair Script
# Fixes base conda Python corruption and rebuilds affected environments

param(
    [switch]$SkipBackup
)

$ErrorActionPreference = "Continue"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "   EMERGENCY CONDA REPAIR" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Step 1: Check base conda Python
Write-Host "[1] Checking base conda Python..." -ForegroundColor Yellow
try {
    $baseCheck = python -c "import sys; print(sys.version)" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] Base conda Python is corrupted!" -ForegroundColor Red
        Write-Host "    Error: $baseCheck" -ForegroundColor Red
        
        Write-Host "`n[FIX] Attempting to repair base conda..." -ForegroundColor Yellow
        
        # Try to update conda itself
        Write-Host "  → Updating conda..." -ForegroundColor Cyan
        conda update -n base conda -y 2>&1 | Out-Host
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[!] Conda update failed. Manual intervention required." -ForegroundColor Red
            Write-Host "`nRECOMMENDED ACTIONS:" -ForegroundColor Yellow
            Write-Host "1. Close all conda/Python processes" -ForegroundColor White
            Write-Host "2. Run: conda install -n base python=3.11 --force-reinstall -y" -ForegroundColor White
            Write-Host "3. Or reinstall Miniconda from: https://docs.conda.io/en/latest/miniconda.html" -ForegroundColor White
            exit 1
        }
    } else {
        Write-Host "[✓] Base conda Python is healthy" -ForegroundColor Green
        Write-Host "    Version: $baseCheck" -ForegroundColor Gray
    }
} catch {
    Write-Host "[!] Cannot test base Python: $_" -ForegroundColor Red
}

# Step 2: Identify broken environments
Write-Host "`n[2] Scanning for broken environments..." -ForegroundColor Yellow

$brokenEnvs = @()
$goodqEnvs = conda env list | Select-String "goodq_" | ForEach-Object {
    $line = $_.Line -split '\s+'
    $line[0]
}

foreach ($env in $goodqEnvs) {
    Write-Host "  Testing: $env" -ForegroundColor Gray -NoNewline
    
    # Test if pip works
    $pipTest = conda run -n $env pip --version 2>&1
    if ($LASTEXITCODE -ne 0 -or $pipTest -match "ImportError|ModuleNotFoundError") {
        Write-Host " [BROKEN]" -ForegroundColor Red
        $brokenEnvs += $env
    } else {
        Write-Host " [OK]" -ForegroundColor Green
    }
}

if ($brokenEnvs.Count -eq 0) {
    Write-Host "`n[✓] All environments are healthy!" -ForegroundColor Green
    exit 0
}

Write-Host "`n[!] Found $($brokenEnvs.Count) broken environment(s):" -ForegroundColor Red
$brokenEnvs | ForEach-Object { Write-Host "    - $_" -ForegroundColor Yellow }

# Step 3: Rebuild broken environments
Write-Host "`n[3] Rebuilding broken environments..." -ForegroundColor Yellow

foreach ($env in $brokenEnvs) {
    Write-Host "`n  → Rebuilding: $env" -ForegroundColor Cyan
    
    # Check if requirements file exists
    $reqFile = "L:\goodq4all\envs\$env\requirements.txt"
    $ymlFile = "L:\goodq4all\envs\$env\environment.yml"
    
    if (-not (Test-Path $reqFile)) {
        Write-Host "    [!] No requirements file found at: $reqFile" -ForegroundColor Red
        Write-Host "    [!] Skipping $env - manual rebuild required" -ForegroundColor Yellow
        continue
    }
    
    # Backup if requested
    if (-not $SkipBackup) {
        Write-Host "    → Exporting current state..." -ForegroundColor Gray
        conda env export -n $env > "L:\_ARCHIVE\env_backups\${env}_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').yml" 2>&1 | Out-Null
    }
    
    # Remove the broken environment
    Write-Host "    → Removing broken environment..." -ForegroundColor Gray
    conda env remove -n $env -y 2>&1 | Out-Null
    
    # Recreate from scratch
    Write-Host "    → Creating fresh environment..." -ForegroundColor Gray
    
    if (Test-Path $ymlFile) {
        conda env create -f $ymlFile 2>&1 | Out-Host
    } else {
        # Create minimal env and install requirements
        conda create -n $env python=3.10 pip -y 2>&1 | Out-Host
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "    → Installing requirements..." -ForegroundColor Gray
            
            # Use direct pip call to avoid -m flag
            $envPath = (conda env list | Select-String $env | ForEach-Object { ($_.Line -split '\s+')[1] })
            $pipExe = Join-Path $envPath "Scripts\pip.exe"
            
            if (Test-Path $pipExe) {
                & $pipExe install -r $reqFile --no-cache-dir 2>&1 | Out-Host
            }
        }
    }
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "    [✓] $env rebuilt successfully!" -ForegroundColor Green
    } else {
        Write-Host "    [!] $env rebuild failed!" -ForegroundColor Red
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "   REPAIR COMPLETE" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Final verification
Write-Host "[4] Final verification..." -ForegroundColor Yellow
$stillBroken = @()

foreach ($env in $brokenEnvs) {
    $pipTest = conda run -n $env pip --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        $stillBroken += $env
    }
}

if ($stillBroken.Count -eq 0) {
    Write-Host "[✓] All repairs successful!" -ForegroundColor Green
} else {
    Write-Host "[!] Still broken:" -ForegroundColor Red
    $stillBroken | ForEach-Object { Write-Host "    - $_" -ForegroundColor Yellow }
    Write-Host "`nThese environments require manual attention." -ForegroundColor Yellow
}
