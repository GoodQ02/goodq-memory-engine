Param(
  [string]$ModelsDir = 'L:/models',
  [switch]$DryRun = $true
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Note($m){ Write-Host "[hf-cache] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[hf-cache] $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[hf-cache] $m" -ForegroundColor Yellow }

if (-not (Test-Path $ModelsDir)) { throw "Models dir not found: $ModelsDir" }

$root = (Get-Item -LiteralPath $ModelsDir).FullName
$hub = Join-Path $root 'hub'
if (-not (Test-Path $hub)) { New-Item -ItemType Directory -Force -Path $hub | Out-Null }
$legacy = Join-Path $root ("legacy_hf_" + (Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Force -Path $legacy | Out-Null

$candidates = Get-ChildItem -LiteralPath $root -Directory | Where-Object { $_.Name -like 'models--*' -or $_.Name -like 'datasets--*' }

if (-not $candidates) { Ok 'No stray top-level HF cache folders found'; exit 0 }

foreach ($dir in $candidates) {
  $target = Join-Path $hub $dir.Name
  if (Test-Path $target) {
    Note ("Duplicate found: {0} (hub already has {1})" -f $dir.FullName, $target)
    $dest = Join-Path $legacy $dir.Name
    Note ("Moving duplicate to LEGACY: {0}" -f $dest)
    if (-not $DryRun) { Move-Item -LiteralPath $dir.FullName -Destination $dest -Force }
  } else {
    Note ("Consolidating {0} -> {1}" -f $dir.FullName, $target)
    if (-not $DryRun) { Move-Item -LiteralPath $dir.FullName -Destination $target -Force }
  }
}

Ok 'HF cache consolidation plan complete.'

