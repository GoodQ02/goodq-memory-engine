Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Info($m){ Write-Host "[fix] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[fix] $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[fix] $m" -ForegroundColor Yellow }

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot

# Read tool paths from config
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
$tesseractExe = Read-YamlQuotedValue $cfgOpen 'tesseract_exe'
$popplerBin = Read-YamlQuotedValue $cfgOpen 'poppler_bin'
$ffmpegExe = Read-YamlQuotedValue $cfgOpen 'ffmpeg_exe'

# Add to PATH (User) if missing: tesseract dir and poppler bin
$pathsToAdd = @()
if ($tesseractExe -and (Test-Path $tesseractExe)) {
  $tdir = Split-Path -Parent $tesseractExe
  if ($tdir) { $pathsToAdd += $tdir }
}
if ($popplerBin) { $pathsToAdd += $popplerBin }

Info 'Reconciling PATH and removing deprecated cache env var'
& pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'set_env_vars.ps1') -Persist -AppendToEnvLocal -Unset @('TRANSFORMERS_CACHE') -AddPath $pathsToAdd

# Print result
Info 'Checking tesseract presence on PATH'
if (Get-Command tesseract -ErrorAction SilentlyContinue) { Ok 'tesseract found on PATH' } else { Warn 'tesseract still not found on PATH (steps will still use configured path)' }

Ok 'Preflight fixes applied.'

