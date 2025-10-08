Param(
  [string]$TestAudio = 'L:\GoodQ_4_All\smoke_inbox\test.wav'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Info($msg) { Write-Host "[test] $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "[test] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[test] $msg" -ForegroundColor Yellow }

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot

Write-Info "Testing audio_emotion step in isolation"

# Create test item JSON
$testItem = @{
  source_path = $TestAudio
  content_type = 'audio'
} | ConvertTo-Json -Compress

$testCfg = @{} | ConvertTo-Json -Compress

$tempItem = [System.IO.Path]::GetTempFileName()
$tempCfg = [System.IO.Path]::GetTempFileName()

try {
  Set-Content -Path $tempItem -Value $testItem -Encoding UTF8
  Set-Content -Path $tempCfg -Value $testCfg -Encoding UTF8
  
  Write-Info "Running audio_emotion step..."
  $testScript = @"
import sys, json
sys.path.insert(0, 'L:/')
from steps.steps.audio_emotion.step import audio_emotion

with open('$($tempItem.Replace('\','\\'))', 'r', encoding='utf-8') as f:
    item = json.load(f)
with open('$($tempCfg.Replace('\','\\'))', 'r', encoding='utf-8') as f:
    cfg = json.load(f)

print('[test] Calling audio_emotion step...')
result = audio_emotion(item, cfg)
print('[test] Result:', json.dumps(result, indent=2))
"@
  
  $scriptFile = [System.IO.Path]::GetTempFileName() + '.py'
  Set-Content -Path $scriptFile -Value $testScript -Encoding UTF8
  
  & conda run -n goodq_audio_emotion python $scriptFile
  
  if ($LASTEXITCODE -eq 0) {
    Write-Ok "Audio emotion step executed successfully!"
  } else {
    Write-Warn "Step returned non-zero exit code: $LASTEXITCODE"
  }
  
  Remove-Item -Path $scriptFile -Force -ErrorAction SilentlyContinue
  
} finally {
  Remove-Item -Path $tempItem -Force -ErrorAction SilentlyContinue
  Remove-Item -Path $tempCfg -Force -ErrorAction SilentlyContinue
}
