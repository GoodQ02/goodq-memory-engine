#Requires -Version 5.1
<#
.SYNOPSIS
    GoodQ Intelligence Report - Shows processing results
.DESCRIPTION
    Displays mission intelligence from processed videos
#>

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "     [MISSION INTEL] GoodQ Intelligence Report                 " -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# Database path
$dbPath = "L:\goodq4all\data\memory.db"

if (-not (Test-Path $dbPath)) {
    Write-Host "[!] No intelligence database found" -ForegroundColor Yellow
    Write-Host "    Location: $dbPath" -ForegroundColor Gray
    Write-Host "    Run ingestion first to generate intelligence" -ForegroundColor Gray
    Write-Host ""
    exit 0
}

# Python script to query database
$pyScript = @"
import sqlite3
import json
import sys
from pathlib import Path

conn = sqlite3.connect('L:/goodq4all/data/memory.db')
c = conn.cursor()

# Basic stats
c.execute('SELECT COUNT(*) FROM scenes')
scene_count = c.fetchone()[0]

c.execute('SELECT COUNT(*) FROM embeddings')
emb_count = c.fetchone()[0]

c.execute('SELECT COUNT(*) FROM links')
link_count = c.fetchone()[0]

print(f'Scenes: {scene_count}')
print(f'Embeddings: {emb_count}')
print(f'Links: {link_count}')

# Modality breakdown
c.execute('SELECT modality, COUNT(*) FROM embeddings GROUP BY modality')
modalities = c.fetchall()
if modalities:
    print('MODALITIES')
    for mod, cnt in modalities:
        print(f'{mod}:{cnt}')

# Scenes with metadata
c.execute('SELECT COUNT(*) FROM scenes WHERE meta IS NOT NULL')
meta_count = c.fetchone()[0]
print(f'MetaScenes:{meta_count}')

# Sample scenes
c.execute('''
    SELECT start, end, meta 
    FROM scenes 
    WHERE meta IS NOT NULL 
    ORDER BY start 
    LIMIT 10
''')
scenes_data = c.fetchall()
if scenes_data:
    print('SCENES_START')
    for start, end, meta in scenes_data:
        try:
            meta_dict = json.loads(meta) if meta else {}
            caption = meta_dict.get('caption', '(processing)')
            timestamp = f'{int(start//60):02d}:{int(start%60):02d}'
            print(f'{timestamp}|{caption[:80]}')
        except:
            pass
    print('SCENES_END')

conn.close()
"@

try {
    # Run query
    $output = conda run -n goodq_zenml python -c $pyScript 2>$null

    # Parse output
    $stats = @{}
    $modalities = @()
    $scenes = @()
    $inScenes = $false

    foreach ($line in $output) {
        if ($line -eq 'SCENES_START') {
            $inScenes = $true
            continue
        }
        if ($line -eq 'SCENES_END') {
            $inScenes = $false
            continue
        }

        if ($inScenes) {
            $scenes += $line
        } elseif ($line -like '*:*') {
            $parts = $line -split ':', 2
            if ($parts[0] -eq 'MODALITIES') {
                continue
            }
            if ($parts[0] -match '^[a-z_]+$') {
                $modalities += "$($parts[0]): $($parts[1])"
            } else {
                $stats[$parts[0]] = $parts[1]
            }
        }
    }

    # Display results
    Write-Host "[MISSION SUMMARY]" -ForegroundColor Green
    Write-Host "  Scenes Analyzed:       $($stats['Scenes'])" -ForegroundColor White
    Write-Host "  Embeddings Created:    $($stats['Embeddings'])" -ForegroundColor White
    Write-Host "  Knowledge Links:       $($stats['Links'])" -ForegroundColor White
    Write-Host "  Scenes with Metadata:  $($stats['MetaScenes'])" -ForegroundColor White
    Write-Host ""

    if ($modalities.Count -gt 0) {
        Write-Host "[INTELLIGENCE BY MODALITY]" -ForegroundColor Green
        foreach ($mod in $modalities) {
            Write-Host "  $mod" -ForegroundColor White
        }
        Write-Host ""
    }

    if ($scenes.Count -gt 0) {
        Write-Host "[SCENE HIGHLIGHTS]" -ForegroundColor Green
        $i = 1
        foreach ($scene in $scenes) {
            $parts = $scene -split '\|', 2
            if ($parts.Count -eq 2) {
                Write-Host "  $("{0,2}" -f $i). [$($parts[0])] $($parts[1])" -ForegroundColor White
                $i++
            }
        }
        Write-Host ""
    }

    # Show workspaces
    Write-Host "[DATA LOCATIONS]" -ForegroundColor Green
    Write-Host "  Database: L:\goodq4all\data\memory.db" -ForegroundColor White
    
    $workspaces = Get-ChildItem "L:\goodq4all\logs" -Directory | Where-Object { $_.Name -like "watchdog_*" } | Sort-Object CreationTime -Descending | Select-Object -First 3
    if ($workspaces) {
        Write-Host "  Recent Workspaces:" -ForegroundColor White
        foreach ($ws in $workspaces) {
            $size = (Get-ChildItem $ws.FullName -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB
            Write-Host "    $($ws.Name) ($($size.ToString('F2')) MB)" -ForegroundColor Gray
        }
    }
    Write-Host ""

    Write-Host "[OK] Mission Status: INTELLIGENCE SUCCESSFULLY EXTRACTED" -ForegroundColor Green
    Write-Host ""

} catch {
    Write-Host "[ERROR] Failed to retrieve intelligence" -ForegroundColor Red
    Write-Host "  $($_.Exception.Message)" -ForegroundColor Gray
    Write-Host ""
    exit 1
}

