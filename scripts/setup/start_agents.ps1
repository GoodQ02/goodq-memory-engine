# GoodQ Agent System - Startup Script
# Legacy helper for historical agent surfaces and diagnostics

Write-Host "=== GoodQ Agent System Startup ===" -ForegroundColor Cyan
Write-Host ""

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "..\\_lib\\interpreter_bindings.ps1")
$condaExe = Get-GoodQCondaExe
$runtimeEnv = Get-GoodQCondaEnv
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
$env:PYTHONPATH = $RepoRoot

$runtimeJson = & $condaExe run -n $runtimeEnv python -c "from steps.common.config_loader import get_runtime_paths, load_configs; import json; rp = get_runtime_paths(load_configs({})); print(json.dumps({'import_inbox': rp['import_inbox'], 'log_dir': rp['log_dir']}))"
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($runtimeJson)) {
    throw "Failed to resolve canonical runtime paths via config_loader."
}
$runtimePaths = $runtimeJson | ConvertFrom-Json

# Check if LM Studio is running
Write-Host "Checking LM Studio..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:1234/v1/models" -TimeoutSec 5 -UseBasicParsing
    Write-Host "  ✓ LM Studio is running" -ForegroundColor Green
} catch {
    Write-Host "  ✗ LM Studio not running - LLM features will be disabled" -ForegroundColor Red
    Write-Host "    Start LM Studio and load a model to enable LLM features" -ForegroundColor Yellow
}

# Install required packages if missing
Write-Host "`nChecking Python dependencies..." -ForegroundColor Yellow
$packages = @("pyyaml", "aiohttp", "watchdog")

foreach ($pkg in $packages) {
    & $condaExe run -n base python -c "import $($pkg.Replace('-', '_'))" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Installing $pkg..." -ForegroundColor Yellow
        & $condaExe run -n base pip install $pkg --quiet
    }
}

Write-Host "  ✓ Dependencies ready" -ForegroundColor Green

# Create necessary directories
Write-Host "`nSetting up directories..." -ForegroundColor Yellow
$dirs = @(
    $runtimePaths.import_inbox,
    (Join-Path $runtimePaths.import_inbox "_completed"),
    (Join-Path $runtimePaths.import_inbox "_failed"),
    $runtimePaths.log_dir,
    (Join-Path $RepoRoot "workflows")
)

foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}

Write-Host "  ✓ Directories ready" -ForegroundColor Green

# Display startup options
Write-Host "`n=== Startup Options ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Legacy Watchdog Entry (retired)" -ForegroundColor White
Write-Host "   The old agent-orchestrator watcher was removed; use python -m cli.watchdog"
Write-Host ""
Write-Host "2. Start Self-Healing Monitor" -ForegroundColor White
Write-Host "   Monitors pipeline health and auto-fixes issues"
Write-Host ""
Write-Host "3. Legacy Agent Health (retired)" -ForegroundColor White
Write-Host "   The old pipeline integration health check was removed"
Write-Host ""
Write-Host "4. Legacy Single-Video Agent Pipeline (retired)" -ForegroundColor White
Write-Host "   Use canonical ingestion entrypoints instead"
Write-Host ""
Write-Host "5. Legacy All-Services Bundle (retired)" -ForegroundColor White
Write-Host "   The old watcher bundle was removed; start canonical services explicitly"
Write-Host ""

$choice = Read-Host "Select option (1-5)"

switch ($choice) {
    "1" {
        Write-Host "`nLegacy watcher retired." -ForegroundColor Yellow
        Write-Host "Use: $condaExe run -n $runtimeEnv python -m cli.watchdog" -ForegroundColor Yellow
        exit 1
    }
    "2" {
        Write-Host "`nStarting Self-Healing Monitor..." -ForegroundColor Green
        & $condaExe run -n base python (Join-Path $RepoRoot "agents\\self_healing_monitor.py")
    }
    "3" {
        Write-Host "`nLegacy agent health path retired." -ForegroundColor Yellow
        Write-Host "Use current runtime utilities and docs instead of the removed pipeline integration harness." -ForegroundColor Yellow
        exit 1
    }
    "4" {
        Write-Host "`nLegacy single-video agent pipeline retired." -ForegroundColor Yellow
        Write-Host "Use: $condaExe run -n $runtimeEnv python -m cli.run_ingestion --input-dir <path>" -ForegroundColor Yellow
        exit 1
    }
    "5" {
        Write-Host "`nLegacy all-services bundle retired." -ForegroundColor Yellow
        Write-Host "Start the canonical watchdog explicitly with python -m cli.watchdog." -ForegroundColor Yellow
        exit 1
    }
    default {
        Write-Host "Invalid option" -ForegroundColor Red
        exit 1
    }
}
