Param(
  [switch]$WriteJson,
  [string]$JsonOut
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Info($m){ Write-Host "[env-audit] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[env-audit] $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[env-audit] $m" -ForegroundColor Yellow }
function Fail($m){ Write-Error $m; exit 1 }

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot

$logsDir = Join-Path $repoRoot 'logs'
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
if (-not $JsonOut) { $JsonOut = Join-Path $logsDir 'env_audit.json' }

function Read-YamlQuotedValue {
  Param([string]$File,[string]$Key)
  if (-not (Test-Path $File)) { return $null }
  $pattern = ('^\s*{0}\s*:\s*"(.*)"\s*$' -f [regex]::Escape($Key))
  foreach ($line in Get-Content -LiteralPath $File) {
    $m = [regex]::Match($line, $pattern)
    if ($m.Success) { return $m.Groups[1].Value }
  }
  return $null
}

$cfgOpen = Join-Path $repoRoot 'configs\config_open.yaml'
$cfgPaths = Join-Path $repoRoot 'configs\paths.yaml'
$envLocal = Join-Path $repoRoot '.env.local'

$importantEnv = @(
  'GOODQ_VERBOSE','GOODQ_STEP_TIMEOUT_MS',
  'GOODQ_API_HOST','GOODQ_API_PORT',
  'HF_HOME','TORCH_HOME','TRANSFORMERS_CACHE',
  'PYANNOTE_TOKEN','PYANNOTE_AUDIO_AUTH','HF_TOKEN',
  'OPENAI_API_KEY','ELEVENLABS_API_KEY','ELEVENLABS_VOICE_ID',
  'HA_TOKEN'
)
$secretEnv = @('PYANNOTE_TOKEN','PYANNOTE_AUDIO_AUTH','HF_TOKEN','OPENAI_API_KEY','ELEVENLABS_API_KEY','ELEVENLABS_VOICE_ID','HA_TOKEN')

# Gather env in Process/User/Machine scopes (value redacted if secret)
function Get-EnvScope {
  Param([string]$Name,[string]$Scope)
  try {
    return [Environment]::GetEnvironmentVariable($Name, $Scope)
  } catch { return $null }
}

$envReport = @{}
foreach ($k in $importantEnv) {
  $proc = Get-EnvScope $k 'Process'
  $user = Get-EnvScope $k 'User'
  $mach = Get-EnvScope $k 'Machine'
  $val = $proc; if (-not $val) { $val = $user }; if (-not $val) { $val = $mach }
  $shown = if ($secretEnv -contains $k) { if ($val) { 'SET' } else { '' } } else { [string]$val }
  $envReport[$k] = @{ process=$proc; user=$user; machine=$mach; effective=$val }
  $disp = if ($secretEnv -contains $k) { if ($val) { '(set)' } else { '(empty)' } } else { $shown }
  Write-Host (' - {0} = {1}' -f $k, $disp)
}

# PATH breakdown (effective)
$pathVal = [Environment]::GetEnvironmentVariable('PATH','Process'); if (-not $pathVal) { $pathVal = $Env:PATH }
$pathParts = ($pathVal -split ';' | Where-Object { $_ -and $_.Trim() -ne '' })

# Tool paths from config
$tools = @{
  ffmpeg = Read-YamlQuotedValue $cfgOpen 'ffmpeg_exe'
  tesseract = Read-YamlQuotedValue $cfgOpen 'tesseract_exe'
  poppler_bin = Read-YamlQuotedValue $cfgOpen 'poppler_bin'
  pdftotext = Read-YamlQuotedValue $cfgOpen 'pdftotext_exe'
  piper = Read-YamlQuotedValue $cfgOpen 'piper_exe'
  piper_voice = Read-YamlQuotedValue $cfgOpen 'piper_voice'
}

function Test-PathInfo {
  Param([string]$p)
  if (-not $p) { return @{ exists=$false; writable=$false } }
  $exists = Test-Path $p
  $writable = $false
  try {
    if ($exists) {
      if ((Get-Item -LiteralPath $p).PSIsContainer) {
        $tmp = Join-Path $p (".__writetest_{0}" -f ([Guid]::NewGuid()))
        New-Item -ItemType File -Path $tmp -Force | Out-Null
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        $writable = $true
      } else {
        $dir = Split-Path -Parent $p
        if (Test-Path $dir) {
          $tmp = Join-Path $dir (".__writetest_{0}" -f ([Guid]::NewGuid()))
          New-Item -ItemType File -Path $tmp -Force | Out-Null
          Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
          $writable = $true
        }
      }
    }
  } catch { $writable = $false }
  return @{ exists=$exists; writable=$writable }
}

$pathsCfg = @{
  log_dir = Read-YamlQuotedValue $cfgPaths 'log_dir'
  output_directory = Read-YamlQuotedValue $cfgPaths 'output_directory'
  db_dir = Read-YamlQuotedValue $cfgPaths 'db_dir'
  system_csv = Read-YamlQuotedValue $cfgPaths 'system_csv'
  input_inbox = Read-YamlQuotedValue $cfgPaths 'input_inbox'
  db_path = Read-YamlQuotedValue $cfgPaths 'db_path'
  faiss_index_path = Read-YamlQuotedValue $cfgPaths 'faiss_index_path'
  faiss_audio_path = Read-YamlQuotedValue $cfgPaths 'faiss_audio_path'
  faiss_dino_path = Read-YamlQuotedValue $cfgPaths 'faiss_dino_path'
  faiss_clip_path = Read-YamlQuotedValue $cfgPaths 'faiss_clip_path'
  clap_id_map_db = Read-YamlQuotedValue $cfgPaths 'clap_id_map_db'
  known_faces_db_path = Read-YamlQuotedValue $cfgPaths 'known_faces_db_path'
  clip_id_map_db = Read-YamlQuotedValue $cfgPaths 'clip_id_map_db'
  dino_id_map_db = Read-YamlQuotedValue $cfgPaths 'dino_id_map_db'
}

Info 'Verifying configured paths:'
$pathChecks = @{}
foreach ($k in $pathsCfg.Keys) {
  $v = $pathsCfg[$k]
  $chk = Test-PathInfo $v
  $pathChecks[$k] = @{ value=$v; exists=$chk.exists; writable=$chk.writable }
  $status = if ($chk.exists) { if ($chk.writable) { 'OK' } else { 'RO' } } else { 'MISSING' }
  Write-Host (" - {0} = {1} [{2}]" -f $k, ($v ?? ''), $status)
}

Info 'Verifying tools from config:'
$toolChecks = @{}
foreach ($k in $tools.Keys) {
  $v = $tools[$k]
  $chk = Test-PathInfo $v
  $toolChecks[$k] = @{ value=$v; exists=$chk.exists }
  $status = if ($chk.exists) { 'FOUND' } else { 'NOT_FOUND' }
  Write-Host (" - {0} = {1} [{2}]" -f $k, ($v ?? ''), $status)
}

# PATH duplicates and presence of tool directories
$dupes = $pathParts | Group-Object | Where-Object Count -gt 1 | Select-Object -ExpandProperty Name
$toolDirsPresent = @{}
foreach ($k in @('poppler_bin')) {
  $v = $tools[$k]
  if ($v) {
    $toolDirsPresent[$k] = [bool]($pathParts -contains $v)
  }
}

$report = @{
  env = $envReport
  path = @{ parts=$pathParts; duplicates=$dupes; tool_dirs_present=$toolDirsPresent }
  tools = $toolChecks
  config_paths = $pathChecks
  config_tools = $tools
}

if ($WriteJson) {
  ($report | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $JsonOut -Encoding UTF8
  Ok ("Wrote JSON report to {0}" -f $JsonOut)
}

Ok 'Environment audit complete.'

