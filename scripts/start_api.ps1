Param(
  [Alias('Host')][string]$BindAddress = '0.0.0.0',
  [int]$Port = 8000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Write-Host ("Starting the GoodQ Retrieval API server on {0}:{1}..." -f $BindAddress, $Port) -ForegroundColor Cyan

# Ensure we run from repo root
try {
  $repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
  Set-Location $repoRoot
} catch {}

# Pass bind host/port to server via env and run our server wrapper that fixes sys.path
$env:GOODQ_API_HOST = $BindAddress
$env:GOODQ_API_PORT = [string]$Port

if (-not (Get-Command conda -ErrorAction SilentlyContinue)) {
  Write-Error 'conda not found on PATH. Please open an Anaconda/Miniconda PowerShell prompt.'
  exit 1
}

# Ensure API deps are present; install if missing (use temp file instead of heredoc)
$py = @"
try:
    import uvicorn, fastapi
    print('OK')
except Exception:
    print('MISS')
"@
$tmp = [System.IO.Path]::GetTempFileName()
Set-Content -LiteralPath $tmp -Value $py -Encoding UTF8
try {
  $check = & conda run -n goodq_text_embed python $tmp
} finally {
  Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
}
if (-not ($check | Out-String).Trim().StartsWith('OK')) {
  Write-Host '[api] Installing API requirements into goodq_text_embed...' -ForegroundColor Yellow
  $req = Join-Path $repoRoot 'api\requirements.txt'
  $prevNoUser=$env:PYTHONNOUSERSITE; $prevNoCache=$env:PIP_NO_CACHE_DIR; $prevDisable=$env:PIP_DISABLE_PIP_VERSION_CHECK
  try {
    $env:PYTHONNOUSERSITE='1'; $env:PIP_NO_CACHE_DIR='1'; $env:PIP_DISABLE_PIP_VERSION_CHECK='1'
    & conda run -n goodq_text_embed pip install --upgrade pip --no-cache-dir --no-user --isolated
    & conda run -n goodq_text_embed pip install -r $req --no-cache-dir --no-user --isolated --upgrade-strategy only-if-needed
  } finally {
    if ($null -ne $prevNoUser) { $env:PYTHONNOUSERSITE=$prevNoUser } else { Remove-Item Env:PYTHONNOUSERSITE -ErrorAction SilentlyContinue }
    if ($null -ne $prevNoCache) { $env:PIP_NO_CACHE_DIR=$prevNoCache } else { Remove-Item Env:PIP_NO_CACHE_DIR -ErrorAction SilentlyContinue }
    if ($null -ne $prevDisable) { $env:PIP_DISABLE_PIP_VERSION_CHECK=$prevDisable } else { Remove-Item Env:PIP_DISABLE_PIP_VERSION_CHECK -ErrorAction SilentlyContinue }
  }
}

# Invoke by file path so Python doesn't need to resolve the package before server.py adjusts sys.path
$serverPath = Join-Path $repoRoot 'api\server.py'
& conda run -n goodq_text_embed python $serverPath
