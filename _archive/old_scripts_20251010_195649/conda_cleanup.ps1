Param(
  [switch]$CleanPkgs,
  [switch]$CleanCache
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Info($m){ Write-Host "[conda] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[conda] $m" -ForegroundColor Green }
function Fail($m){ Write-Error $m; exit 1 }

if (-not (Get-Command conda -ErrorAction SilentlyContinue)) { Fail 'conda not found' }

if ($CleanPkgs -or $CleanCache) {
  Info 'Running conda clean'
  $args = @('clean','-y')
  if ($CleanPkgs) { $args += '-p' }
  if ($CleanCache) { $args += '-t'; $args += '-a' }
  & conda @args
  Ok 'Conda clean complete'
} else {
  Info 'No actions requested. Use -CleanPkgs and/or -CleanCache.'
}

