Param(
  [string]$Drive = 'L:',
  [string[]]$Keep = @('zenml_project','GoodQ_Data','GoodQ_Pipeline','models','Tools','datasets','logs'),
  [switch]$Force,
  [switch]$DryRun,
  [switch]$Verbose
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Info($m){ Write-Host "[organize] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[organize] $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[organize] $m" -ForegroundColor Yellow }
function Fail($m){ Write-Error $m; exit 1 }

if (-not (Test-Path $Drive)) { Fail ("Drive not found: {0}" -f $Drive) }

# Resolve drive root robustly (handle 'L:' vs 'L:\')
if ($Drive -match '^[A-Za-z]:$') {
  $root = ($Drive + '\\')
} else {
  $root = (Get-Item -LiteralPath $Drive).FullName
}

# Safety: we're operating at resolved drive root in $root.
$legacyBase = Join-Path $root 'LEGACY'
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$legacyTarget = Join-Path $legacyBase $stamp

$systemNames = @('$RECYCLE.BIN','System Volume Information')
$keepFiles = @('zenml_project.code-workspace','GoodQ_Data.code-workspace','GoodQ_Pipeline.code-workspace')

# Build list of candidates at the root of the drive
$items = Get-ChildItem -LiteralPath $root -Force -ErrorAction SilentlyContinue
$candidates = @()
foreach ($it in $items) {
  if ($it.PSIsContainer) {
    if ($systemNames -contains $it.Name) { continue }
    if ($Keep -contains $it.Name) { continue }
    if ($it.Name.StartsWith('.')) { continue } # dotfolders (e.g. syncthing)
    $candidates += $it
  } else {
    if ($keepFiles -contains $it.Name) { continue }
    if ($it.Name -like 'desktop.ini') { continue }
    # Prefer moving loose artifacts like backups, scripts, temp files
    $candidates += $it
  }
}

if (-not $Force) {
  Info ("Preview of items to move to LEGACY\\{0}:" -f $stamp)
  foreach ($c in $candidates) { Write-Host ("  - {0}" -f $c.FullName) }
  $ans = Read-Host "Proceed with move? (y/N)"
  if ($ans.ToLowerInvariant() -ne 'y') { Write-Host 'Aborted.'; exit 0 }
}

if (-not $DryRun) {
  New-Item -ItemType Directory -Force -Path $legacyTarget | Out-Null
}

# Special case: prefer consolidated YOLO model under models/yolo/
function Handle-Yolo()
{
  $loose = Join-Path $root 'yolov8n.pt'
  if (Test-Path $loose) {
    $targetDir = Join-Path $root 'models\yolo'
    $targetPath = Join-Path $targetDir 'yolov8n.pt'
    if (-not (Test-Path $targetPath)) {
      if (-not $DryRun) { New-Item -ItemType Directory -Force -Path $targetDir | Out-Null }
      Info ("Relocating {0} -> {1}" -f $loose, $targetPath)
      if (-not $DryRun) { Move-Item -LiteralPath $loose -Destination $targetPath -Force }
    } else {
      Info ("Root yolov8n.pt already consolidated; sending loose file to LEGACY")
      if (-not $DryRun) { Move-Item -LiteralPath $loose -Destination $legacyTarget -Force }
    }
  }
}

Handle-Yolo

foreach ($c in $candidates) {
  $dest = Join-Path $legacyTarget $c.Name
  Info ("Moving {0} -> {1}" -f $c.FullName, $dest)
  if (-not $DryRun) {
    try {
      Move-Item -LiteralPath $c.FullName -Destination $dest -Force -ErrorAction Stop
    } catch {
      Warn ("Failed to move {0}: {1}" -f $c.FullName, $_)
    }
  }
}

Ok ("Organize complete. Review: {0}" -f $legacyTarget)
