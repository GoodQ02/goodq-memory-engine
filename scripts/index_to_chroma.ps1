Param(
  [string]$EnvPrefix = 'goodq',
  [string]$Collection = 'goodq',
  [int]$Limit = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot

$envName = "${EnvPrefix}_text_embed"

Write-Host "[chroma] Installing API/Chroma requirements into $envName (if needed)" -ForegroundColor Cyan
try {
  & conda run -n $envName python -c "import chromadb, langchain_community" 2>$null
} catch {
  $prevNoUser=$env:PYTHONNOUSERSITE; $prevNoCache=$env:PIP_NO_CACHE_DIR; $prevDisable=$env:PIP_DISABLE_PIP_VERSION_CHECK
  try {
    $env:PYTHONNOUSERSITE='1'; $env:PIP_NO_CACHE_DIR='1'; $env:PIP_DISABLE_PIP_VERSION_CHECK='1'
    & conda run -n $envName python -m pip install --upgrade pip --no-cache-dir --no-user --isolated
    & conda run -n $envName python -m pip install -r api/requirements.txt --no-cache-dir --no-user --isolated --upgrade-strategy only-if-needed
  } finally {
    if ($null -ne $prevNoUser) { $env:PYTHONNOUSERSITE=$prevNoUser } else { Remove-Item Env:PYTHONNOUSERSITE -ErrorAction SilentlyContinue }
    if ($null -ne $prevNoCache) { $env:PIP_NO_CACHE_DIR=$prevNoCache } else { Remove-Item Env:PIP_NO_CACHE_DIR -ErrorAction SilentlyContinue }
    if ($null -ne $prevDisable) { $env:PIP_DISABLE_PIP_VERSION_CHECK=$prevDisable } else { Remove-Item Env:PIP_DISABLE_PIP_VERSION_CHECK -ErrorAction SilentlyContinue }
  }
}

Write-Host "[chroma] Building / updating collection..." -ForegroundColor Cyan
& conda run -n $envName python -m zenml_project.cli.chroma_store --collection $Collection --limit $Limit
