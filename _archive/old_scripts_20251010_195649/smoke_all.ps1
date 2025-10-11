Param(
  [string]$EnvPrefix = 'goodq'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Ok($m){ Write-Host "[ok] $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[warn] $m" -ForegroundColor Yellow }
function Info($m){ Write-Host "[info] $m" -ForegroundColor Cyan }

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot

Info 'Health check + sanity'
& pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'mission_health_check.ps1') -EnvPrefix $EnvPrefix -FixMissingCaches -SmokeAll

Info 'Reconcile indices'
& pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'reconcile_indices.ps1') -EnvPrefix $EnvPrefix

Info 'Export run profile'
& pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'export_run_profile.ps1')

Info 'Export gallery'
& pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'export_gallery.ps1')

Ok 'Smoke all complete.'

