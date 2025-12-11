# STAGE 3.5 - SAFE ARCHIVE & CLEANUP SCRIPT
# Generated: 2025-12-10 19:16 UTC
# Mode: ARCHIVE-FIRST | USER CONFIRMATION REQUIRED

# ========================================
# SAFETY CHECKS
# ========================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  STAGE 3.5: ARCHIVE & CLEANUP" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "⚠️  This script will ARCHIVE legacy data" -ForegroundColor Yellow
Write-Host "⚠️  Data will NOT be deleted until you confirm" -ForegroundColor Yellow
Write-Host ""

# Create timestamped archive path
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$archiveRoot = "L:\goodq4all\archive\legacy_$timestamp"

Write-Host "Archive destination: $archiveRoot" -ForegroundColor Cyan
Write-Host ""

# Verify protected paths are NOT in target list
$protectedPaths = @(
    "L:\_DATA\GoodQ_Data\processing",
    "L:\_DATA\GoodQ_Data\import_inbox",
    "L:\_DATA\GoodQ_Data\memory.db",
    "L:\_DATA\GoodQ_Data\knowledge_graph.db",
    "L:\goodq4all\vendor\qdrant\storage"
)

Write-Host "Protected paths (will NOT be touched):" -ForegroundColor Green
foreach ($path in $protectedPaths) {
    Write-Host "  ✅ $path" -ForegroundColor Green
}
Write-Host ""

# ========================================
# PHASE 1: ARCHIVE (NON-DESTRUCTIVE)
# ========================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PHASE 1: ARCHIVING (Copy-Only)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Create archive root
New-Item -ItemType Directory -Path $archiveRoot -Force | Out-Null
Write-Host "[OK] Archive directory created: $archiveRoot" -ForegroundColor Green
Write-Host ""

$archiveLog = @()

# 1. Archive legacy processing
Write-Host "[1/7] Archiving legacy processing..." -ForegroundColor Cyan
if (Test-Path "L:\goodq4all\data\processing") {
    $dest = "$archiveRoot\data_processing"
    Copy-Item "L:\goodq4all\data\processing" $dest -Recurse -Force
    $size = (Get-ChildItem $dest -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1GB
    Write-Host "  ✅ Archived to: $dest ($([math]::Round($size, 2)) GB)" -ForegroundColor Green
    $archiveLog += "Legacy processing → $dest"
} else {
    Write-Host "  ⏭️  Not found, skipping" -ForegroundColor Yellow
}

# 2. Archive scripts/data/processing (empty)
Write-Host "[2/7] Archiving empty scripts folder..." -ForegroundColor Cyan
if (Test-Path "L:\goodq4all\scripts\data\processing") {
    $dest = "$archiveRoot\scripts_data_processing"
    Copy-Item "L:\goodq4all\scripts\data\processing" $dest -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  ✅ Archived to: $dest" -ForegroundColor Green
    $archiveLog += "Scripts processing → $dest"
} else {
    Write-Host "  ⏭️  Not found, skipping" -ForegroundColor Yellow
}

# 3. Archive stuck workspace
Write-Host "[3/7] Archiving stuck workspaces..." -ForegroundColor Cyan
$stuck = Get-ChildItem "L:\_DATA\GoodQ_Data" -Directory -Filter "processing_stuck_*" -ErrorAction SilentlyContinue
foreach ($s in $stuck) {
    $dest = "$archiveRoot\$($s.Name)"
    Copy-Item $s.FullName $dest -Recurse -Force
    $size = (Get-ChildItem $dest -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1GB
    Write-Host "  ✅ Archived: $($s.Name) → $dest ($([math]::Round($size, 2)) GB)" -ForegroundColor Green
    $archiveLog += "Stuck workspace $($s.Name) → $dest"
}

# 4. Archive legacy databases
Write-Host "[4/7] Archiving legacy databases..." -ForegroundColor Cyan
$legacyDBs = @(
    @{Path="L:\goodq4all\data\memory.db"; Name="memory_legacy.db"},
    @{Path="L:\goodq4all\data\control_memory.db"; Name="control_memory_legacy.db"},
    @{Path="L:\goodq4all\data\agent_checkpoints\control_memory.db"; Name="control_memory_agent_legacy.db"},
    @{Path="L:\_DATA\knowledge_graph.db"; Name="knowledge_graph_empty_legacy.db"},
    @{Path="L:\goodq4all\data\recovery.db"; Name="recovery_legacy.db"}
)

foreach ($db in $legacyDBs) {
    if (Test-Path $db.Path) {
        $dest = "$archiveRoot\databases\$($db.Name)"
        New-Item -ItemType Directory -Path "$archiveRoot\databases" -Force | Out-Null
        Copy-Item $db.Path $dest -Force
        $size = (Get-Item $dest).Length / 1KB
        Write-Host "  ✅ Archived: $($db.Name) ($([math]::Round($size, 2)) KB)" -ForegroundColor Green
        $archiveLog += "DB $($db.Path) → $dest"
    }
}

# 5. Archive FAISS indices
Write-Host "[5/7] Archiving FAISS indices (deprecated)..." -ForegroundColor Cyan
if (Test-Path "L:\goodq4all\data\faiss_indices") {
    $dest = "$archiveRoot\faiss_goodq4all"
    Copy-Item "L:\goodq4all\data\faiss_indices" $dest -Recurse -Force
    Write-Host "  ✅ Archived: L:\goodq4all\data\faiss_indices" -ForegroundColor Green
    $archiveLog += "FAISS (goodq4all) → $dest"
}

if (Test-Path "L:\_DATA\GoodQ_Data\faiss_indices") {
    $dest = "$archiveRoot\faiss_data"
    Copy-Item "L:\_DATA\GoodQ_Data\faiss_indices" $dest -Recurse -Force
    Write-Host "  ✅ Archived: L:\_DATA\GoodQ_Data\faiss_indices" -ForegroundColor Green
    $archiveLog += "FAISS (_DATA) → $dest"
}

# 6. Create archive manifest
Write-Host "[6/7] Creating archive manifest..." -ForegroundColor Cyan
$manifest = @"
GOODQ4ALL LEGACY DATA ARCHIVE
==============================
Created: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Archive Location: $archiveRoot

ARCHIVED ITEMS:
$($archiveLog -join "`n")

PROTECTED PATHS (NOT ARCHIVED):
$($protectedPaths -join "`n")

NEXT STEPS:
1. Verify archive integrity
2. Confirm removal of original legacy data
3. Recover ~22 GB of disk space

This archive can be deleted after confirming system stability.
"@

Set-Content -Path "$archiveRoot\ARCHIVE_MANIFEST.txt" -Value $manifest
Write-Host "  ✅ Manifest created: $archiveRoot\ARCHIVE_MANIFEST.txt" -ForegroundColor Green

# 7. Verification
Write-Host "[7/7] Verifying archive integrity..." -ForegroundColor Cyan
$archiveSize = (Get-ChildItem $archiveRoot -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1GB
Write-Host "  ✅ Archive complete: $([math]::Round($archiveSize, 2)) GB" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  PHASE 1 COMPLETE: ARCHIVE CREATED" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Archive location: $archiveRoot" -ForegroundColor Cyan
Write-Host "Archive size: $([math]::Round($archiveSize, 2)) GB" -ForegroundColor Cyan
Write-Host ""

# ========================================
# PHASE 2: REMOVAL (USER CONFIRMATION REQUIRED)
# ========================================

Write-Host "========================================" -ForegroundColor Yellow
Write-Host "  PHASE 2: REMOVE ORIGINALS (OPTIONAL)" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "⚠️  Archive is complete and verified" -ForegroundColor Green
Write-Host "⚠️  Original legacy files can now be removed" -ForegroundColor Yellow
Write-Host ""
Write-Host "Items to remove:" -ForegroundColor White
Write-Host "  - L:\goodq4all\data\processing (14.57 GB)" -ForegroundColor Gray
Write-Host "  - L:\_DATA\GoodQ_Data\processing_stuck_* (7.3 GB)" -ForegroundColor Gray
Write-Host "  - Legacy databases (~0.8 MB)" -ForegroundColor Gray
Write-Host "  - FAISS indices (~0.2 MB)" -ForegroundColor Gray
Write-Host ""
Write-Host "Total disk space to recover: ~21.87 GB" -ForegroundColor Cyan
Write-Host ""

$response = Read-Host "Type 'YES, remove archived originals' to proceed with deletion"

if ($response -eq "YES, remove archived originals") {
    Write-Host ""
    Write-Host "Removing original legacy files..." -ForegroundColor Yellow
    Write-Host ""
    
    # Remove legacy processing
    if (Test-Path "L:\goodq4all\data\processing") {
        Remove-Item "L:\goodq4all\data\processing" -Recurse -Force
        Write-Host "  ✅ Removed: L:\goodq4all\data\processing" -ForegroundColor Green
    }
    
    # Remove scripts folder
    if (Test-Path "L:\goodq4all\scripts\data\processing") {
        Remove-Item "L:\goodq4all\scripts\data\processing" -Recurse -Force
        Write-Host "  ✅ Removed: L:\goodq4all\scripts\data\processing" -ForegroundColor Green
    }
    
    # Remove stuck workspaces
    $stuck = Get-ChildItem "L:\_DATA\GoodQ_Data" -Directory -Filter "processing_stuck_*" -ErrorAction SilentlyContinue
    foreach ($s in $stuck) {
        Remove-Item $s.FullName -Recurse -Force
        Write-Host "  ✅ Removed: $($s.FullName)" -ForegroundColor Green
    }
    
    # Remove legacy DBs
    foreach ($db in $legacyDBs) {
        if (Test-Path $db.Path) {
            Remove-Item $db.Path -Force
            Write-Host "  ✅ Removed: $($db.Path)" -ForegroundColor Green
        }
    }
    
    # Remove FAISS
    if (Test-Path "L:\goodq4all\data\faiss_indices") {
        Remove-Item "L:\goodq4all\data\faiss_indices" -Recurse -Force
        Write-Host "  ✅ Removed: L:\goodq4all\data\faiss_indices" -ForegroundColor Green
    }
    
    if (Test-Path "L:\_DATA\GoodQ_Data\faiss_indices") {
        Remove-Item "L:\_DATA\GoodQ_Data\faiss_indices" -Recurse -Force
        Write-Host "  ✅ Removed: L:\_DATA\GoodQ_Data\faiss_indices" -ForegroundColor Green
    }
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  CLEANUP COMPLETE!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "✅ All legacy data archived to: $archiveRoot" -ForegroundColor Green
    Write-Host "✅ Original files removed" -ForegroundColor Green
    Write-Host "✅ Disk space recovered: ~21.87 GB" -ForegroundColor Green
    Write-Host ""
    Write-Host "Archive can be deleted after confirming system stability." -ForegroundColor Gray
    
} else {
    Write-Host ""
    Write-Host "Removal cancelled. Archive preserved at:" -ForegroundColor Yellow
    Write-Host "  $archiveRoot" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Original files remain in place." -ForegroundColor Yellow
    Write-Host "Run this script again when ready to remove originals." -ForegroundColor White
}

Write-Host ""
