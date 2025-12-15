# GoodQ4All Entity Extraction Monitor
# Watches for entity extraction activity in real-time

param(
    [int]$RefreshSeconds = 30,
    [switch]$Continuous
)

function Show-EntityStats {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  ENTITY EXTRACTION MONITOR" -ForegroundColor Cyan
    Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
    
    # Check if ingestion is running
    $proc = Get-Process | Where-Object {$_.ProcessName -eq "python" -and $_.CommandLine -like "*run_ingestion*"} | Select-Object -First 1
    
    if ($proc) {
        $runtime = (Get-Date) - $proc.StartTime
        Write-Host "✅ Ingestion ACTIVE" -ForegroundColor Green
        Write-Host "   Runtime: $($runtime.ToString('hh\:mm\:ss'))" -ForegroundColor White
        Write-Host "   Memory: $([math]::Round($proc.WorkingSet64/1MB,2)) MB`n" -ForegroundColor White
    } else {
        Write-Host "⏸️  Ingestion NOT RUNNING`n" -ForegroundColor Yellow
    }
    
    # Check latest entity logs
    $logPath = "L:\goodq4all\logs\Entity Cataloging.log"
    if (Test-Path $logPath) {
        Write-Host "📊 Recent Entity Activity (last 10 lines):" -ForegroundColor Yellow
        $recent = Get-Content $logPath -Tail 10 -ErrorAction SilentlyContinue
        if ($recent) {
            $recent | ForEach-Object {
                if ($_ -match "entity|Entity|ENTITY") {
                    Write-Host "   $_" -ForegroundColor Green
                } else {
                    Write-Host "   $_" -ForegroundColor Gray
                }
            }
        }
    }
    
    # Check for KG stats in recent output
    Write-Host "`n🔍 Searching for Knowledge Graph updates..." -ForegroundColor Yellow
    $allLogs = @()
    Get-ChildItem "L:\goodq4all\logs\*.log" | ForEach-Object {
        $content = Get-Content $_.FullName -Tail 5 -ErrorAction SilentlyContinue
        $allLogs += $content
    }
    
    $kgMatches = $allLogs | Select-String -Pattern "\[kg\].*entities|total_nodes|person|entity" -ErrorAction SilentlyContinue
    if ($kgMatches) {
        Write-Host "   Found KG activity:" -ForegroundColor Green
        $kgMatches | Select-Object -First 5 | ForEach-Object {
            Write-Host "   $_" -ForegroundColor White
        }
    } else {
        Write-Host "   No KG activity detected yet" -ForegroundColor Gray
    }
    
    # Check WSL2 audio service
    Write-Host "`n🎙️  WSL2 Audio Service:" -ForegroundColor Yellow
    $wslCheck = wsl ps aux 2>$null | Select-String "audio_service"
    if ($wslCheck) {
        Write-Host "   ✅ Running" -ForegroundColor Green
    } else {
        Write-Host "   ⚠️  Not detected" -ForegroundColor Red
    }
    
    Write-Host "`n========================================`n" -ForegroundColor Cyan
}

# Main loop
if ($Continuous) {
    Write-Host "Starting continuous monitoring (Ctrl+C to stop)..." -ForegroundColor Cyan
    Write-Host "Refresh interval: $RefreshSeconds seconds`n" -ForegroundColor Yellow
    
    while ($true) {
        Clear-Host
        Show-EntityStats
        Start-Sleep -Seconds $RefreshSeconds
    }
} else {
    Show-EntityStats
}
