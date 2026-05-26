#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Test audio diarization components individually
.DESCRIPTION
    PowerShell-native test runner for audio diarization pipeline
#>

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "_lib\\interpreter_bindings.ps1")
$condaExe = Get-GoodQCondaExe

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "GoodQ4All - Audio Diarization Component Testing" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

$envName = "goodq_audio_diarize"
$testScript = "L:\goodq4all\scripts\test_audio_components.py"

# Check if environment exists
Write-Host "[0] Checking environment..." -ForegroundColor Yellow
$envExists = & $condaExe env list | Select-String $envName
if (-not $envExists) {
    Write-Host "  ❌ Environment '$envName' not found" -ForegroundColor Red
    Write-Host "  Available environments:" -ForegroundColor Yellow
    & $condaExe env list
    exit 1
}
Write-Host "  ✓ Environment found: $envName" -ForegroundColor Green
Write-Host ""

# Run test in environment (no shell-state activation)
Write-Host "[2] Activating environment and running tests..." -ForegroundColor Yellow
Write-Host "  Environment: $envName" -ForegroundColor Cyan
Write-Host "  Test Script: $testScript" -ForegroundColor Cyan
Write-Host ""

try {
    # Run the test
    Write-Host "================================================================================" -ForegroundColor Cyan
    Write-Host "Starting Audio Component Tests" -ForegroundColor Cyan
    Write-Host "================================================================================" -ForegroundColor Cyan
    Write-Host ""
    
    & $condaExe run -n $envName python $testScript
    
    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Cyan
    Write-Host "Tests Complete" -ForegroundColor Cyan
    Write-Host "================================================================================" -ForegroundColor Cyan
    
} catch {
    Write-Host ""
    Write-Host "  ❌ Error: $_" -ForegroundColor Red
    exit 1
}
