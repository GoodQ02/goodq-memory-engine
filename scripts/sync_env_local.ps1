Param(
  [string]$EnvFile = '.env.local',
  [string[]]$Names = @(
    'GOODQ_VERBOSE','GOODQ_STEP_TIMEOUT_MS','GOODQ_API_HOST','GOODQ_API_PORT',
    'GOODQ_SUMMARY_TTL_HOURS','GOODQ_MODELS_DIR','GOODQ_CC_QUERY','GOODQ_CC_THUMBS',
    'HF_HOME','TORCH_HOME','TRANSFORMERS_CACHE','HF_TOKEN','HF_DATASETS_OFFLINE',
    'TRANSFORMERS_OFFLINE','PYANNOTE_TOKEN','PYANNOTE_AUDIO_AUTH','PYANNOTE_MODEL',
    'OPENAI_API_KEY','ELEVENLABS_API_KEY','ELEVENLABS_VOICE_ID','elevenlabs_voice_id',
    'HA_TOKEN','SPEECHBRAIN_DOWNLOAD_STRATEGY','HF_HUB_ENABLE_HF_TRANSFER'
  )
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Note($msg) { Write-Host "[env-sync] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[env-sync] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[env-sync] $msg" -ForegroundColor Yellow }

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
$envPath = Join-Path $repoRoot $EnvFile
$envDir = Split-Path -Parent $envPath
if ($envDir -and -not (Test-Path $envDir)) {
  New-Item -ItemType Directory -Force -Path $envDir | Out-Null
}

$existing = @{}
if (Test-Path $envPath) {
  foreach ($line in Get-Content -LiteralPath $envPath) {
    if ($line -match '^\s*#') { continue }
    if ($line -match '^\s*$') { continue }
    $parts = $line.Split('=',2)
    if ($parts.Count -ge 2) {
      $key = $parts[0].Trim()
      $val = $parts[1]
      if ($key) { $existing[$key] = $val }
    }
  }
}

$merged = @{}
foreach ($k in $existing.Keys) { $merged[$k] = $existing[$k] }
$changed = $false

foreach ($name in $Names) {
  if (-not $name) { continue }
  $value = $null
  foreach ($scope in @('User','Machine','Process')) {
    $candidate = [Environment]::GetEnvironmentVariable($name, $scope)
    if (-not [string]::IsNullOrEmpty($candidate)) {
      $value = $candidate
      break
    }
  }
  if (-not [string]::IsNullOrEmpty($value)) {
    if (-not $merged.ContainsKey($name) -or $merged[$name] -ne $value) {
      $merged[$name] = $value
      $changed = $true
    }
    if ([Environment]::GetEnvironmentVariable($name, 'Process') -ne $value) {
      [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }
  }
}

if (-not $changed) {
  Write-Note 'No changes detected in tracked variables.'
  return
}

$timestamp = Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK'
$lines = @("# Auto-synced from system environment at $timestamp")
foreach ($entry in ($merged.GetEnumerator() | Sort-Object Key)) {
  $key = $entry.Key
  $val = $entry.Value
  if ($null -eq $val) { continue }
  $safe = $val -replace '"', '""'
  $lines += "$key=$safe"
}
$lines | Set-Content -LiteralPath $envPath -Encoding ASCII
Write-Ok ("Updated {0}" -f $EnvFile)


