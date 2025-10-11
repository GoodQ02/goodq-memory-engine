Param(
  [string]$OutPath = 'logs/run_profile.json'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Info($m){ Write-Host "[profile] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[profile] $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[profile] $m" -ForegroundColor Yellow }

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot

function Read-PathsYaml {
  $f = 'configs/paths.yaml'
  $raw = Get-Content -LiteralPath $f -Raw
  $o = @{}
  foreach ($line in $raw -split "`n") { if ($line -match '^\s*([A-Za-z0-9_]+):\s*"(.*)"\s*$') { $o[$matches[1]] = $matches[2] } }
  return $o
}

$p = Read-PathsYaml
$logDir = if ($p['log_dir']) { $p['log_dir'] } else { (Join-Path $repoRoot 'logs') }
$jsonl = Join-Path $logDir 'step_runs.jsonl'
if (-not (Test-Path $jsonl)) { Warn 'No step_runs.jsonl found'; exit 0 }

$lines = Get-Content -LiteralPath $jsonl -Raw -ErrorAction Stop
$entries = @()
foreach ($ln in ($lines -split "`n")) { if ($ln.Trim()) { try { $entries += ($ln | ConvertFrom-Json) } catch {} } }

$byStep = @{}
foreach ($e in $entries) {
  $s = $e.step
  if (-not $byStep.ContainsKey($s)) { $byStep[$s] = @() }
  $byStep[$s] += $e
}

$summary = @{}
foreach ($k in $byStep.Keys) {
  $arr = $byStep[$k]
  $dur = 0.0; foreach ($x in $arr) { try { $dur += [double]$x.duration_ms } catch {} }
  $avg = if ($arr.Count -gt 0) { $dur / $arr.Count } else { 0.0 }
  $summary[$k] = @{ count = $arr.Count; avg_duration_ms = [double]::Parse("{0:F2}" -f $avg) }
}

$diag = @{ steps = $summary; total_entries = $entries.Count }

try { $cuda = (& nvidia-smi --query-gpu=name,driver_version --format=csv,noheader,nounits) } catch { $cuda = $null }
if ($cuda) { $diag['gpu'] = $cuda.Trim().Split("`n"); }

Set-Content -LiteralPath $OutPath -Value (ConvertTo-Json -Depth 6 $diag) -Encoding UTF8
Ok ("Wrote {0}" -f $OutPath)

