Param(
  [string]$EnvPrefix = 'goodq',
  [switch]$GenerateIn,
  [switch]$UpgradePipTools
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Info($m){ Write-Host "[lock] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[lock] $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[lock] $m" -ForegroundColor Yellow }
function Fail($m){ Write-Error $m; exit 1 }

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot

if (-not (Get-Command conda -ErrorAction SilentlyContinue)) { Fail 'conda not found' }

$zenEnv = "${EnvPrefix}_zenml"
if ($UpgradePipTools) {
  Info 'Installing/upgrading pip-tools in zenml env'
  $prevNoUser=$env:PYTHONNOUSERSITE; $prevNoCache=$env:PIP_NO_CACHE_DIR; $prevDisable=$env:PIP_DISABLE_PIP_VERSION_CHECK
  try {
    $env:PYTHONNOUSERSITE='1'; $env:PIP_NO_CACHE_DIR='1'; $env:PIP_DISABLE_PIP_VERSION_CHECK='1'
    & conda run -n $zenEnv pip install --upgrade pip --no-cache-dir --no-user --isolated
    & conda run -n $zenEnv pip install pip-tools --no-cache-dir --no-user --isolated --upgrade-strategy only-if-needed
  } finally {
    if ($null -ne $prevNoUser) { $env:PYTHONNOUSERSITE=$prevNoUser } else { Remove-Item Env:PYTHONNOUSERSITE -ErrorAction SilentlyContinue }
    if ($null -ne $prevNoCache) { $env:PIP_NO_CACHE_DIR=$prevNoCache } else { Remove-Item Env:PIP_NO_CACHE_DIR -ErrorAction SilentlyContinue }
    if ($null -ne $prevDisable) { $env:PIP_DISABLE_PIP_VERSION_CHECK=$prevDisable } else { Remove-Item Env:PIP_DISABLE_PIP_VERSION_CHECK -ErrorAction SilentlyContinue }
  }
}

$envDirs = Get-ChildItem -LiteralPath (Join-Path $repoRoot 'envs') -Directory
foreach ($dir in $envDirs) {
  $name = $dir.Name
  $in = Join-Path $dir.FullName 'requirements.in'
  $txt = Join-Path $dir.FullName 'requirements.txt'
  $lock = Join-Path $dir.FullName 'requirements.lock.txt'
  if ($GenerateIn -or -not (Test-Path $in)) {
    if (Test-Path $txt) {
      Info ("Generating {0}" -f $in)
      Copy-Item -LiteralPath $txt -Destination $in -Force
    } else {
      Warn ("Missing requirements.txt for {0}; skipping" -f $name)
      continue
    }
  }
  if (-not (Test-Path $in)) { Warn ("No requirements.in for {0}; skipping" -f $name); continue }
  Info ("pip-compile {0}" -f $name)
  try {
    & conda run -n $zenEnv pip-compile --generate-hashes --strip-extras --output-file $lock $in
    Ok ("Wrote {0}" -f $lock)
  } catch {
    Warn ("pip-compile failed for {0}" -f $name)
  }
}

Ok 'Env locking complete.'
