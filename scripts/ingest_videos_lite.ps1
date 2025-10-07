Param(
  [string]$InputDir = 'import_inbox',
  [string]$Workspace = 'logs\\ingest_lite',
  [string]$Output = 'logs\\ingest_lite\\results.json',
  [int]$MaxVideos = 1,
  [int]$MaxScenes = 12,
  [Nullable[Double]]$SceneThreshold,
  [Nullable[Double]]$MinSceneSeconds,
  [switch]$NoSync,
  [switch]$VerboseSteps,
  [int]$StepTimeoutSeconds = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Info([string]$Message)  { Write-Host "[lite] $Message" -ForegroundColor Cyan }
function Write-Ok([string]$Message)    { Write-Host "[lite] $Message" -ForegroundColor Green }
function Write-Warn([string]$Message)  { Write-Host "[lite] $Message" -ForegroundColor Yellow }
function Fail([string]$Message)        { Write-Error $Message; exit 1 }

$DefaultPyannoteToken = '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'

function Get-EnvCascade([string]$Name) {
  foreach ($scope in @('Process','User','Machine')) {
    $val = [Environment]::GetEnvironmentVariable($Name, $scope)
    if (-not [string]::IsNullOrEmpty($val)) { return $val }
  }
  return $null
}

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot

if (-not $NoSync) {
  $syncScript = Join-Path $repoRoot 'scripts\\sync_env_local.ps1'
  if (Test-Path $syncScript) {
    Write-Info 'Syncing .env.local with system environment variables'
    try {
      & $syncScript | Out-Null
    } catch {
      Write-Warn "sync_env_local.ps1 reported an issue: $_"
    }
  }
}

function Resolve-Rooted([string]$PathValue, [string]$BaseDir) {
  if ([string]::IsNullOrWhiteSpace($PathValue)) { return $null }
  if ([System.IO.Path]::IsPathRooted($PathValue)) {
    return (Resolve-Path -LiteralPath $PathValue -ErrorAction Stop).Path
  }
  return (Join-Path $BaseDir $PathValue)
}

$inputPath = Resolve-Rooted -PathValue $InputDir -BaseDir $repoRoot
if (-not $inputPath -or -not (Test-Path -LiteralPath $inputPath)) {
  Fail "Input directory not found: $InputDir"
}

$workspacePath = Resolve-Rooted -PathValue $Workspace -BaseDir $repoRoot
$null = New-Item -ItemType Directory -Path $workspacePath -Force

$outputPath = Resolve-Rooted -PathValue $Output -BaseDir $repoRoot
$outputDir = Split-Path -Parent $outputPath
$null = New-Item -ItemType Directory -Path $outputDir -Force

Write-Info "Ingesting from $inputPath"
Write-Info "Workspace: $workspacePath"

$pythonArgs = @(
  '-m','zenml_project.cli.run_ingestion',
  '--input-dir', $inputPath,
  '--workspace', $workspacePath,
  '--output', $outputPath
)
if ($VerboseSteps) { $pythonArgs += '--verbose' }
if ($StepTimeoutSeconds -gt 0) { $pythonArgs += @('--step-timeout', [string]$StepTimeoutSeconds) }
if ($MaxVideos -gt 0)   { $pythonArgs += @('--max-videos', $MaxVideos) }
if ($MaxScenes -gt 0)   { $pythonArgs += @('--max-scenes', $MaxScenes) }
if ($PSBoundParameters.ContainsKey('SceneThreshold')) {
  $pythonArgs += @('--scene-threshold', ('{0:F2}' -f $SceneThreshold))
}
if ($PSBoundParameters.ContainsKey('MinSceneSeconds')) {
  $pythonArgs += @('--min-scene-seconds', ('{0:F2}' -f $MinSceneSeconds))
}

$command = @('conda','run','-n','goodq_zenml','python') + $pythonArgs
Write-Info "Running orchestrator: $($command -join ' ')"

$exe = $command[0]
$exeArgs = if ($command.Count -gt 1) { $command[1..($command.Count - 1)] } else { @() }
$env:HF_HOME = Get-EnvCascade 'HF_HOME'
if (-not $env:HF_HOME) { $env:HF_HOME = 'L:\models' }
$env:TORCH_HOME = Get-EnvCascade 'TORCH_HOME'
if (-not $env:TORCH_HOME) { $env:TORCH_HOME = 'L:\models' }
$env:HF_HUB_ENABLE_HF_TRANSFER = Get-EnvCascade 'HF_HUB_ENABLE_HF_TRANSFER'
if (-not $env:HF_HUB_ENABLE_HF_TRANSFER) { $env:HF_HUB_ENABLE_HF_TRANSFER = '0' }
$env:HF_TOKEN = Get-EnvCascade 'HF_TOKEN'
$pyannoteToken = Get-EnvCascade 'PYANNOTE_TOKEN'
if (-not $pyannoteToken) { $pyannoteToken = $DefaultPyannoteToken }
$env:PYANNOTE_TOKEN = $pyannoteToken
& $exe @exeArgs
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
  Fail "Ingestion failed with exit code $exitCode"
}

Write-Ok "Lite ingestion complete. Results: $outputPath"








