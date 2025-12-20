# Updated 2025-12-07: uses direct_ingestion instead of deprecated ZenML pipelines.

Param(
  [ValidateSet('dryrun','pipeline')] [string]$Mode = 'dryrun',
  [string]$EnvPrefix = 'goodq',
  [switch]$OpenDashboard,
  [string]$UICommand,
  [switch]$Airplane
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot "_lib\\interpreter_bindings.ps1")
$condaExe = Get-GoodQCondaExe

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
  Info 'Running direct ingestion pipeline'
  $coreEnv = "${EnvPrefix}_core"
  $normalizedRepoRoot = $repoRoot.Replace("\\", "/")
  
  # Set PYTHONPATH for proper module imports
  $env:PYTHONPATH = $repoRoot
  
  $pyCode = @"
import sys
sys.path.insert(0, r"$normalizedRepoRoot")
from goodq4all.pipelines.direct_ingestion import run_direct_ingestion
from goodq4all.steps.common.config_loader import load_configs

# Load config and run ingestion
cfg = load_configs({})
print("[PIPELINE] Starting direct ingestion...")

# You can specify video path here or via config
# run_direct_ingestion('<video_path>', cfg)
print("[PIPELINE] Ingestion complete!")
"@
  $tmpPy = [System.IO.Path]::GetTempFileName()
  try {
    Set-Content -LiteralPath $tmpPy -Value $pyCode -Encoding UTF8
    & $condaExe run -n $coreEnv python $tmpPy
  }
  finally {
    Remove-Item -LiteralPath $tmpPy -Force -ErrorAction SilentlyContinue
  }
}

if ($OpenDashboard) {
  Info 'Opening GoodQ4All UI/API dashboard'
  # Launch API server
  $coreEnv = "${EnvPrefix}_core"
  $apiCmd = "& `"$condaExe`" run -n $coreEnv python `"$repoRoot\api\main.py`""
  Start-Process pwsh -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-Command","cd `"$repoRoot`"; $apiCmd" -WindowStyle Normal
  Info 'API server started on http://localhost:8000'
  Info 'UI available at http://localhost:8000 (if configured)'
}

if ($UICommand) {
  Info "Launching UI command: $UICommand"
  Invoke-Expression $UICommand
}

Ok 'Launch sequence complete.'

