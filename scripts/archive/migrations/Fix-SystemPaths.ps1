#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Fix system PATH and environment configuration
.DESCRIPTION
    Ensures FFmpeg, Python, and other tools are accessible from all contexts
#>

$ErrorActionPreference = "Stop"

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "GoodQ4All - System Path Configuration Fix" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Define critical paths
$pathsToAdd = @(
    "L:\tools\ffmpeg\bin",
    "C:\Users\jdben\miniconda3",
    "C:\Users\jdben\miniconda3\Scripts",
    "C:\Users\jdben\miniconda3\Library\bin"
)

# Check current PATH
Write-Host "[1] Analyzing current PATH..." -ForegroundColor Yellow
$currentPath = $env:PATH -split ';'
$missingPaths = @()

foreach ($path in $pathsToAdd) {
    if (Test-Path $path) {
        if ($currentPath -contains $path) {
            Write-Host "  ✓ $path (already in PATH)" -ForegroundColor Green
        } else {
            Write-Host "  ⚠ $path (MISSING from PATH)" -ForegroundColor Yellow
            $missingPaths += $path
        }
    } else {
        Write-Host "  ❌ $path (does not exist)" -ForegroundColor Red
    }
}
Write-Host ""

# Add missing paths to current session
if ($missingPaths.Count -gt 0) {
    Write-Host "[2] Adding paths to current session..." -ForegroundColor Yellow
    $env:PATH = ($missingPaths + $currentPath) -join ';'
    Write-Host "  ✓ Added $($missingPaths.Count) path(s) to current session" -ForegroundColor Green
    Write-Host ""
}

# Verify tools are now accessible
Write-Host "[3] Verifying tool accessibility..." -ForegroundColor Yellow
$tools = @{
    "ffmpeg" = "FFmpeg"
    "ffprobe" = "FFprobe"
    "python" = "Python"
    "conda" = "Conda"
}

foreach ($tool in $tools.Keys) {
    $cmd = Get-Command $tool -ErrorAction SilentlyContinue
    if ($cmd) {
        Write-Host "  ✓ $($tools[$tool]): $($cmd.Source)" -ForegroundColor Green
    } else {
        Write-Host "  ❌ $($tools[$tool]) not found" -ForegroundColor Red
    }
}
Write-Host ""

# Offer to make permanent
Write-Host "[4] PATH Configuration Options" -ForegroundColor Yellow
Write-Host "  Current session has been updated." -ForegroundColor Green
Write-Host ""
Write-Host "  To make changes permanent, you can:" -ForegroundColor Cyan
Write-Host "  1. Add to User PATH (affects all PowerShell/CMD sessions)" -ForegroundColor White
Write-Host "  2. Add to conda environment activation scripts" -ForegroundColor White
Write-Host "  3. Add to PowerShell profile ($PROFILE)" -ForegroundColor White
Write-Host ""
Write-Host "  Would you like to:" -ForegroundColor Yellow
Write-Host "  [U] Update User PATH (requires restart)" -ForegroundColor White
Write-Host "  [P] Update PowerShell profile (affects PowerShell only)" -ForegroundColor White
Write-Host "  [S] Skip (current session only)" -ForegroundColor White
Write-Host ""

$choice = Read-Host "  Choice [U/P/S]"

switch ($choice.ToUpper()) {
    "U" {
        Write-Host "`n  Updating User PATH..." -ForegroundColor Yellow
        
        # Get current user PATH
        $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
        $userPathArray = $userPath -split ';'
        
        # Add missing paths
        $updated = $false
        foreach ($path in $missingPaths) {
            if ($userPathArray -notcontains $path) {
                $userPathArray += $path
                $updated = $true
                Write-Host "    + $path" -ForegroundColor Green
            }
        }
        
        if ($updated) {
            $newUserPath = $userPathArray -join ';'
            [Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
            Write-Host "  ✓ User PATH updated (restart required)" -ForegroundColor Green
        } else {
            Write-Host "  ℹ All paths already in User PATH" -ForegroundColor Cyan
        }
    }
    
    "P" {
        Write-Host "`n  Updating PowerShell profile..." -ForegroundColor Yellow
        
        # Create profile if it doesn't exist
        if (-not (Test-Path $PROFILE)) {
            New-Item -Path $PROFILE -ItemType File -Force | Out-Null
            Write-Host "    Created profile: $PROFILE" -ForegroundColor Green
        }
        
        # Read current profile
        $profileContent = Get-Content $PROFILE -Raw -ErrorAction SilentlyContinue
        
        # Add PATH update code
        $pathUpdateCode = @"

# GoodQ4All - Auto-added by Fix-SystemPaths.ps1
# Ensures FFmpeg and other tools are accessible
`$goodqPaths = @(
$(($missingPaths | ForEach-Object { "    '$_'" }) -join ",`n")
)
foreach (`$path in `$goodqPaths) {
    if ((Test-Path `$path) -and (`$env:PATH -notlike "*`$path*")) {
        `$env:PATH = "`$path;`$env:PATH"
    }
}
"@
        
        if ($profileContent -notlike "*GoodQ4All*") {
            Add-Content -Path $PROFILE -Value $pathUpdateCode
            Write-Host "  ✓ PowerShell profile updated" -ForegroundColor Green
            Write-Host "    Profile: $PROFILE" -ForegroundColor Gray
        } else {
            Write-Host "  ℹ GoodQ4All paths already in profile" -ForegroundColor Cyan
        }
    }
    
    default {
        Write-Host "`n  Skipped - changes apply to current session only" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Configuration Complete" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
