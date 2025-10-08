Param(
  [string]$EnvPrefix = 'goodq',
  [int]$MaxFrames = 50
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Info($m){ Write-Host "[dryrun] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[dryrun] $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[dryrun] $m" -ForegroundColor Yellow }
function Fail($m){ Write-Error $m; exit 1 }

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot

Info 'Ingesting videos (stub) to generate per-video summaries input'
& pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'ingest_videos.ps1') -MaxFrames $MaxFrames

Info 'Running ingest_multimodal ZenML pipeline'
$zenEnv = "${EnvPrefix}_zenml"
$pyCode = @"
from steps.pipelines.ingest_multimodal_conda import ingest_multimodal
ingest_multimodal()
"@
$tmpPy = [System.IO.Path]::GetTempFileName()
try {
  Set-Content -LiteralPath $tmpPy -Value $pyCode -Encoding UTF8
  & conda run -n $zenEnv python $tmpPy
}
finally {
  Remove-Item -LiteralPath $tmpPy -Force -ErrorAction SilentlyContinue
}

Ok 'Dry run complete.'
