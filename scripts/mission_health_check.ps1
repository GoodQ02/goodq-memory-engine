Param(
  [string]$EnvPrefix = 'goodq',
  [switch]$FixMissingCaches,
  [string]$ExpectedModelsCache,
  [switch]$SmokeAll
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Ok($m){ Write-Host "[ok] $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[warn] $m" -ForegroundColor Yellow }
function Info($m){ Write-Host "[info] $m" -ForegroundColor Cyan }
function Fail($m){ Write-Error $m; exit 1 }

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot
$syncScript = Join-Path $repoRoot 'scripts\sync_env_local.ps1'
if (Test-Path $syncScript) {
  & $syncScript | Out-Null
}

Info 'Preflight checks'

# Tooling
if (Get-Command conda -ErrorAction SilentlyContinue) { Ok 'conda on PATH' } else { Fail 'conda not found' }
if (Get-Command python -ErrorAction SilentlyContinue) { Ok 'python on PATH' } else { Warn 'python not found (will use conda run)' }
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) { Ok 'ffmpeg on PATH' } else { Warn 'ffmpeg not found on PATH' }
if (Get-Command tesseract -ErrorAction SilentlyContinue) { Ok 'tesseract on PATH' } else { Warn 'tesseract not found on PATH' }
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { Ok 'nvidia-smi available' } else { Warn 'nvidia-smi not found (GPU features unavailable)' }

# Caches
$hf = [Environment]::GetEnvironmentVariable('HF_HOME','User')
if (-not $hf) { $hf = [Environment]::GetEnvironmentVariable('HF_HOME','Process') }
$th = [Environment]::GetEnvironmentVariable('TORCH_HOME','User')
if (-not $th) { $th = [Environment]::GetEnvironmentVariable('TORCH_HOME','Process') }
if ($hf) { Ok "HF_HOME=$hf" } else { Warn 'HF_HOME not set' }
if ($th) { Ok "TORCH_HOME=$th" } else { Warn 'TORCH_HOME not set' }

if ($FixMissingCaches -and $ExpectedModelsCache) {
  $hfDir = Join-Path $ExpectedModelsCache 'hf'
  $thDir = Join-Path $ExpectedModelsCache 'torch'
  New-Item -ItemType Directory -Force -Path $hfDir | Out-Null
  New-Item -ItemType Directory -Force -Path $thDir | Out-Null
  Ok "Ensured cache dirs exist under $ExpectedModelsCache"
}

# Env existence snapshot
Info 'Conda env snapshot:'
& conda env list

# Optional quick smokes (import-only)
function Smoke-Import($envName,[string[]]$modules){
  $joined = ($modules | ForEach-Object { '"' + $_ + '"' }) -join ', '
  $listLiteral = "[{0}]" -f $joined
  $code = @"
import importlib, json
MODULES = ${listLiteral}
result = {}
for name in MODULES:
    try:
        importlib.import_module(name)
        result[name] = True
    except Exception:
        result[name] = False
print(json.dumps(result))
"@
  $tmp = [System.IO.Path]::GetTempFileName()
  try {
    Set-Content -LiteralPath $tmp -Value $code -Encoding UTF8
    $out = & conda run -n $envName python $tmp
    Ok ("{0}: {1}" -f $envName, ($out.Trim()))
  } catch {
    Warn ("{0}: import smoke failed" -f $envName)
  } finally {
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
  }
}

Smoke-Import -envName "${EnvPrefix}_text_embed" -modules @('faiss','sqlite3','sentence_transformers','GoodQ_4_All')
Smoke-Import -envName "${EnvPrefix}_image_caption" -modules @('torch','transformers','GoodQ_4_All')
Smoke-Import -envName "${EnvPrefix}_audio_transcribe" -modules @('torch','faster_whisper','GoodQ_4_All')
Smoke-Import -envName "${EnvPrefix}_zenml" -modules @('zenml','openai','openai_agents','GoodQ_4_All')

if ($SmokeAll) {
  Info 'Running sanity suite (lightweight)'
  try {
    & pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'sanity_suite.ps1') -EnvPrefix $EnvPrefix
  } catch {
    Warn 'Sanity suite failed to run'
  }
}

Ok 'Preflight complete.'
