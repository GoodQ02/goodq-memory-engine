#!/usr/bin/env pwsh
# Quick Laptop Installation Test Script
# Run this after fresh installation to verify everything works

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  GoodQ4All - Laptop Installation Test" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

. (Join-Path $PSScriptRoot "..\\_lib\\interpreter_bindings.ps1")
$condaExe = Get-GoodQCondaExe

$testsPassed = 0
$testsFailed = 0

# Test 1: Conda Installation
Write-Host "[TEST 1/10] Checking Conda installation..." -ForegroundColor Yellow
try {
    $condaVersion = & $condaExe --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Conda found: $condaVersion" -ForegroundColor Green
        $testsPassed++
    } else {
        throw "Conda not found"
    }
} catch {
    Write-Host "  ✗ Conda not installed or not in PATH" -ForegroundColor Red
    Write-Host "    Install from: https://docs.conda.io/en/latest/miniconda.html" -ForegroundColor Yellow
    $testsFailed++
}

# Test 2: Python Paths
Write-Host "[TEST 2/10] Validating Python paths..." -ForegroundColor Yellow
try {
    & $condaExe run -n goodq_zenml python test_python_paths.py > $null 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ All Python paths configured correctly" -ForegroundColor Green
        $testsPassed++
    } else {
        throw "Python path validation failed"
    }
} catch {
    Write-Host "  ✗ Python path configuration issues" -ForegroundColor Red
    Write-Host "    Run: python configure_envs_pythonpath.py" -ForegroundColor Yellow
    $testsFailed++
}

# Test 3: GPU Access
Write-Host "[TEST 3/10] Checking GPU access..." -ForegroundColor Yellow
try {
    nvidia-smi > $null 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ NVIDIA GPU detected" -ForegroundColor Green
        $testsPassed++
    } else {
        throw "GPU not detected"
    }
} catch {
    Write-Host "  ✗ No NVIDIA GPU or driver issue" -ForegroundColor Red
    Write-Host "    Install latest NVIDIA drivers" -ForegroundColor Yellow
    $testsFailed++
}

# Test 4: Database Status
Write-Host "[TEST 4/10] Checking databases..." -ForegroundColor Yellow
try {
    $dbCheck = & $condaExe run -n goodq_zenml python check_db_status.py 2>&1
    if ($dbCheck -match "OK") {
        Write-Host "  ✓ Databases initialized" -ForegroundColor Green
        $testsPassed++
    } else {
        throw "Database check failed"
    }
} catch {
    Write-Host "  ✗ Database initialization issues" -ForegroundColor Red
    Write-Host "    Run: python -c 'from common.db_utils import init_all_databases; init_all_databases()'" -ForegroundColor Yellow
    $testsFailed++
}

# Test 5: FAISS Indices
Write-Host "[TEST 5/10] Checking FAISS indices..." -ForegroundColor Yellow
$faissPath = "output\faiss"
if (Test-Path $faissPath) {
    $indices = Get-ChildItem $faissPath -Filter "*.index"
    if ($indices.Count -ge 4) {
        Write-Host "  ✓ FAISS indices present ($($indices.Count) found)" -ForegroundColor Green
        $testsPassed++
    } else {
        Write-Host "  ⚠ Only $($indices.Count) FAISS indices (expected 4+)" -ForegroundColor Yellow
        $testsFailed++
    }
} else {
    Write-Host "  ✗ FAISS directory not found" -ForegroundColor Red
    $testsFailed++
}

# Test 6: Directory Structure
Write-Host "[TEST 6/10] Validating directory structure..." -ForegroundColor Yellow
$requiredDirs = @("import_inbox", "output", "logs", "steps", "envs", "pipelines")
$missingDirs = @()
foreach ($dir in $requiredDirs) {
    if (-not (Test-Path $dir)) {
        $missingDirs += $dir
    }
}
if ($missingDirs.Count -eq 0) {
    Write-Host "  ✓ All required directories present" -ForegroundColor Green
    $testsPassed++
} else {
    Write-Host "  ✗ Missing directories: $($missingDirs -join ', ')" -ForegroundColor Red
    $testsFailed++
}

# Test 7: Configuration Files
Write-Host "[TEST 7/10] Checking configuration..." -ForegroundColor Yellow
if ((Test-Path ".env.local") -and (Test-Path "config.yaml")) {
    Write-Host "  ✓ Configuration files present" -ForegroundColor Green
    $testsPassed++
} else {
    Write-Host "  ✗ Missing .env.local or config.yaml" -ForegroundColor Red
    Write-Host "    Copy .env.local.template to .env.local and configure" -ForegroundColor Yellow
    $testsFailed++
}

# Test 8: LM Studio Connection
Write-Host "[TEST 8/10] Testing LM Studio connection..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:1234/v1/models" -TimeoutSec 3 -ErrorAction Stop
    if ($response.StatusCode -eq 200) {
        Write-Host "  ✓ LM Studio server responding" -ForegroundColor Green
        $testsPassed++
    }
} catch {
    Write-Host "  ⚠ LM Studio not responding (optional)" -ForegroundColor Yellow
    Write-Host "    Start LM Studio and enable local server" -ForegroundColor Yellow
    $testsFailed++
}

# Test 9: Import Inbox
Write-Host "[TEST 9/10] Checking import inbox..." -ForegroundColor Yellow
if (Test-Path "import_inbox") {
    $files = Get-ChildItem "import_inbox" -File
    Write-Host "  ✓ Import inbox ready ($($files.Count) files)" -ForegroundColor Green
    $testsPassed++
} else {
    Write-Host "  ✗ Import inbox not found" -ForegroundColor Red
    $testsFailed++
}

# Test 10: GPU Management
Write-Host "[TEST 10/10] Testing GPU management..." -ForegroundColor Yellow
try {
    & $condaExe run -n goodq_zenml python test_gpu_management.py > $null 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ GPU management configured" -ForegroundColor Green
        $testsPassed++
    } else {
        throw "GPU management test failed"
    }
} catch {
    Write-Host "  ⚠ GPU management issues (check gpu_config.py)" -ForegroundColor Yellow
    $testsFailed++
}

# Summary
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  Test Summary" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  Passed: $testsPassed/10" -ForegroundColor Green
Write-Host "  Failed: $testsFailed/10" -ForegroundColor Red
Write-Host ""

if ($testsFailed -eq 0) {
    Write-Host "  🎉 All tests passed! System ready for production." -ForegroundColor Green
    Write-Host ""
    Write-Host "  Next steps:" -ForegroundColor Cyan
    Write-Host "    1. Start system: .\LAUNCH_GOODQ.bat" -ForegroundColor White
    Write-Host "    2. Open UI: http://localhost:30000" -ForegroundColor White
    Write-Host "    3. Add videos to import_inbox\" -ForegroundColor White
    Write-Host ""
} elseif ($testsFailed -le 2) {
    Write-Host "  ⚠ Minor issues detected. System should work but may need tuning." -ForegroundColor Yellow
    Write-Host "  Review failed tests above and fix before production use." -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "  ❌ Critical issues detected. Fix errors before proceeding." -ForegroundColor Red
    Write-Host "  See LAPTOP_INSTALL_GUIDE.md for troubleshooting." -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "================================================================================" -ForegroundColor Cyan
