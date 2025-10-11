Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Info($m){ Write-Host "[ci] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[ci] $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[ci] $m" -ForegroundColor Yellow }
function Fail($m){ Write-Error $m; exit 1 }

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot

Param(
  [string]$EnvPrefix = 'goodq',
  [double]$MaxDrift = 0.15
)

Info 'Locking envs with pip-tools'
& pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'lock_envs.ps1') -EnvPrefix $EnvPrefix -UpgradePipTools -GenerateIn

Info 'Reconciling indices'
$out = & pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'reconcile_indices.ps1') -EnvPrefix $EnvPrefix
Write-Host $out
if ($out -match 'drift=([0-9]+\.?[0-9]*)%') {
  # this regex finds only the first; do a coarse failure on any percentage above threshold
  $matches = [regex]::Matches($out, 'drift=([0-9]+\.?[0-9]*)%')
  foreach ($m in $matches) {
    $p = [double]$m.Groups[1].Value / 100.0
    if ($p -gt $MaxDrift) { Fail ("Drift exceeded threshold: {0:P1} > {1:P1}" -f $p, $MaxDrift) }
  }
}

Ok 'CI verify passed.'

