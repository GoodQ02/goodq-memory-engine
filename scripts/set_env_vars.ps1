Param(
  [switch]$OnlyIfMissing,
  [switch]$Persist,
  [switch]$AppendToEnvLocal,
  [string]$ModelsCache,
  [hashtable]$Vars,
  [string]$PyannoteToken,
  [string[]]$Unset,
  [string[]]$AddPath,
  [switch]$GatedDatasets
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Note($msg) { Write-Host "[env] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[env] $msg" -ForegroundColor Yellow }
function Write-Ok($msg)   { Write-Host "[env] $msg" -ForegroundColor Green }

$DefaultHfTransferToken = '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'

function Set-EnvVar {
  Param(
    [Parameter(Mandatory=$true)][string]$Name,
    [Parameter(Mandatory=$true)][string]$Value
  )
  $exists = $false
  if ($OnlyIfMissing) {
    $exists = [bool]([Environment]::GetEnvironmentVariable($Name,'Process') `
      -or [Environment]::GetEnvironmentVariable($Name,'User') `
      -or [Environment]::GetEnvironmentVariable($Name,'Machine'))
  }
  if ($exists) {
    Write-Note "Skip set $Name (already set)"
    return
  }
  # Set in current process scope
  [Environment]::SetEnvironmentVariable($Name, $Value, 'Process') | Out-Null
  if ($Persist) {
    Write-Note "Persisting $Name to user env"
    setx $Name $Value | Out-Null
  }
  if ($AppendToEnvLocal) {
    $repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
    $envFile = Join-Path $repoRoot '.env.local'
    $line = "$Name=$Value"
    try {
      $existing = @()
      if (Test-Path $envFile) {
        $existing = Get-Content -LiteralPath $envFile
      }
      $header = @($existing | Where-Object { $_.StartsWith('#') })
      $entries = [ordered]@{}
      foreach ($entry in $existing | Where-Object { (-not $_.StartsWith('#')) -and ($_ -match '=') }) {
        $split = $entry.Split('=',2)
        $entries[$split[0]] = $split[1]
      }
      $entries[$Name] = $Value
      $outLines = @()
      if ($header.Count) { $outLines += $header }
      foreach ($kv in $entries.GetEnumerator()) {
        $outLines += ($kv.Key + '=' + $kv.Value)
      }
      Set-Content -LiteralPath $envFile -Value $outLines -Encoding UTF8
      Write-Note ".env.local updated with $Name"
    } catch {
      Write-Warn ("Failed to update .env.local for {0}: {1}" -f $Name, $_)
    }
  }
  Write-Ok "Set $Name"
}

if ($ModelsCache) {
  $hf = Join-Path $ModelsCache 'hf'
  $th = Join-Path $ModelsCache 'torch'
  New-Item -ItemType Directory -Force -Path $hf | Out-Null
  New-Item -ItemType Directory -Force -Path $th | Out-Null
  Set-EnvVar -Name 'HF_HOME'   -Value $hf
  Set-EnvVar -Name 'TORCH_HOME' -Value $th
}

if ($Vars) {
  foreach ($k in $Vars.Keys) {
    $v = [string]$Vars[$k]
    if (-not $v) { continue }
    Set-EnvVar -Name ([string]$k) -Value $v
  }
}

if ($GatedDatasets) {
  $currentToken = [Environment]::GetEnvironmentVariable('HF_TOKEN','Process')
  if (-not $currentToken) { $currentToken = [Environment]::GetEnvironmentVariable('HF_TOKEN','User') }
  if (-not $currentToken) { $currentToken = [Environment]::GetEnvironmentVariable('HF_TOKEN','Machine') }
  if (-not $currentToken) { $currentToken = $DefaultHfTransferToken }
  Set-EnvVar -Name 'HF_TOKEN' -Value $currentToken
  Set-EnvVar -Name 'HF_HUB_ENABLE_HF_TRANSFER' -Value '1'
  Set-EnvVar -Name 'HF_HUB_TOKEN' -Value $currentToken
  try {
    setx HF_TOKEN $currentToken | Out-Null
    Write-Note 'HF_TOKEN persisted to user environment'
    try { setx HF_HUB_ENABLE_HF_TRANSFER 1 | Out-Null } catch { Write-Warn "Failed to persist HF_HUB_ENABLE_HF_TRANSFER for user: $_" }
  } catch { Write-Warn "Failed to persist HF_TOKEN for user: $_" }
  try {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = 'cmd.exe'
    $psi.Arguments = "/C setx /M HF_TOKEN `"$currentToken`""
    $psi.CreateNoWindow = $true
    $psi.UseShellExecute = $false
    $proc = [System.Diagnostics.Process]::Start($psi)
    $proc.WaitForExit()
    if ($proc.ExitCode -eq 0) {
      Write-Note 'HF_TOKEN persisted to system environment'
      try {
        $psiHub = New-Object System.Diagnostics.ProcessStartInfo
        $psiHub.FileName = 'cmd.exe'
        $psiHub.Arguments = "/C setx /M HF_HUB_ENABLE_HF_TRANSFER 1"
        $psiHub.CreateNoWindow = $true
        $psiHub.UseShellExecute = $false
        $procHub = [System.Diagnostics.Process]::Start($psiHub)
        $procHub.WaitForExit()
        if ($procHub.ExitCode -ne 0) { Write-Warn 'setx /M HF_HUB_ENABLE_HF_TRANSFER failed (insufficient rights?)' }
      } catch { Write-Warn "Failed to persist HF_HUB_ENABLE_HF_TRANSFER for system: $_" }
    } else {
      Write-Warn 'setx /M HF_TOKEN failed (insufficient rights?)'
    }
  } catch { Write-Warn "Failed to persist HF_TOKEN for system: $_" }
  if (-not $AppendToEnvLocal) {
    try {
      $repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
      $envFile = Join-Path $repoRoot '.env.local'
      $existing = @()
      if (Test-Path $envFile) { $existing = Get-Content -LiteralPath $envFile }
      $header = @($existing | Where-Object { $_.StartsWith('#') })
      $entries = [ordered]@{}
      foreach ($entry in $existing | Where-Object { (-not $_.StartsWith('#')) -and ($_ -match '=') }) {
        $split = $entry.Split('=',2)
        $entries[$split[0]] = $split[1]
      }
      $entries['HF_TOKEN'] = $currentToken
      $entries['HF_HUB_ENABLE_HF_TRANSFER'] = '1'
      $outLines = @()
      if ($header.Count) { $outLines += $header }
      foreach ($kv in $entries.GetEnumerator()) {
        $outLines += ($kv.Key + '=' + $kv.Value)
      }
      Set-Content -LiteralPath $envFile -Value $outLines -Encoding UTF8
      Write-Note '.env.local updated with HF_TOKEN'
    } catch { Write-Warn "Failed to update .env.local with HF_TOKEN: $_" }
  }
}

# Convenience: set PYANNOTE_TOKEN if provided
if ($PyannoteToken) {
  Set-EnvVar -Name 'PYANNOTE_TOKEN' -Value $PyannoteToken
}

# Unset variables (Process and User)
if ($Unset) {
  foreach ($name in $Unset) {
    try {
      if (-not $OnlyIfMissing) {
        [Environment]::SetEnvironmentVariable($name, $null, 'Process') | Out-Null
        [Environment]::SetEnvironmentVariable($name, $null, 'User') | Out-Null
        Write-Ok ("Unset {0} (Process/User)" -f $name)
      }
      if ($AppendToEnvLocal) {
        $repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
        $envFile = Join-Path $repoRoot '.env.local'
        $content = ''
        if (Test-Path $envFile) { $content = Get-Content -Raw $envFile }
        # Remove any exact KEY=... lines and add a commented placeholder
        $content = ($content -split "`r?`n") | Where-Object { $_ -notmatch "^$name=" } | ForEach-Object { $_ }
        $content = ($content -join "`r`n")
        if ($content -notmatch "^#\s*$name=") { $content += "`r`n# $name=" }
        Set-Content -LiteralPath $envFile -Value $content -Encoding UTF8
        Write-Note ".env.local updated for $name"
      }
    } catch { Write-Warn ("Failed to unset {0}" -f $name) }
  }
}

# Append directories to User PATH (idempotent)
if ($AddPath) {
  $current = [Environment]::GetEnvironmentVariable('Path','User')
  if (-not $current) { $current = '' }
  $parts = ($current -split ';') | Where-Object { $_ -and $_.Trim() -ne '' }
  $changed = $false
  foreach ($p in $AddPath) {
    if ($p -and (Test-Path $p)) {
      if (-not ($parts -contains $p)) {
        $parts += $p
        $changed = $true
        Write-Note ("PATH + {0}" -f $p)
      }
    } else {
      Write-Warn ("AddPath skip (missing): {0}" -f $p)
    }
  }
  if ($changed) {
    $newPath = ($parts -join ';')
    if ($Persist) {
      setx PATH "$newPath" | Out-Null
      Write-Ok 'User PATH updated'
    } else {
      [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
      Write-Ok 'User PATH updated (session)'
    }
  }
}

Write-Ok 'Done.'
