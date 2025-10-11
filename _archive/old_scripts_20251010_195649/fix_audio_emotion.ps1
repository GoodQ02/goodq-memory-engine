Param(
  [string]$EnvName = 'goodq_audio_emotion'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Info($msg) { Write-Host "[fix] $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "[fix] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[fix] $msg" -ForegroundColor Yellow }
function Fail($msg) { Write-Error $msg; exit 1 }

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot

$reqFile = Join-Path $repoRoot "envs\audio_emotion\requirements.txt"
if (-not (Test-Path $reqFile)) {
  Fail "Requirements file not found: $reqFile"
}

Write-Info "Installing audio_emotion requirements with strict isolation"
Write-Info "Environment: $EnvName"

# Store previous values
$prevNoUser = $env:PYTHONNOUSERSITE
$prevNoCache = $env:PIP_NO_CACHE_DIR
$prevDisableCheck = $env:PIP_DISABLE_PIP_VERSION_CHECK

try {
  # Enforce strict isolation
  $env:PYTHONNOUSERSITE = '1'
  $env:PIP_NO_CACHE_DIR = '1'
  $env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
  
  Write-Info "Upgrading pip in isolated mode..."
  & conda run -n $EnvName pip install --upgrade pip --no-cache-dir --no-user --isolated
  if ($LASTEXITCODE -ne 0) {
    Fail "pip upgrade failed"
  }
  
  Write-Info "Installing requirements..."
  & conda run -n $EnvName pip install -r $reqFile --no-cache-dir --no-user --isolated --upgrade-strategy only-if-needed
  if ($LASTEXITCODE -ne 0) {
    Fail "Requirements install failed"
  }
  
  Write-Ok "Installation complete!"
  
} finally {
  # Restore previous values
  if ($null -ne $prevNoUser) { 
    $env:PYTHONNOUSERSITE = $prevNoUser 
  } else { 
    Remove-Item Env:PYTHONNOUSERSITE -ErrorAction SilentlyContinue 
  }
  if ($null -ne $prevNoCache) { 
    $env:PIP_NO_CACHE_DIR = $prevNoCache 
  } else { 
    Remove-Item Env:PIP_NO_CACHE_DIR -ErrorAction SilentlyContinue 
  }
  if ($null -ne $prevDisableCheck) { 
    $env:PIP_DISABLE_PIP_VERSION_CHECK = $prevDisableCheck 
  } else { 
    Remove-Item Env:PIP_DISABLE_PIP_VERSION_CHECK -ErrorAction SilentlyContinue 
  }
}

Write-Info "Verifying installation..."
& conda run -n $EnvName python -c "import torch; print(f'PyTorch {torch.__version__}, CUDA: {torch.cuda.is_available()}'); import transformers; print(f'Transformers {transformers.__version__}'); import hf_transfer; print('hf_transfer: OK')"

if ($LASTEXITCODE -eq 0) {
  Write-Ok "Verification passed!"
} else {
  Write-Warn "Verification had issues, but packages may still work"
}
