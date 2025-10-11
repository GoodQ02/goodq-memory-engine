#!/usr/bin/env pwsh
# GoodQ Full Stack Launcher
# Starts all local services and monitoring tools

Param(
    [int]$ApiPort = 8000,
    [string]$ApiHost = '0.0.0.0',
    [switch]$NoBrowser,
    [switch]$NoCommandCenter,
    [switch]$HealthCheckFirst
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Banner {
    Write-Host ""
    Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║                    GoodQ Mission Launch                       ║" -ForegroundColor Cyan
    Write-Host "║         Command Center + API + Local Services                 ║" -ForegroundColor Cyan
    Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Section($title) {
    Write-Host "`n▶ $title" -ForegroundColor Magenta
}

function Write-Info($msg) { Write-Host "  [launch] $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "  [launch] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [launch] $msg" -ForegroundColor Yellow }
function Fail($msg) { Write-Error $msg; exit 1 }

Write-Banner

# Change to repo root
$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot
Write-Info "Repository: $repoRoot"

# Verify prerequisites
Write-Section "Checking Prerequisites"

if (-not (Get-Command conda -ErrorAction SilentlyContinue)) {
    Fail "Conda not found. Please open an Anaconda PowerShell prompt."
}
Write-Ok "Conda: Available"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Warn "Python not in PATH, but conda will handle it"
} else {
    $pyVer = (python --version 2>&1)
    Write-Ok "Python: $pyVer"
}

# Optional health check
if ($HealthCheckFirst) {
    Write-Section "Running Health Check"
    Write-Info "Validating environments and caches..."
    
    try {
        & pwsh scripts\mission_health_check.ps1 -EnvPrefix goodq
        Write-Ok "Health check passed!"
    } catch {
        Write-Warn "Health check had issues: $_"
        $continue = Read-Host "Continue anyway? (y/N)"
        if ($continue -ne 'y') {
            exit 1
        }
    }
}

# Start API Server
Write-Section "Starting API Server"
Write-Info "Launching API on ${ApiHost}:${ApiPort}"

$apiJob = Start-Job -ScriptBlock {
    param($RepoRoot, $Host, $Port)
    Set-Location $RepoRoot
    & pwsh scripts\start_api.ps1 -BindAddress $Host -Port $Port
} -ArgumentList $repoRoot, $ApiHost, $ApiPort

Write-Ok "API Server started (Job ID: $($apiJob.Id))"
Write-Info "Waiting for API to initialize..."
Start-Sleep -Seconds 5

# Verify API is responding
$apiUrl = "http://localhost:${ApiPort}"
$apiReady = $false
$retries = 5

for ($i = 1; $i -le $retries; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "${apiUrl}/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $apiReady = $true
            Write-Ok "API is responding at $apiUrl"
            break
        }
    } catch {
        Write-Info "API not ready yet (attempt $i/$retries)..."
        Start-Sleep -Seconds 2
    }
}

if (-not $apiReady) {
    Write-Warn "API may not be fully ready, but continuing..."
}

# Start Command Center
if (-not $NoCommandCenter) {
    Write-Section "Starting Command Center"
    Write-Info "Launching interactive dashboard..."
    
    $ccJob = Start-Job -ScriptBlock {
        param($RepoRoot)
        Set-Location $RepoRoot
        & pwsh scripts\command_center.ps1
    } -ArgumentList $repoRoot
    
    Write-Ok "Command Center started (Job ID: $($ccJob.Id))"
    Start-Sleep -Seconds 2
}

# Open browser
if (-not $NoBrowser) {
    Write-Section "Opening Browser"
    Write-Info "Launching API documentation..."
    Start-Sleep -Seconds 2
    
    try {
        Start-Process "${apiUrl}/docs"
        Write-Ok "Browser opened to ${apiUrl}/docs"
    } catch {
        Write-Warn "Could not open browser: $_"
        Write-Info "Manually navigate to: ${apiUrl}/docs"
    }
}

# Display status
Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                  ✓ GoodQ Launch Complete!                     ║" -ForegroundColor Green
Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

Write-Host "Services Running:" -ForegroundColor Cyan
Write-Host "  • API Server:      $apiUrl" -ForegroundColor White
Write-Host "  • API Docs:        ${apiUrl}/docs" -ForegroundColor White
Write-Host "  • API Health:      ${apiUrl}/health" -ForegroundColor White
if (-not $NoCommandCenter) {
    Write-Host "  • Command Center:  PowerShell Dashboard" -ForegroundColor White
}
Write-Host ""

Write-Host "Job Management:" -ForegroundColor Cyan
Write-Host "  • View jobs:       Get-Job" -ForegroundColor White
Write-Host "  • Stop API:        Stop-Job -Id $($apiJob.Id)" -ForegroundColor White
if (-not $NoCommandCenter) {
    Write-Host "  • Stop Dashboard:  Stop-Job -Id $($ccJob.Id)" -ForegroundColor White
}
Write-Host "  • Stop all:        Get-Job | Stop-Job; Get-Job | Remove-Job" -ForegroundColor White
Write-Host ""

Write-Host "Press Ctrl+C to stop monitoring (jobs will continue in background)" -ForegroundColor Yellow
Write-Host "Or run: " -NoNewline -ForegroundColor Yellow
Write-Host "Get-Job | Stop-Job; Get-Job | Remove-Job" -ForegroundColor White
Write-Host ""

# Monitor jobs
try {
    while ($true) {
        $jobs = Get-Job | Where-Object { $_.Id -in @($apiJob.Id, $ccJob.Id) }
        $running = ($jobs | Where-Object { $_.State -eq 'Running' }).Count
        
        if ($running -eq 0) {
            Write-Warn "All jobs have stopped!"
            break
        }
        
        Start-Sleep -Seconds 5
        
        # Show any errors
        foreach ($job in $jobs) {
            if ($job.State -eq 'Failed') {
                Write-Warn "Job $($job.Id) failed!"
                Receive-Job -Job $job
            }
        }
    }
} catch {
    Write-Host "`n[launch] Stopping monitoring..." -ForegroundColor Yellow
}

Write-Host "`nTo fully stop all services, run:" -ForegroundColor Yellow
Write-Host "  Get-Job | Stop-Job; Get-Job | Remove-Job" -ForegroundColor White
