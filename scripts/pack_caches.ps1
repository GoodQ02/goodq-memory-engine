Param(
  [string]$OutDir = 'logs/cache_packs'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Info($m){ Write-Host "[pack] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[pack] $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[pack] $m" -ForegroundColor Yellow }
function Fail($m){ Write-Error $m; exit 1 }

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot

$hf = [Environment]::GetEnvironmentVariable('HF_HOME','User'); if (-not $hf) { $hf = [Environment]::GetEnvironmentVariable('HF_HOME','Process') }
$th = [Environment]::GetEnvironmentVariable('TORCH_HOME','User'); if (-not $th) { $th = [Environment]::GetEnvironmentVariable('TORCH_HOME','Process') }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

if ($hf -and (Test-Path $hf)) {
  $zip = Join-Path $OutDir ("hf_cache_" + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.zip')
  Info ("Packing HF_HOME from {0}" -f $hf)
  Add-Type -AssemblyName 'System.IO.Compression.FileSystem'
  [System.IO.Compression.ZipFile]::CreateFromDirectory($hf, $zip)
  Ok ("Wrote {0}" -f $zip)
} else { Warn 'HF_HOME not set or missing' }

if ($th -and (Test-Path $th)) {
  $zip = Join-Path $OutDir ("torch_cache_" + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.zip')
  Info ("Packing TORCH_HOME from {0}" -f $th)
  Add-Type -AssemblyName 'System.IO.Compression.FileSystem'
  [System.IO.Compression.ZipFile]::CreateFromDirectory($th, $zip)
  Ok ("Wrote {0}" -f $zip)
} else { Warn 'TORCH_HOME not set or missing' }

