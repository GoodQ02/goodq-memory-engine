# ============================================================================
# GoodQ Full Diagnostic Suite - PowerShell Version
# Comprehensive testing and validation of the entire pipeline
# ============================================================================

$Host.UI.RawUI.WindowTitle = "GoodQ Full Diagnostic"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

. (Join-Path $PSScriptRoot "..\\_lib\\interpreter_bindings.ps1")
$condaExe = Get-GoodQCondaExe

Clear-Host
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "           GoodQ FULL DIAGNOSTIC SUITE                         " -ForegroundColor Cyan
Write-Host "                                                                " -ForegroundColor Cyan
Write-Host "  This will run comprehensive tests on your GoodQ system:      " -ForegroundColor White
Write-Host "  1. Code audit for silent failures                            " -ForegroundColor White
Write-Host "  2. System readiness check                                    " -ForegroundColor White
Write-Host "  3. Database health check                                     " -ForegroundColor White
Write-Host "  4. Clean test run on sample video                            " -ForegroundColor White
Write-Host "                                                                " -ForegroundColor White
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "Estimated time: 10-15 minutes" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press any key to continue..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

Set-Location L:\goodq4all

# ============================================================================
# PHASE 1: CODE AUDIT
# ============================================================================
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "PHASE 1: CODE AUDIT" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

try {
    & $condaExe run -n goodq_zenml python scripts\comprehensive_code_audit.py 2>&1 | Out-String | Write-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Code audit failed with exit code $LASTEXITCODE"
    }
} catch {
    Write-Host ""
    Write-Host "[ERROR] Code audit failed: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Press any key to exit..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

# ============================================================================
# PHASE 2: SYSTEM READINESS
# ============================================================================
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "PHASE 2: SYSTEM READINESS" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

try {
    & $condaExe run -n goodq_zenml python scripts\system_readiness_check.py 2>&1 | Out-String | Write-Host
    if ($LASTEXITCODE -ne 0) {
        throw "System readiness check failed with exit code $LASTEXITCODE"
    }
} catch {
    Write-Host ""
    Write-Host "[ERROR] System readiness check failed: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Press any key to exit..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

# ============================================================================
# PHASE 3: DATABASE HEALTH
# ============================================================================
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "PHASE 3: DATABASE HEALTH" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

& $condaExe run -n goodq_zenml python scripts\check_db_status.py 2>&1 | Out-String | Write-Host

# ============================================================================
# PHASE 4: CLEAN TEST RUN
# ============================================================================
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "PHASE 4: CLEAN TEST RUN" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "About to clear databases and run full pipeline test..." -ForegroundColor Yellow
Write-Host "Press any key to continue..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

try {
    & $condaExe run -n goodq_zenml python scripts\test_clean_run.py 2>&1 | Out-String | Write-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Clean test run failed with exit code $LASTEXITCODE"
    }
} catch {
    Write-Host ""
    Write-Host "[ERROR] Clean test run failed: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Press any key to exit..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

# ============================================================================
# COMPLETE
# ============================================================================
Write-Host ""
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "[OK] DIAGNOSTIC COMPLETE" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "Review the output above for any issues." -ForegroundColor White
Write-Host "Check L:\goodq4all\docs\project_communication\AUDIT_REPORT.md for detailed findings." -ForegroundColor White
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
