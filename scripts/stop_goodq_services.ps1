#!/usr/bin/env pwsh
# Stop all GoodQ services gracefully

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

Write-Host "`n╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "║              Stopping GoodQ Services                          ║" -ForegroundColor Yellow
Write-Host "╚═══════════════════════════════════════════════════════════════╝`n" -ForegroundColor Yellow

# Stop PowerShell jobs
Write-Host "[stop] Checking for background jobs..." -ForegroundColor Cyan
$jobs = Get-Job | Where-Object { $_.Name -like "*GoodQ*" -or $_.Command -like "*goodq*" }

if ($jobs) {
    Write-Host "[stop] Found $($jobs.Count) GoodQ job(s)" -ForegroundColor Yellow
    foreach ($job in $jobs) {
        Write-Host "  • Stopping job $($job.Id): $($job.Name)" -ForegroundColor White
        Stop-Job -Job $job -ErrorAction SilentlyContinue
        Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
    }
    Write-Host "[stop] ✓ Jobs stopped" -ForegroundColor Green
} else {
    Write-Host "[stop] No background jobs found" -ForegroundColor Gray
}

# Stop processes on API port
Write-Host "`n[stop] Checking for processes on port 8000..." -ForegroundColor Cyan
try {
    $connections = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
    if ($connections) {
        foreach ($conn in $connections) {
            $process = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
            if ($process) {
                Write-Host "  • Stopping process: $($process.ProcessName) (PID: $($process.Id))" -ForegroundColor Yellow
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            }
        }
        Write-Host "[stop] ✓ Port 8000 cleared" -ForegroundColor Green
    } else {
        Write-Host "[stop] Port 8000 already free" -ForegroundColor Gray
    }
} catch {
    Write-Host "[stop] Could not check port 8000: $_" -ForegroundColor Yellow
}

# Stop any uvicorn processes
Write-Host "`n[stop] Checking for uvicorn processes..." -ForegroundColor Cyan
$uvicorn = Get-Process | Where-Object { $_.ProcessName -like "*uvicorn*" -or $_.CommandLine -like "*uvicorn*" }
if ($uvicorn) {
    foreach ($proc in $uvicorn) {
        Write-Host "  • Stopping: $($proc.ProcessName) (PID: $($proc.Id))" -ForegroundColor Yellow
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "[stop] ✓ Uvicorn processes stopped" -ForegroundColor Green
} else {
    Write-Host "[stop] No uvicorn processes found" -ForegroundColor Gray
}

Write-Host "`n╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                 ✓ Services Stopped                            ║" -ForegroundColor Green
Write-Host "╚═══════════════════════════════════════════════════════════════╝`n" -ForegroundColor Green

Write-Host "All GoodQ services have been stopped." -ForegroundColor White
Write-Host "You can now close any remaining PowerShell windows manually.`n" -ForegroundColor Gray
