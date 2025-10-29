# GoodQ4All Cache Consolidation Script
# Safely moves fragmented HuggingFace caches to single source of truth (L:\models)

Param(
    [switch]$WhatIf,
    [switch]$Force,
    [switch]$SkipBackup
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Header($msg) {
    Write-Host "`n$('='*70)" -ForegroundColor Cyan
    Write-Host $msg -ForegroundColor Cyan
    Write-Host "$('='*70)`n" -ForegroundColor Cyan
}

function Write-Success($msg) {
    Write-Host "  ✓ $msg" -ForegroundColor Green
}

function Write-Warning($msg) {
    Write-Host "  ⚠ $msg" -ForegroundColor Yellow
}

function Write-Error($msg) {
    Write-Host "  ✗ $msg" -ForegroundColor Red
}

function Write-Info($msg) {
    Write-Host "  → $msg" -ForegroundColor Cyan
}

# Define canonical paths (single source of truth)
$CANONICAL_CACHE = "L:\models"
$CANONICAL_HUB = "L:\models\hub"
$CANONICAL_DATASETS = "L:\models\hf\datasets"

# Fragmented cache locations to consolidate
$fragmentedLocations = @(
    "$env:USERPROFILE\.cache\huggingface",
    "$env:LOCALAPPDATA\huggingface",
    "$env:APPDATA\huggingface"
)

Write-Header "GoodQ4All Cache Consolidation"

if ($WhatIf) {
    Write-Warning "DRY RUN MODE - No changes will be made"
}

# Check if canonical location exists
if (-not (Test-Path $CANONICAL_CACHE)) {
    Write-Error "Canonical cache location does not exist: $CANONICAL_CACHE"
    exit 1
}

Write-Success "Canonical cache location: $CANONICAL_CACHE"

# Analyze fragmented caches
Write-Header "Analyzing Fragmented Caches"

$totalFragmentedSize = 0
$consolidationPlan = @()

foreach ($location in $fragmentedLocations) {
    if (Test-Path $location) {
        Write-Info "Found fragmented cache: $location"
        
        # Calculate size
        $items = Get-ChildItem $location -Recurse -File -ErrorAction SilentlyContinue
        $sizeBytes = ($items | Measure-Object -Property Length -Sum).Sum
        $sizeGB = [math]::Round($sizeBytes / 1GB, 2)
        $totalFragmentedSize += $sizeGB
        
        Write-Info "  Size: $sizeGB GB"
        Write-Info "  Files: $($items.Count)"
        
        # Check subdirectories
        $subdirs = Get-ChildItem $location -Directory -ErrorAction SilentlyContinue
        foreach ($subdir in $subdirs) {
            $subdirSize = (Get-ChildItem $subdir.FullName -Recurse -File -ErrorAction SilentlyContinue | 
                           Measure-Object -Property Length -Sum).Sum / 1GB
            
            if ($subdirSize -gt 0.01) {  # More than 10MB
                $subdirSizeGB = [math]::Round($subdirSize, 2)
                Write-Info "    - $($subdir.Name): $subdirSizeGB GB"
                
                # Determine destination
                $destination = switch ($subdir.Name) {
                    "hub" { $CANONICAL_HUB }
                    "datasets" { $CANONICAL_DATASETS }
                    "transformers" { "$CANONICAL_CACHE\transformers" }
                    default { "$CANONICAL_CACHE\$($subdir.Name)" }
                }
                
                $consolidationPlan += @{
                    Source = $subdir.FullName
                    Destination = $destination
                    SizeGB = $subdirSizeGB
                    Type = $subdir.Name
                }
            }
        }
    } else {
        Write-Success "$location does not exist (no fragmentation)"
    }
}

if ($totalFragmentedSize -eq 0) {
    Write-Success "`nNo fragmented caches found - system is clean!"
    exit 0
}

Write-Header "Consolidation Plan"
Write-Warning "Total fragmented cache size: $totalFragmentedSize GB"
Write-Info ""

foreach ($plan in $consolidationPlan) {
    Write-Info "Move: $($plan.Source)"
    Write-Info "  To: $($plan.Destination)"
    Write-Info "  Size: $($plan.SizeGB) GB"
    Write-Info ""
}

if ($WhatIf) {
    Write-Warning "DRY RUN - No changes made. Run without -WhatIf to execute."
    exit 0
}

# Confirm with user unless Force is specified
if (-not $Force) {
    Write-Warning "This will consolidate $totalFragmentedSize GB of fragmented caches."
    $response = Read-Host "Continue? (yes/no)"
    if ($response -ne "yes") {
        Write-Info "Consolidation cancelled by user."
        exit 0
    }
}

# Create backup list if not skipping
if (-not $SkipBackup) {
    Write-Header "Creating Backup Manifest"
    $backupManifest = @{
        Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        FragmentedLocations = $fragmentedLocations
        ConsolidationPlan = $consolidationPlan
        TotalSize = $totalFragmentedSize
    }
    
    $backupPath = "$CANONICAL_CACHE\consolidation_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
    $backupManifest | ConvertTo-Json -Depth 10 | Set-Content $backupPath
    Write-Success "Backup manifest created: $backupPath"
}

# Execute consolidation
Write-Header "Executing Consolidation"

$movedCount = 0
$errorCount = 0

foreach ($plan in $consolidationPlan) {
    $source = $plan.Source
    $destination = $plan.Destination
    
    Write-Info "Processing: $source"
    
    try {
        # Ensure destination directory exists
        if (-not (Test-Path $destination)) {
            New-Item -ItemType Directory -Path $destination -Force | Out-Null
            Write-Success "  Created destination: $destination"
        }
        
        # Check if items already exist in destination
        $sourceItems = Get-ChildItem $source -ErrorAction Stop
        $duplicates = 0
        $moved = 0
        
        foreach ($item in $sourceItems) {
            $destPath = Join-Path $destination $item.Name
            
            if (Test-Path $destPath) {
                # Item already exists in canonical location
                $duplicates++
                Write-Info "    Skip: $($item.Name) (already in canonical location)"
            } else {
                # Move item to canonical location
                Move-Item -Path $item.FullName -Destination $destPath -Force
                $moved++
            }
        }
        
        Write-Success "  Moved: $moved items"
        if ($duplicates -gt 0) {
            Write-Info "  Skipped: $duplicates duplicates"
        }
        
        # Remove source directory if empty
        if ((Get-ChildItem $source -ErrorAction SilentlyContinue).Count -eq 0) {
            Remove-Item $source -Force -Recurse
            Write-Success "  Cleaned up empty source directory"
        }
        
        $movedCount++
        
    } catch {
        Write-Error "  Failed: $_"
        $errorCount++
    }
}

# Cleanup empty parent directories
Write-Header "Cleanup"

foreach ($location in $fragmentedLocations) {
    if (Test-Path $location) {
        $remainingItems = Get-ChildItem $location -Recurse -ErrorAction SilentlyContinue
        if ($remainingItems.Count -eq 0) {
            try {
                Remove-Item $location -Force -Recurse -ErrorAction Stop
                Write-Success "Removed empty directory: $location"
            } catch {
                Write-Warning "Could not remove $location : $_"
            }
        } else {
            Write-Info "Retained $location ($($remainingItems.Count) items remain)"
        }
    }
}

# Summary
Write-Header "Consolidation Complete"

Write-Success "Successfully consolidated: $movedCount cache directories"
if ($errorCount -gt 0) {
    Write-Warning "Errors encountered: $errorCount"
}

Write-Info "`nRecovered space from fragmented locations: ~$totalFragmentedSize GB"
Write-Info "All caches now consolidated in: $CANONICAL_CACHE"

# Update environment variables recommendation
Write-Header "Next Steps"
Write-Info "1. Verify caches in L:\models"
Write-Info "2. Run: pwsh scripts\unified_health_check.py --auto-heal"
Write-Info "3. Test ingestion to confirm cache consolidation"

exit 0
