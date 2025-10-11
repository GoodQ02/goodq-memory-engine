Param(
  [string]$EnvPrefix = 'goodq',
  [switch]$Force,
  [switch]$ClearTemp,
  [switch]$Verbose
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Info($msg){ Write-Host "[reset] $msg" -ForegroundColor Cyan }
function Warn($msg){ Write-Host "[reset] $msg" -ForegroundColor Yellow }
function Ok($msg){ Write-Host "[reset] $msg" -ForegroundColor Green }
function Fail($msg){ Write-Error $msg; exit 1 }

if (-not (Get-Command conda -ErrorAction SilentlyContinue)) {
  Fail 'conda not found on PATH. Open an Anaconda/Miniconda PowerShell prompt.'
}

if (-not $Force) {
  $confirm = Read-Host "This will delete all Conda envs starting with '$EnvPrefix'. Continue? (y/N)"
  if ($confirm.ToLowerInvariant() -ne 'y') { Write-Host 'Aborted.'; exit 0 }
}

Info "Collecting Conda environments"
$envJson = & conda env list --json
if (-not $envJson) { Fail 'Unable to list conda environments (no output).' }
$envData = $envJson | ConvertFrom-Json
$targets = @()
$envList = @()
if ($null -ne $envData -and $null -ne $envData.envs) { $envList = $envData.envs }
foreach ($envPath in $envList) {
  $name = Split-Path $envPath -Leaf
  if ($name -like "$EnvPrefix*") {
    $targets += [pscustomobject]@{ Name = $name; Path = $envPath }
  }
}

if (-not $targets -or $targets.Count -eq 0) {
  Info "No environments found with prefix '$EnvPrefix'."
} else {
  foreach ($env in $targets) {
    Info "Removing $($env.Name)"
    try {
      & conda env remove -n $env.Name -y | Out-Null
      Ok "conda env remove succeeded for $($env.Name)"
    } catch {
      Warn "conda env remove failed for $($env.Name): $_"
    }

    if (Test-Path $env.Path) {
      try {
        Remove-Item -LiteralPath $env.Path -Recurse -Force -ErrorAction Stop
        Ok "Deleted residual directory $($env.Path)"
      } catch {
        Warn "Could not remove $($env.Path). Close processes or reboot and retry."
      }
    }
  }
}

if ($ClearTemp) {
  $pattern = Join-Path $env:TEMP '__conda_tmp_*'
  Info "Clearing temp activation scripts: $pattern"
  Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue | ForEach-Object {
    try {
      Remove-Item -LiteralPath $_.FullName -Force -ErrorAction Stop
      if ($Verbose) { Ok ("Removed temp file {0}" -f $_.FullName) }
    } catch {
      Warn ("Unable to remove temp file {0}" -f $_.FullName)
    }
  }
}

Ok 'Environment reset complete.'
