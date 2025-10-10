Param(
  [string[]]$GpuEnvs = @('goodq_image_caption','goodq_object_detect','goodq_audio_transcribe','goodq_audio_emotion','goodq_audio_diarize'),  # Removed goodq_face_embed temporarily
  [switch]$Verify,
  [string]$CudaChannel = 'cu121',
  [string]$Torch = '2.3.1',
  [string]$TorchVision = '0.18.1',
  [string]$TorchAudio = '2.3.1'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Note($msg) { Write-Host "[cuda] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[cuda] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[cuda] $msg" -ForegroundColor Yellow }
function Fail($msg) { Write-Error $msg; exit 1 }

if (-not (Get-Command conda -ErrorAction SilentlyContinue)) { Fail 'conda not found' }

Write-Note ("Installing PyTorch CUDA wheels where missing ({0})" -f $CudaChannel)
foreach ($envName in $GpuEnvs) {
  try {
    $cudaOk = (& conda run -n $envName python -c "import torch,sys;print(torch.cuda.is_available())" 2>$null).Trim()
  } catch { $cudaOk = '' }
  if ($cudaOk -eq 'True') {
    Write-Ok "$($envName): CUDA already available"
    continue
  }
  Write-Note "$($envName): installing torch/vision/audio CUDA wheels"
  # Enforce isolation during pip operations
  $prevNoUser = $env:PYTHONNOUSERSITE; $prevNoCache = $env:PIP_NO_CACHE_DIR; $prevDisable = $env:PIP_DISABLE_PIP_VERSION_CHECK
  try {
    $env:PYTHONNOUSERSITE='1'; $env:PIP_NO_CACHE_DIR='1'; $env:PIP_DISABLE_PIP_VERSION_CHECK='1'
    # Use pip directly (not python -m pip) to avoid runpy dependency
    & conda run -n $envName pip install --upgrade pip --no-cache-dir --no-user --isolated
  } finally {
    if ($null -ne $prevNoUser) { $env:PYTHONNOUSERSITE=$prevNoUser } else { Remove-Item Env:PYTHONNOUSERSITE -ErrorAction SilentlyContinue }
    if ($null -ne $prevNoCache) { $env:PIP_NO_CACHE_DIR=$prevNoCache } else { Remove-Item Env:PIP_NO_CACHE_DIR -ErrorAction SilentlyContinue }
    if ($null -ne $prevDisable) { $env:PIP_DISABLE_PIP_VERSION_CHECK=$prevDisable } else { Remove-Item Env:PIP_DISABLE_PIP_VERSION_CHECK -ErrorAction SilentlyContinue }
  }
  $indexUrl = "https://download.pytorch.org/whl/$CudaChannel"
  if ($envName -eq 'goodq_audio_diarize') {
    # WhisperX stack prefers its own compatible torch; avoid pinning exact versions here.
    $packages = @('--index-url', $indexUrl, 'torch', 'torchvision', 'torchaudio')
  } else {
    $packages = @(
      '--index-url', $indexUrl,
      ('torch=={0}' -f $Torch),
      ('torchvision=={0}' -f $TorchVision),
      ('torchaudio=={0}' -f $TorchAudio)
    )
  }
  $prevNoUser = $env:PYTHONNOUSERSITE; $prevNoCache = $env:PIP_NO_CACHE_DIR; $prevDisable = $env:PIP_DISABLE_PIP_VERSION_CHECK
  try {
    $env:PYTHONNOUSERSITE='1'; $env:PIP_NO_CACHE_DIR='1'; $env:PIP_DISABLE_PIP_VERSION_CHECK='1'
    # Use pip directly (not python -m pip) to avoid runpy dependency
    & conda run -n $envName pip install --no-cache-dir --no-user --isolated @packages
  } finally {
    if ($null -ne $prevNoUser) { $env:PYTHONNOUSERSITE=$prevNoUser } else { Remove-Item Env:PYTHONNOUSERSITE -ErrorAction SilentlyContinue }
    if ($null -ne $prevNoCache) { $env:PIP_NO_CACHE_DIR=$prevNoCache } else { Remove-Item Env:PIP_NO_CACHE_DIR -ErrorAction SilentlyContinue }
    if ($null -ne $prevDisable) { $env:PIP_DISABLE_PIP_VERSION_CHECK=$prevDisable } else { Remove-Item Env:PIP_DISABLE_PIP_VERSION_CHECK -ErrorAction SilentlyContinue }
  }
}

if ($Verify) {
  Write-Note 'Verifying CUDA availability per env'
  foreach ($envName in $GpuEnvs) {
    try {
      $tmp = [System.IO.Path]::GetTempFileName()
      @"
import torch, json
print(json.dumps({"cuda_available": bool(getattr(torch, 'cuda', None) and torch.cuda.is_available())}))
"@ | Set-Content -LiteralPath $tmp -Encoding UTF8
      $out = & conda run -n $envName python $tmp
      Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
      Write-Host ("  {0}: {1}" -f $envName, ($out | Out-String).Trim())
    } catch {
      Write-Warn ("  {0}: verify failed" -f $envName)
    }
  }
}

Write-Ok 'CUDA enablement pass complete.'
