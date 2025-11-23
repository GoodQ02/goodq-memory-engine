Param(
  [string]$EnvPrefix = 'goodq',
  [string]$PythonVersion = '3.10',
  [switch]$ForceReinstall,
  [switch]$LinkProject
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Note($msg) { Write-Host "[envs] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[envs] $msg" -ForegroundColor Yellow }
function Write-Ok($msg)   { Write-Host "[envs] $msg" -ForegroundColor Green }
function Fail($msg) { Write-Error $msg; exit 1 }

function Test-Command($name) {
  $null -ne (Get-Command $name -ErrorAction SilentlyContinue)
}

if (-not (Test-Command 'conda')) { Fail 'conda not found on PATH. Please install Miniconda/Anaconda.' }

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot

# Ensure critical environment variables are set and persisted consistently
try {
  $vars = @{
    'HF_HOME'    = 'L:\\models'
    'TORCH_HOME' = 'L:\\models'
    'HF_HUB_ENABLE_HF_TRANSFER' = '1'
    'GOODQ_API_HOST' = '0.0.0.0'
    'GOODQ_API_PORT' = '30000'
  }
  Write-Note 'Setting core environment variables (HF_HOME, TORCH_HOME, API host/port)'
  & (Join-Path $PSScriptRoot 'set_env_vars.ps1') -Vars $vars -Persist -AppendToEnvLocal
} catch {
  Write-Warn "Failed to set core environment variables: $_"
}

function Link-ProjectPath {
  Param([string]$EnvName)
  $code = @"
import site, pathlib
root = pathlib.Path(r'$repoRoot').resolve()
paths = []
try:
    paths.extend(site.getsitepackages())
except Exception:
    pass
paths.extend(site.getusersitepackages() if hasattr(site, 'getusersitepackages') else [])
written = False
for target in paths:
    try:
        p = pathlib.Path(target)
        p.mkdir(parents=True, exist_ok=True)
        with open(p / 'goodq4all_local.pth', 'w', encoding='utf-8') as fh:
            # Add the parent of the repo root to sys.path so that the
            # package 'goodq4all' (which lives at $repoRoot) can be imported
            # as a top-level module. E.g., if repoRoot is L:\\goodq4all,
            # we must add L:\\ to sys.path.
            fh.write(str(root.parent))
        written = True
        break
    except Exception:
        continue
if not written:
    raise RuntimeError('Unable to create .pth link for goodq4all')
"@
  try {
    $tmp = [System.IO.Path]::GetTempFileName()
    Set-Content -LiteralPath $tmp -Value $code -Encoding UTF8
    & conda run -n $EnvName python $tmp
    Remove-Item -LiteralPath $tmp -Force
    Write-Note "Linked repo into $EnvName via .pth"
  } catch {
    Write-Warn ("Failed to link repo into {0}: {1}" -f $EnvName, $_)
  }
}

function Ensure-CondaEnv {
  Param([string]$Name, [string]$ReqFile)
  $exists = (& conda env list) -match "^$Name\b"
  if ($exists -and -not $ForceReinstall) {
    Write-Note "Env $Name exists"
  } else {
    if ($exists -and $ForceReinstall) {
      Write-Warn "Recreating env $Name (ForceReinstall)"
      & conda env remove -n $Name -y | Out-Null
    }
    Write-Note "Creating env $Name (python=$PythonVersion)"
    & conda create -y -n $Name python=$PythonVersion | Out-Null
  }
  if (Test-Path $ReqFile) {
    Write-Note "Installing requirements for $Name from $ReqFile"
    # Enforce isolation: never consult or write to user site/packages during install
    $prevNoUser = $env:PYTHONNOUSERSITE
    $prevNoCache = $env:PIP_NO_CACHE_DIR
    $prevDisableCheck = $env:PIP_DISABLE_PIP_VERSION_CHECK
    try {
      $env:PYTHONNOUSERSITE = '1'           # disable user site entirely for Python/pip
      $env:PIP_NO_CACHE_DIR = '1'            # avoid cache bleed across envs
      $env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
      # Upgrade pip inside the env in isolated mode with no user writes
      & conda run -n $Name pip install --upgrade pip --no-cache-dir --no-user --isolated
      # Install env requirements in isolated mode with no user writes
      & conda run -n $Name pip install -r $ReqFile --no-cache-dir --no-user --isolated --upgrade-strategy only-if-needed
    } finally {
      if ($null -ne $prevNoUser) { $env:PYTHONNOUSERSITE = $prevNoUser } else { Remove-Item Env:PYTHONNOUSERSITE -ErrorAction SilentlyContinue }
      if ($null -ne $prevNoCache) { $env:PIP_NO_CACHE_DIR = $prevNoCache } else { Remove-Item Env:PIP_NO_CACHE_DIR -ErrorAction SilentlyContinue }
      if ($null -ne $prevDisableCheck) { $env:PIP_DISABLE_PIP_VERSION_CHECK = $prevDisableCheck } else { Remove-Item Env:PIP_DISABLE_PIP_VERSION_CHECK -ErrorAction SilentlyContinue }
    }
  }
  if ($LinkProject) {
    Link-ProjectPath -EnvName $Name
  }
}

# Step envs from envs/*/requirements.txt
Get-ChildItem -LiteralPath (Join-Path $repoRoot 'envs') -Directory | ForEach-Object {
  $short = $_.Name
  $envName = "${EnvPrefix}_$short"
  $req = Join-Path $_.FullName 'requirements.txt'
  Ensure-CondaEnv -Name $envName -ReqFile $req
}

# ZenML env for orchestration and dashboard
$zenEnv = "${EnvPrefix}_zenml"
Ensure-CondaEnv -Name $zenEnv -ReqFile $null
Write-Note 'Installing zenml into the ZenML env'
try {
  $prevNoUser=$env:PYTHONNOUSERSITE; $prevNoCache=$env:PIP_NO_CACHE_DIR; $prevDisable=$env:PIP_DISABLE_PIP_VERSION_CHECK
  $env:PYTHONNOUSERSITE='1'; $env:PIP_NO_CACHE_DIR='1'; $env:PIP_DISABLE_PIP_VERSION_CHECK='1'
  & conda run -n $zenEnv pip install --upgrade pip --no-cache-dir --no-user --isolated
  & conda run -n $zenEnv pip install "zenml>=0.65" "openai>=1.40" "openai-agents>=0.1" "nest_asyncio>=1.6" "typer>=0.9.0" --no-cache-dir --no-user --isolated --upgrade-strategy only-if-needed
} finally {
  if ($null -ne $prevNoUser) { $env:PYTHONNOUSERSITE=$prevNoUser } else { Remove-Item Env:PYTHONNOUSERSITE -ErrorAction SilentlyContinue }
  if ($null -ne $prevNoCache) { $env:PIP_NO_CACHE_DIR=$prevNoCache } else { Remove-Item Env:PIP_NO_CACHE_DIR -ErrorAction SilentlyContinue }
  if ($null -ne $prevDisable) { $env:PIP_DISABLE_PIP_VERSION_CHECK=$prevDisable } else { Remove-Item Env:PIP_DISABLE_PIP_VERSION_CHECK -ErrorAction SilentlyContinue }
}
if ($LinkProject) {
  Link-ProjectPath -EnvName $zenEnv
}

# Ensure API deps installed in text_embed env if present
try {
  $apiReq = Join-Path $repoRoot 'api\requirements.txt'
  if (Test-Path $apiReq) {
    $apiEnv = "${EnvPrefix}_text_embed"
    Write-Note "Installing API requirements into $apiEnv"
    $prevNoUser=$env:PYTHONNOUSERSITE; $prevNoCache=$env:PIP_NO_CACHE_DIR; $prevDisable=$env:PIP_DISABLE_PIP_VERSION_CHECK
    try {
      $env:PYTHONNOUSERSITE='1'; $env:PIP_NO_CACHE_DIR='1'; $env:PIP_DISABLE_PIP_VERSION_CHECK='1'
      & conda run -n $apiEnv pip install --upgrade pip --no-cache-dir --no-user --isolated
      & conda run -n $apiEnv pip install -r $apiReq --no-cache-dir --no-user --isolated --upgrade-strategy only-if-needed
    } finally {
      if ($null -ne $prevNoUser) { $env:PYTHONNOUSERSITE=$prevNoUser } else { Remove-Item Env:PYTHONNOUSERSITE -ErrorAction SilentlyContinue }
      if ($null -ne $prevNoCache) { $env:PIP_NO_CACHE_DIR=$prevNoCache } else { Remove-Item Env:PIP_NO_CACHE_DIR -ErrorAction SilentlyContinue }
      if ($null -ne $prevDisable) { $env:PIP_DISABLE_PIP_VERSION_CHECK=$prevDisable } else { Remove-Item Env:PIP_DISABLE_PIP_VERSION_CHECK -ErrorAction SilentlyContinue }
    }
    if ($LinkProject) { Link-ProjectPath -EnvName $apiEnv }
  }
} catch {
  Write-Warn "Failed to install API requirements into text_embed: $_"
}

Write-Ok 'All environments prepared.'

