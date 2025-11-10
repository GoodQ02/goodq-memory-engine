# GoodQ Agent System - Startup Script
# Starts agent orchestrator with self-healing and LLM integration

Write-Host "=== GoodQ Agent System Startup ===" -ForegroundColor Cyan
Write-Host ""

$ErrorActionPreference = "Stop"

# Check if LM Studio is running
Write-Host "Checking LM Studio..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:1234/v1/models" -TimeoutSec 5 -UseBasicParsing
    Write-Host "  ✓ LM Studio is running" -ForegroundColor Green
} catch {
    Write-Host "  ✗ LM Studio not running - LLM features will be disabled" -ForegroundColor Red
    Write-Host "    Start LM Studio and load a model to enable LLM features" -ForegroundColor Yellow
}

# Activate conda environment
Write-Host "`nActivating base environment..." -ForegroundColor Yellow
conda activate base

# Install required packages if missing
Write-Host "`nChecking Python dependencies..." -ForegroundColor Yellow
$packages = @("pyyaml", "aiohttp", "watchdog")

foreach ($pkg in $packages) {
    python -c "import $($pkg.Replace('-', '_'))" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Installing $pkg..." -ForegroundColor Yellow
        pip install $pkg --quiet
    }
}

Write-Host "  ✓ Dependencies ready" -ForegroundColor Green

# Create necessary directories
Write-Host "`nSetting up directories..." -ForegroundColor Yellow
$dirs = @(
    "L:\goodq4all\import_inbox",
    "L:\goodq4all\import_inbox\_completed",
    "L:\goodq4all\import_inbox\_failed",
    "L:\goodq4all\logs",
    "L:\goodq4all\workflows"
)

foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}

Write-Host "  ✓ Directories ready" -ForegroundColor Green

# Display startup options
Write-Host "`n=== Startup Options ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Start Watchdog with Agent Orchestrator" -ForegroundColor White
Write-Host "   Watches import_inbox and processes videos with full agent pipeline"
Write-Host ""
Write-Host "2. Start Self-Healing Monitor" -ForegroundColor White
Write-Host "   Monitors pipeline health and auto-fixes issues"
Write-Host ""
Write-Host "3. Test Agent Health" -ForegroundColor White
Write-Host "   Check status of all agents"
Write-Host ""
Write-Host "4. Process Single Video" -ForegroundColor White
Write-Host "   Process one video through agent pipeline"
Write-Host ""
Write-Host "5. Start All Services" -ForegroundColor White
Write-Host "   Start watchdog + self-healing monitor"
Write-Host ""

$choice = Read-Host "Select option (1-5)"

switch ($choice) {
    "1" {
        Write-Host "`nStarting Watchdog with Agent Orchestrator..." -ForegroundColor Green
        python L:\goodq4all\agents\watchdog_agent_integration.py
    }
    "2" {
        Write-Host "`nStarting Self-Healing Monitor..." -ForegroundColor Green
        python L:\goodq4all\agents\self_healing_monitor.py
    }
    "3" {
        Write-Host "`nChecking Agent Health..." -ForegroundColor Green
        python L:\goodq4all\agents\pipeline_integration.py
    }
    "4" {
        $videoPath = Read-Host "Enter video path"
        Write-Host "`nProcessing $videoPath..." -ForegroundColor Green
        python -c "import asyncio; from agents.pipeline_integration import process_video_with_agents; asyncio.run(process_video_with_agents('$videoPath'))"
    }
    "5" {
        Write-Host "`nStarting All Services..." -ForegroundColor Green
        
        # Start self-healing monitor in background
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd L:\goodq4all; conda activate base; python agents\self_healing_monitor.py"
        
        Start-Sleep -Seconds 2
        
        # Start watchdog in foreground
        python L:\goodq4all\agents\watchdog_agent_integration.py
    }
    default {
        Write-Host "Invalid option" -ForegroundColor Red
        exit 1
    }
}
