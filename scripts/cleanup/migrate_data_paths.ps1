# GoodQ4All Data Path Migration Script
# Consolidates all data to L:\_DATA\GoodQ_Data (canonical location)

$ErrorActionPreference = "Stop"

Write-Host "
========================================" -ForegroundColor Cyan
Write-Host "  GoodQ4All Data Path Migration" -ForegroundColor Cyan
Write-Host "========================================
" -ForegroundColor Cyan

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$archiveRoot = "L:\goodq4all\archive\data_migration_$timestamp"
$canonicalData = "L:\_DATA\GoodQ_Data"

if (!(Test-Path $canonicalData)) {
    New-Item -ItemType Directory -Path $canonicalData -Force | Out-Null
}

# MIGRATE KNOWLEDGE GRAPH DB
Write-Host "
[MIGRATE] Knowledge Graph Database..." -ForegroundColor Yellow
$legacyKG = "L:\goodq4all\data\knowledge_graph.db"
$canonicalKG = "$canonicalData\knowledge_graph.db"

if (Test-Path $legacyKG) {
    $legacySize = (Get-Item $legacyKG).Length
    $canonicalSize = if (Test-Path $canonicalKG) { (Get-Item $canonicalKG).Length } else { 0 }
    
    if ($legacySize -gt $canonicalSize) {
        Copy-Item $legacyKG $canonicalKG -Force
        New-Item -ItemType Directory -Path "$archiveRoot\legacy_kg" -Force | Out-Null
        Move-Item $legacyKG "$archiveRoot\legacy_kg\" -Force
    }
}

# MIGRATE CONTROL MEMORY DBs
Write-Host "
[MIGRATE] Control Memory Databases..." -ForegroundColor Yellow
if (Test-Path "L:\goodq4all\data\control_memory.db") {
    Copy-Item "L:\goodq4all\data\control_memory.db" "$canonicalData\control_memory.db" -Force
    New-Item -ItemType Directory -Path "$archiveRoot\legacy_control" -Force | Out-Null
    Move-Item "L:\goodq4all\data\control_memory.db" "$archiveRoot\legacy_control\" -Force
}

if (Test-Path "L:\goodq4all\data\agent_checkpoints") {
    New-Item -ItemType Directory -Path "$archiveRoot\legacy_checkpoints" -Force | Out-Null
    Move-Item "L:\goodq4all\data\agent_checkpoints" "$archiveRoot\legacy_checkpoints\" -Force
}

# ARCHIVE ACCIDENTAL QDRANT STORAGE
Write-Host "
[CLEANUP] Accidental Qdrant Storage..." -ForegroundColor Yellow
if (Test-Path "L:\goodq4all\data\qdrant_storage") {
    New-Item -ItemType Directory -Path "$archiveRoot\accidental_qdrant" -Force | Out-Null
    Move-Item "L:\goodq4all\data\qdrant_storage" "$archiveRoot\accidental_qdrant\" -Force
}

# CLEANUP EMPTY DIRECTORIES
if (Test-Path "L:\goodq4all\data") {
    $items = @(Get-ChildItem "L:\goodq4all\data" -Recurse)
    if ($items.Count -eq 0) {
        Remove-Item "L:\goodq4all\data" -Force
    }
}

Write-Host "
========================================" -ForegroundColor Cyan
Write-Host "  MIGRATION COMPLETE" -ForegroundColor Cyan
Write-Host "========================================
" -ForegroundColor Cyan
