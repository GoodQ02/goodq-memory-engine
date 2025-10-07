#!/usr/bin/env pwsh
# Comprehensive Test Plan for GoodQ Project Polish
# Executes tests in priority order with validation after each step

Param(
  [switch]$SkipEnvCheck,
  [switch]$SkipReadiness,
  [switch]$SkipLiteTest,
  [int]$MaxFrames = 5,
  [int]$MaxSegments = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Section($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Magenta }
function Write-Info($msg) { Write-Host "[test] $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "[test] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[test] $msg" -ForegroundColor Yellow }
function Fail($msg) { Write-Error $msg; exit 1 }

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot

$results = @{
  priority1_audio_emotion = $false
  priority2_env_verification = $false
  priority3_readiness_checks = $false
  priority4_lite_ingestion = $false
  priority5_dedup_verification = $false
}

Write-Section "GoodQ Project Comprehensive Test Plan"
Write-Info "Repository: $repoRoot"
Write-Info "Test Configuration: MaxFrames=$MaxFrames, MaxSegments=$MaxSegments"

# ============================================================================
# Priority 1: Audio Emotion Environment (Already Fixed)
# ============================================================================
if (-not $SkipEnvCheck) {
  Write-Section "Priority 1: Verify Audio Emotion Environment"
  
  try {
    Write-Info "Checking audio_emotion packages..."
    $check = & conda run -n goodq_audio_emotion python -c "import torch, transformers, hf_transfer; print('OK')" 2>&1
    if ($check -match "OK") {
      Write-Ok "✓ Audio emotion environment has all dependencies"
      
      Write-Info "Checking CUDA availability..."
      $cuda = & conda run -n goodq_audio_emotion python -c "import torch; print(torch.cuda.is_available())" 2>&1
      if ($cuda -match "True") {
        Write-Ok "✓ CUDA is available in audio_emotion"
        $results.priority1_audio_emotion = $true
      } else {
        Write-Warn "✗ CUDA not available (may still work on CPU)"
      }
    } else {
      Write-Warn "✗ Audio emotion environment missing dependencies"
    }
  } catch {
    Write-Warn "✗ Failed to verify audio_emotion: $_"
  }
}

# ============================================================================
# Priority 2: Environment Verification
# ============================================================================
if (-not $SkipEnvCheck) {
  Write-Section "Priority 2: Verify All Environments"
  
  try {
    Write-Info "Counting environments..."
    $envCount = (& conda env list | Select-String "goodq" | Measure-Object -Line).Lines
    Write-Info "Found $envCount goodq environments"
    
    if ($envCount -ge 22) {
      Write-Ok "✓ All 22+ environments present"
      $results.priority2_env_verification = $true
    } else {
      Write-Warn "✗ Missing some environments (expected 22, got $envCount)"
      Write-Info "Run: pwsh scripts/prepare_step_envs.ps1 -EnvPrefix goodq -LinkProject"
    }
  } catch {
    Write-Warn "✗ Failed to verify environments: $_"
  }
}

# ============================================================================
# Priority 3: Readiness Checks
# ============================================================================
if (-not $SkipReadiness) {
  Write-Section "Priority 3: System & Cache Readiness"
  
  try {
    Write-Info "Running system_readiness_check.py..."
    $sysCheck = & python scripts\system_readiness_check.py 2>&1
    $sysExit = $LASTEXITCODE
    
    if ($sysExit -eq 0) {
      Write-Ok "✓ System readiness check passed"
    } else {
      Write-Warn "✗ System readiness check had issues (exit code: $sysExit)"
    }
    
    Write-Info "Running cache_readiness_check.py..."
    $cacheCheck = & python scripts\cache_readiness_check.py 2>&1
    $cacheExit = $LASTEXITCODE
    
    if ($cacheExit -eq 0) {
      Write-Ok "✓ Cache readiness check passed"
      $results.priority3_readiness_checks = $true
    } else {
      Write-Warn "✗ Cache readiness check had issues (exit code: $cacheExit)"
    }
  } catch {
    Write-Warn "✗ Failed to run readiness checks: $_"
  }
}

# ============================================================================
# Priority 4: Lite Ingestion Test
# ============================================================================
if (-not $SkipLiteTest) {
  Write-Section "Priority 4: Lite Ingestion End-to-End Test"
  
  try {
    Write-Info "Preparing test workspace..."
    $testWorkspace = "logs\test_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    New-Item -ItemType Directory -Path $testWorkspace -Force | Out-Null
    
    Write-Info "Running lite ingestion (MaxFrames=$MaxFrames, MaxSegments=$MaxSegments)..."
    Write-Info "Command: pwsh scripts/ingest_videos_lite.ps1 -InputDir smoke_inbox -Workspace $testWorkspace -MaxVideos 1 -MaxScenes $MaxSegments -VerboseSteps"
    
    $ingestStart = Get-Date
    $ingestOutput = & pwsh scripts/ingest_videos_lite.ps1 -InputDir smoke_inbox -Workspace $testWorkspace -MaxVideos 1 -MaxScenes $MaxSegments -VerboseSteps 2>&1
    $ingestExit = $LASTEXITCODE
    $ingestDuration = (Get-Date) - $ingestStart
    
    Write-Info "Ingestion completed in $($ingestDuration.TotalSeconds) seconds (exit code: $ingestExit)"
    
    if ($ingestExit -eq 0) {
      Write-Ok "✓ Lite ingestion completed successfully!"
      $results.priority4_lite_ingestion = $true
      
      # Check for results
      $resultsFile = Join-Path $testWorkspace "results.json"
      if (Test-Path $resultsFile) {
        $resultsData = Get-Content $resultsFile -Raw | ConvertFrom-Json
        Write-Info "Results: $($resultsData.scenes_processed) scenes processed"
      }
    } else {
      Write-Warn "✗ Lite ingestion failed (exit code: $ingestExit)"
      Write-Info "Check logs in: $testWorkspace"
    }
  } catch {
    Write-Warn "✗ Failed to run lite ingestion: $_"
  }
}

# ============================================================================
# Priority 5: Deduplication Verification
# ============================================================================
if (-not $SkipLiteTest) {
  Write-Section "Priority 5: Verify Deduplication Works"
  
  try {
    Write-Info "Checking step_runs.jsonl for dedupe entries..."
    $logFile = "L:\GoodQ_Data\logs\step_runs.jsonl"
    
    if (Test-Path $logFile) {
      $recentLines = Get-Content $logFile -Tail 50 | ForEach-Object {
        try { $_ | ConvertFrom-Json } catch { $null }
      } | Where-Object { $_ -ne $null }
      
      $dedupCount = ($recentLines | Where-Object { 
        $_.extra.reason -eq "dedupe" -or $_.status -eq "skipped" 
      } | Measure-Object).Count
      
      if ($dedupCount -gt 0) {
        Write-Ok "✓ Found $dedupCount deduplicated/skipped entries in recent logs"
        $results.priority5_dedup_verification = $true
      } else {
        Write-Info "No recent dedupe entries found (expected on first run)"
      }
    } else {
      Write-Warn "✗ step_runs.jsonl not found at $logFile"
    }
  } catch {
    Write-Warn "✗ Failed to verify deduplication: $_"
  }
}

# ============================================================================
# Summary Report
# ============================================================================
Write-Section "Test Summary"

$passed = 0
$total = $results.Count

foreach ($key in $results.Keys | Sort-Object) {
  $status = if ($results[$key]) { "✓ PASS" } else { "✗ FAIL/SKIP" }
  $color = if ($results[$key]) { "Green" } else { "Yellow" }
  Write-Host "  $key : " -NoNewline
  Write-Host $status -ForegroundColor $color
  if ($results[$key]) { $passed++ }
}

Write-Host "`nOverall: $passed / $total tests passed" -ForegroundColor $(if ($passed -eq $total) { "Green" } else { "Yellow" })

if ($passed -eq $total) {
  Write-Ok "`n🎉 All priorities completed successfully! Project is polished and ready."
} else {
  Write-Warn "`n⚠ Some tests failed or were skipped. Review output above."
}
