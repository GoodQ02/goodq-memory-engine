#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Test audio diarization components individually
.DESCRIPTION
    PowerShell-native test runner for audio diarization pipeline
#>

$ErrorActionPreference = "Stop"

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "GoodQ4All - Audio Diarization Component Testing" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

$envName = "goodq_audio_diarize"
$testScript = "L:\goodq4all\scripts\test_audio_components.py"

# Check if environment exists
Write-Host "[0] Checking environment..." -ForegroundColor Yellow
$envExists = conda env list | Select-String $envName
if (-not $envExists) {
    Write-Host "  ❌ Environment '$envName' not found" -ForegroundColor Red
    Write-Host "  Available environments:" -ForegroundColor Yellow
    conda env list
    exit 1
}
Write-Host "  ✓ Environment found: $envName" -ForegroundColor Green
Write-Host ""

# Initialize conda for PowerShell
Write-Host "[1] Initializing conda for PowerShell..." -ForegroundColor Yellow
$condaPath = Split-Path (Split-Path $env:CONDA_EXE -Parent) -Parent
& "$condaPath\shell\condabin\conda-hook.ps1"
Write-Host "  ✓ Conda initialized" -ForegroundColor Green
Write-Host ""

# Activate environment and run test
Write-Host "[2] Activating environment and running tests..." -ForegroundColor Yellow
Write-Host "  Environment: $envName" -ForegroundColor Cyan
Write-Host "  Test Script: $testScript" -ForegroundColor Cyan
Write-Host ""

try {
    conda activate $envName
    
    # Verify activation
    $currentEnv = $env:CONDA_DEFAULT_ENV
    if ($currentEnv -ne $envName) {
        Write-Host "  ⚠ Warning: Expected env '$envName' but got '$currentEnv'" -ForegroundColor Yellow
    } else {
        Write-Host "  ✓ Environment activated: $currentEnv" -ForegroundColor Green
    }
    Write-Host ""
    
    # Run the test
    Write-Host "================================================================================" -ForegroundColor Cyan
    Write-Host "Starting Audio Component Tests" -ForegroundColor Cyan
    Write-Host "================================================================================" -ForegroundColor Cyan
    Write-Host ""
    
    python $testScript
    
    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Cyan
    Write-Host "Tests Complete" -ForegroundColor Cyan
    Write-Host "================================================================================" -ForegroundColor Cyan
    
} catch {
    Write-Host ""
    Write-Host "  ❌ Error: $_" -ForegroundColor Red
    exit 1
}
