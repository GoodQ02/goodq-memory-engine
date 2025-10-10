# GoodQ Ingestion Status Checker
# Quick status check for active ingestion and processing

param(
    [string]$LogFolder = "L:\goodq4all\logs"
)

$ErrorActionPreference = "SilentlyContinue"

Write-Host "`n╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║           GoodQ Ingestion Status Dashboard                    ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

# 1. Active Python Processes
Write-Host "=== Active Python Processes ===" -ForegroundColor Yellow
$pythonProcs = Get-Process python -ErrorAction SilentlyContinue
if ($pythonProcs) {
    foreach ($proc in $pythonProcs) {
        $memMB = [math]::Round($proc.WorkingSet64 / 1MB, 0)
        $cpuSec = [math]::Round($proc.CPU, 1)
        Write-Host "  PID $($proc.Id): ${memMB}MB RAM, ${cpuSec}s CPU, $($proc.Threads.Count) threads" -ForegroundColor Green
    }
} else {
    Write-Host "  No active Python processes" -ForegroundColor Gray
}

# 2. Latest Processing Folder
Write-Host "`n=== Latest Processing Session ===" -ForegroundColor Yellow
$latestFolder = Get-ChildItem $LogFolder -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($latestFolder) {
    Write-Host "  Folder: $($latestFolder.Name)" -ForegroundColor Green
    Write-Host "  Modified: $($latestFolder.LastWriteTime)" -ForegroundColor Green
    $age = (Get-Date) - $latestFolder.LastWriteTime
    $ageStr = if ($age.TotalMinutes -lt 60) { "$([math]::Round($age.TotalMinutes))m ago" } else { "$([math]::Round($age.TotalHours, 1))h ago" }
    Write-Host "  Age: $ageStr" -ForegroundColor Green
    
    # Check for video folders inside
    $videoFolders = Get-ChildItem $latestFolder.FullName -Directory
    foreach ($vf in $videoFolders) {
        Write-Host "`n  Video: $($vf.Name)" -ForegroundColor Cyan
        
        # Count scenes
        $audioPath = Join-Path $vf.FullName "audio"
        $framesPath = Join-Path $vf.FullName "frames"
        $audioCount = if (Test-Path $audioPath) { (Get-ChildItem $audioPath -Filter "scene_*.wav").Count } else { 0 }
        $frameCount = if (Test-Path $framesPath) { (Get-ChildItem $framesPath -Filter "scene_*.jpg").Count } else { 0 }
        
        Write-Host "    Scenes extracted: Audio=$audioCount, Frames=$frameCount" -ForegroundColor Magenta
        
        # Check step log
        $stepLog = Join-Path $latestFolder.FullName "step_log.jsonl"
        if (Test-Path $stepLog) {
            $stepCount = (Get-Content $stepLog).Count
            $lastSteps = Get-Content $stepLog | Select-Object -Last 3 | ConvertFrom-Json
            Write-Host "    Processing steps: $stepCount total" -ForegroundColor Magenta
            Write-Host "    Last 3 steps:" -ForegroundColor White
            foreach ($step in $lastSteps) {
                $icon = switch ($step.status) {
                    "ok" { "✓" }
                    "skipped" { "○" }
                    "error" { "✗" }
                    default { "?" }
                }
                $color = switch ($step.status) {
                    "ok" { "Green" }
                    "skipped" { "Yellow" }
                    "error" { "Red" }
                    default { "Gray" }
                }
                $timeMs = [math]::Round($step.elapsed_ms, 0)
                Write-Host "      $icon $($step.step_name) - ${timeMs}ms - $($step.status)" -ForegroundColor $color
            }
            
            # Calculate statistics
            $allSteps = Get-Content $stepLog | ConvertFrom-Json
            $okCount = ($allSteps | Where-Object { $_.status -eq "ok" }).Count
            $skipCount = ($allSteps | Where-Object { $_.status -eq "skipped" }).Count
            $errorCount = ($allSteps | Where-Object { $_.status -eq "error" }).Count
            Write-Host "    Summary: ✓ $okCount completed, ○ $skipCount skipped, ✗ $errorCount errors" -ForegroundColor White
        } else {
            Write-Host "    No step log found (processing not started)" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "  No processing folders found" -ForegroundColor Gray
}

# 3. Database Status
Write-Host "`n=== Database Status ===" -ForegroundColor Yellow
$dbPath = "L:\GoodQ_Data\db\goodq.db"
if (Test-Path $dbPath) {
    $dbSizeMB = [math]::Round((Get-Item $dbPath).Length / 1MB, 2)
    Write-Host "  Size: ${dbSizeMB}MB" -ForegroundColor Green
    Write-Host "  Modified: $((Get-Item $dbPath).LastWriteTime)" -ForegroundColor Green
} else {
    Write-Host "  Database not found" -ForegroundColor Gray
}

# 4. Import Inbox
Write-Host "`n=== Import Inbox ===" -ForegroundColor Yellow
$inboxPath = "L:\goodq4all\import_inbox"
if (Test-Path $inboxPath) {
    $videos = Get-ChildItem $inboxPath -Include *.mp4,*.avi,*.mov,*.mkv -File
    if ($videos) {
        Write-Host "  Videos waiting:" -ForegroundColor Cyan
        foreach ($v in $videos) {
            $sizeMB = [math]::Round($v.Length / 1MB, 0)
            Write-Host "    • $($v.Name) (${sizeMB}MB)" -ForegroundColor White
        }
    } else {
        Write-Host "  No videos in inbox" -ForegroundColor Gray
    }
}

# 5. Recent File Activity
Write-Host "`n=== Recent File Activity ===" -ForegroundColor Yellow
if ($latestFolder) {
    $recentFiles = Get-ChildItem $latestFolder.FullName -Recurse -File | 
        Sort-Object LastWriteTime -Descending | 
        Select-Object -First 5
    
    foreach ($file in $recentFiles) {
        $age = (Get-Date) - $file.LastWriteTime
        $ageStr = if ($age.TotalMinutes -lt 1) { "$([math]::Round($age.TotalSeconds))s ago" } elseif ($age.TotalMinutes -lt 60) { "$([math]::Round($age.TotalMinutes))m ago" } else { "$([math]::Round($age.TotalHours, 1))h ago" }
        Write-Host "  $($file.Name) - $ageStr" -ForegroundColor White
    }
}

Write-Host "`n" -NoNewline
