Param(
  [ValidateSet('dryrun','pipeline')] [string]$Mode = 'dryrun',
  [string]$EnvPrefix = 'goodq',
  [switch]$OpenDashboard,
  [string]$UICommand,
  [switch]$Airplane
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Info([string]$m) { Write-Host "[launch] $m" -ForegroundColor Cyan }
function Ok([string]$m)   { Write-Host "[launch] $m" -ForegroundColor Green }
function Warn([string]$m) { Write-Host "[launch] $m" -ForegroundColor Yellow }
function Fail([string]$m) { Write-Error $m; exit 1 }

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot
$syncScript = Join-Path $repoRoot 'scripts\sync_env_local.ps1'
if (Test-Path $syncScript) {
  & $syncScript | Out-Null
}

Info "Health check"
& pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'mission_health_check.ps1') -EnvPrefix $EnvPrefix

Info "Enable/verify CUDA"
& pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'enable_cuda.ps1') -Verify

if ($Airplane) {
  $hf = [Environment]::GetEnvironmentVariable('HF_HOME','User')
  if (-not $hf) { $hf = [Environment]::GetEnvironmentVariable('HF_HOME','Process') }
  if ($hf -and (Test-Path $hf)) {
    $env:HF_DATASETS_OFFLINE = '1'
    $env:TRANSFORMERS_OFFLINE = '1'
    Info "Airplane mode: using offline HF caches at $hf"
  } else {
    Warn 'Airplane mode requested but HF_HOME not set or missing; proceeding online'
  }
}

if ($Mode -eq 'dryrun') {
  Info 'Running dry run export bundle'
  & pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'run_full_dry_run.ps1') -EnvPrefix $EnvPrefix
}
elseif ($Mode -eq 'pipeline') {
  Info 'Running ZenML pipeline (ingest_multimodal)'
  $zenEnv = "${EnvPrefix}_zenml"
  $normalizedRepoRoot = $repoRoot.Replace("\\", "/")
  $pyCode = @"
import sys
sys.path.insert(0, r"$normalizedRepoRoot")
from pipelines.ingest_multimodal_conda import ingest_multimodal
ingest_multimodal()
"@
  $tmpPy = [System.IO.Path]::GetTempFileName()
  try {
    Set-Content -LiteralPath $tmpPy -Value $pyCode -Encoding UTF8
    & conda run -n $zenEnv python $tmpPy
  }
  finally {
    Remove-Item -LiteralPath $tmpPy -Force -ErrorAction SilentlyContinue
  }
}

if ($OpenDashboard) {
  $zenEnv = "${EnvPrefix}_zenml"
  Info 'Opening ZenML local server and dashboard (Windows)'
  $cmd1 = "conda run -n $zenEnv zenml login --local --blocking"
  Start-Process pwsh -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-Command","cd `"$repoRoot`"; $cmd1" -WindowStyle Normal
  Start-Sleep -Seconds 3
  Start-Process pwsh -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-Command","cd `"$repoRoot`"; conda run -n $zenEnv zenml dashboard" -WindowStyle Normal
}

if ($UICommand) {
  Info "Launching UI command: $UICommand"
  Invoke-Expression $UICommand
}

Ok 'Launch sequence complete.'

