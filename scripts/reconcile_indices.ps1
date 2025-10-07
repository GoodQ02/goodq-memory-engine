Param(
  [string]$EnvPrefix = 'goodq'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Fail($m){ Write-Error $m; exit 1 }

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot

Write-Host "[reconcile] Rebuilding ID-maps from embeddings" -ForegroundColor Cyan
$envName = "${EnvPrefix}_text_embed"
& conda run -n $envName python -m zenml_project.cli.memory rebuild-id-maps | Write-Host

Write-Host "[reconcile] Cleaning placeholder rows (if any)" -ForegroundColor Cyan
& conda run -n $envName python -m zenml_project.cli.memory cleanup-placeholders | Write-Host

Write-Host "[reconcile] Running memory health check via CLI" -ForegroundColor Cyan
$out = & conda run -n $envName python -m zenml_project.cli.memory health-check
$code = $LASTEXITCODE
Write-Host $out
if ($code -ne 0) {
  Fail '[reconcile] Health-check reported errors or warnings.'
}

Write-Host '[reconcile] All good.' -ForegroundColor Green
