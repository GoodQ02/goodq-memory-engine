# Phase 1 Audio Diarization Optimization - Verification

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "PHASE 1 VERIFICATION: Audio Diarization Chunking" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan

# 1. Check step.py exists and has chunking code
Write-Host "
[1/5] Checking audio_diarize implementation..." -ForegroundColor Yellow
$stepFile = "L:\goodq4all\steps\audio_diarize\step.py"
if (Test-Path $stepFile) {
    $content = Get-Content $stepFile -Raw
    if ($content -match "_extract_audio_chunk" -and $content -match "_merge_speaker_segments") {
        Write-Host "  [OK] Chunking functions found" -ForegroundColor Green
    } else {
        Write-Host "  [ERROR] Chunking functions missing" -ForegroundColor Red
    }
    if ($content -match "chunk_size_minutes") {
        Write-Host "  [OK] Configuration integration found" -ForegroundColor Green
    } else {
        Write-Host "  [ERROR] Configuration integration missing" -ForegroundColor Red
    }
} else {
    Write-Host "  [ERROR] step.py not found" -ForegroundColor Red
}

# 2. Check config.yaml has chunk_size_minutes
Write-Host "
[2/5] Checking configuration..." -ForegroundColor Yellow
$configFile = "L:\goodq4all\config.yaml"
if (Test-Path $configFile) {
    $configContent = Get-Content $configFile -Raw
    if ($configContent -match "chunk_size_minutes") {
        Write-Host "  [OK] chunk_size_minutes found in config" -ForegroundColor Green
        # Extract value
        if ($configContent -match "chunk_size_minutes:\s*(\d+\.?\d*)") {
            Write-Host "  [OK] Value: $($matches[1]) minutes" -ForegroundColor Green
        }
    } else {
        Write-Host "  [ERROR] chunk_size_minutes missing from config" -ForegroundColor Red
    }
} else {
    Write-Host "  [ERROR] config.yaml not found" -ForegroundColor Red
}

# 3. Check backup exists
Write-Host "
[3/5] Checking backups..." -ForegroundColor Yellow
$backupFile = "L:\goodq4all\steps\audio_diarize\step.py.backup_before_chunking"
if (Test-Path $backupFile) {
    Write-Host "  [OK] Backup created" -ForegroundColor Green
} else {
    Write-Host "  [WARN] No backup found (may not be needed)" -ForegroundColor Yellow
}

# 4. Check test suite exists
Write-Host "
[4/5] Checking test suite..." -ForegroundColor Yellow
$testFile = "L:\goodq4all\tests\test_diarization_chunking.py"
if (Test-Path $testFile) {
    Write-Host "  [OK] Test suite created" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] Test suite missing" -ForegroundColor Red
}

# 5. Check documentation
Write-Host "
[5/5] Checking documentation..." -ForegroundColor Yellow
$docs = @(
    "L:\goodq4all\docs\AUDIO_DIARIZATION_OPTIMIZATION_PLAN.md",
    "L:\goodq4all\docs\PHASE_1_AUDIO_DIARIZATION_COMPLETE.md"
)
foreach ($doc in $docs) {
    if (Test-Path $doc) {
        Write-Host "  [OK] $(Split-Path $doc -Leaf)" -ForegroundColor Green
    } else {
        Write-Host "  [ERROR] $(Split-Path $doc -Leaf) missing" -ForegroundColor Red
    }
}

Write-Host "
" + ("=" * 80) -ForegroundColor Cyan
Write-Host "VERIFICATION COMPLETE" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan

Write-Host "
Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Ensure PYANNOTE_TOKEN environment variable is set"
Write-Host "  2. Run: python tests\test_diarization_chunking.py"
Write-Host "  3. Test with real home movie"
Write-Host "  4. Monitor GPU usage and timing"
Write-Host "  5. Proceed to Phase 2 (GPU Memory Management)"
