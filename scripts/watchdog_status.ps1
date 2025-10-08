# GoodQ Watchdog Status Dashboard
# Quick overview of watchdog activity and file processing

param(
    [switch]$Follow,
    [int]$RefreshSeconds = 5
)

$watchDir = "L:\GoodQ_4_All\import_inbox"
$processingDir = "L:\GoodQ_4_All\data\processing"
$processedDir = "L:\GoodQ_4_All\data\processed"
$failedDir = "L:\GoodQ_4_All\data\failed"
$stateFile = "L:\GoodQ_4_All\logs\watchdog_state.json"
$logFile = "L:\GoodQ_4_All\logs\watchdog.log"

function Show-Status {
    Clear-Host
    Write-Host "=" -NoNewline -ForegroundColor Cyan
    Write-Host "=" * 69 -ForegroundColor Cyan
    Write-Host "  GoodQ Watchdog Status Dashboard" -ForegroundColor Yellow
    Write-Host "=" -NoNewline -ForegroundColor Cyan
    Write-Host "=" * 69 -ForegroundColor Cyan
    Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
    Write-Host ""

    # Check if watchdog is running
    $watchdogProc = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -like '*watchdog_ingest*'
    }
    
    if ($watchdogProc) {
        Write-Host "  Status: " -NoNewline
        Write-Host "RUNNING" -ForegroundColor Green
        Write-Host "  PID: $($watchdogProc.Id)" -ForegroundColor Gray
        Write-Host "  CPU: $([math]::Round($watchdogProc.CPU, 2))s" -ForegroundColor Gray
        Write-Host "  Memory: $([math]::Round($watchdogProc.WorkingSet64/1MB, 2)) MB" -ForegroundColor Gray
    } else {
        Write-Host "  Status: " -NoNewline
        Write-Host "STOPPED" -ForegroundColor Red
        Write-Host "  Run START_WATCHDOG.bat to start" -ForegroundColor Yellow
    }
    Write-Host ""

    # File counts
    Write-Host "  Directories:" -ForegroundColor Cyan
    
    $inboxFiles = @()
    $processingFiles = @()
    $processedFiles = @()
    $failedFiles = @()
    
    if (Test-Path $watchDir) {
        $inboxFiles = Get-ChildItem $watchDir -File | Where-Object { $_.Name -notmatch '^PROCESSED_|^FAILED_' }
    }
    if (Test-Path $processingDir) {
        $processingFiles = Get-ChildItem $processingDir -File
    }
    if (Test-Path $processedDir) {
        $processedFiles = Get-ChildItem $processedDir -File
    }
    if (Test-Path $failedDir) {
        $failedFiles = Get-ChildItem $failedDir -File
    }
    
    Write-Host "    Inbox (import_inbox):     " -NoNewline
    Write-Host "$($inboxFiles.Count) files" -ForegroundColor $(if($inboxFiles.Count -gt 0){"Yellow"}else{"Gray"})
    
    Write-Host "    Processing:               " -NoNewline
    Write-Host "$($processingFiles.Count) files" -ForegroundColor $(if($processingFiles.Count -gt 0){"Yellow"}else{"Gray"})
    
    Write-Host "    Processed:                " -NoNewline
    Write-Host "$($processedFiles.Count) files" -ForegroundColor Green
    
    Write-Host "    Failed:                   " -NoNewline
    Write-Host "$($failedFiles.Count) files" -ForegroundColor $(if($failedFiles.Count -gt 0){"Red"}else{"Gray"})
    Write-Host ""

    # Registry stats
    if (Test-Path $stateFile) {
        $registry = Get-Content $stateFile -Raw | ConvertFrom-Json
        $total = ($registry.PSObject.Properties | Measure-Object).Count
        $successful = 0
        $failed = 0
        
        $registry.PSObject.Properties | ForEach-Object {
            if ($_.Value.status -eq 'success') { $successful++ }
            elseif ($_.Value.status -eq 'failed') { $failed++ }
        }
        
        Write-Host "  Registry (all-time):" -ForegroundColor Cyan
        Write-Host "    Total processed:          " -NoNewline
        Write-Host "$total files" -ForegroundColor Gray
        Write-Host "    Successful:               " -NoNewline
        Write-Host "$successful files" -ForegroundColor Green
        Write-Host "    Failed:                   " -NoNewline
        Write-Host "$failed files" -ForegroundColor $(if($failed -gt 0){"Red"}else{"Gray"})
        Write-Host ""
    }

    # Recent inbox files
    if ($inboxFiles.Count -gt 0) {
        Write-Host "  Files in Inbox:" -ForegroundColor Cyan
        $inboxFiles | Select-Object -First 5 | ForEach-Object {
            $sizeMB = [math]::Round($_.Length / 1MB, 2)
            $ext = $_.Extension.ToLower()
            $icon = switch ($ext) {
                {$_ -in '.mp4','.avi','.mov','.mkv'} { "[VID]" }
                {$_ -in '.mp3','.wav','.flac'} { "[AUD]" }
                {$_ -in '.jpg','.jpeg','.png'} { "[IMG]" }
                {$_ -in '.pdf','.txt','.md'} { "[DOC]" }
                default { "[FILE]" }
            }
            Write-Host "    $icon $($_.Name) " -NoNewline -ForegroundColor Yellow
            Write-Host "($sizeMB MB)" -ForegroundColor Gray
        }
        if ($inboxFiles.Count -gt 5) {
            Write-Host "    ... and $($inboxFiles.Count - 5) more" -ForegroundColor Gray
        }
        Write-Host ""
    }

    # Recent log entries
    if (Test-Path $logFile) {
        Write-Host "  Recent Activity:" -ForegroundColor Cyan
        $recentLines = Get-Content $logFile -Tail 8 | ForEach-Object {
            if ($_ -match '\[INFO\]') {
                Write-Host "    " -NoNewline
                Write-Host $_ -ForegroundColor Gray
            }
            elseif ($_ -match '\[ERROR\]') {
                Write-Host "    " -NoNewline
                Write-Host $_ -ForegroundColor Red
            }
            elseif ($_ -match '\[WARNING\]') {
                Write-Host "    " -NoNewline
                Write-Host $_ -ForegroundColor Yellow
            }
        }
        Write-Host ""
    }

    Write-Host "=" -NoNewline -ForegroundColor Cyan
    Write-Host "=" * 69 -ForegroundColor Cyan
    
    if ($Follow) {
        Write-Host ""
        Write-Host "  Refreshing in $RefreshSeconds seconds... (Ctrl+C to stop)" -ForegroundColor Gray
    }
}

# Main execution
if ($Follow) {
    while ($true) {
        Show-Status
        Start-Sleep -Seconds $RefreshSeconds
    }
} else {
    Show-Status
}
