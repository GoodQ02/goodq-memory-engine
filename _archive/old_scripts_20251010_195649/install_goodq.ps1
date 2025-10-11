Param(
  [switch]$SetCacheEnv,
  [string]$ModelsCache = 'L:\\models',
  [string]$EnvPrefix = 'goodq',
  [switch]$SkipCUDA,
  [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Info($m){ Write-Host "[install] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[install] $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[install] $m" -ForegroundColor Yellow }
function Fail($m){ Write-Error $m; exit 1 }

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot

if ($SetCacheEnv) {
  Info "Setting model caches under $ModelsCache (HF_HOME/TORCH_HOME)"
  & pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'set_env_vars.ps1') -OnlyIfMissing -Persist -AppendToEnvLocal -ModelsCache $ModelsCache
}

Info 'Preparing per-step Conda environments'
& pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'prepare_step_envs.ps1') -EnvPrefix $EnvPrefix -LinkProject

Info 'Bootstrapping ZenML (local store)'
& pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'bootstrap_zenml.ps1') -EnvPrefix $EnvPrefix -InitOnly

if (-not $SkipCUDA) {
  Info 'Enabling CUDA across GPU envs'
  & pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'enable_cuda.ps1') -Verify
}

if ($DryRun) {
  Info 'Running dry run (optional)'
  & pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'mission_launch.ps1') -Mode dryrun -EnvPrefix $EnvPrefix
}

Ok 'Install complete.'
