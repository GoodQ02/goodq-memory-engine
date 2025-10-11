Param(
  [string]$EnvPrefix = 'goodq',
  [switch]$InitOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Note($msg) { Write-Host "[zenml] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[zenml] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[zenml] $msg" -ForegroundColor Yellow }
function Fail($msg) { Write-Error $msg; exit 1 }

if (-not (Get-Command conda -ErrorAction SilentlyContinue)) { Fail 'conda not found' }

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot

$zenEnv = "${EnvPrefix}_zenml"

Write-Note "ZenML version in env $zenEnv:" 
& conda run -n $zenEnv python -c "import zenml,sys;print(zenml.__version__)"

Write-Note 'Initializing ZenML repo (local store)'
& conda run -n $zenEnv zenml init

if (-not $InitOnly) {
  Write-Note 'You can start the local server with:'
  Write-Host "  conda run -n $zenEnv zenml login --local --blocking" -ForegroundColor Gray
  Write-Note 'And open the dashboard in another shell:'
  Write-Host "  conda run -n $zenEnv zenml dashboard" -ForegroundColor Gray
}

Write-Ok 'ZenML bootstrap complete.'

