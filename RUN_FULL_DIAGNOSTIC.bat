@echo off
REM ============================================================================
REM GoodQ Full Diagnostic Suite
REM Comprehensive testing and validation of the entire pipeline
REM ============================================================================

title GoodQ Full Diagnostic

cls
echo.
echo ╔═══════════════════════════════════════════════════════════════╗
echo ║           GoodQ FULL DIAGNOSTIC SUITE                         ║
echo ║                                                                ║
echo ║  This will run comprehensive tests on your GoodQ system:      ║
echo ║  1. Code audit for silent failures                            ║
echo ║  2. System readiness check                                    ║
echo ║  3. Database health check                                     ║
echo ║  4. Clean test run on sample video                            ║
echo ║                                                                ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.
echo ⏱️  Estimated time: 10-15 minutes
echo.
pause

cd /d L:\goodq4all

echo.
echo ═══════════════════════════════════════════════════════════════
echo PHASE 1: CODE AUDIT
echo ═══════════════════════════════════════════════════════════════
echo.
conda run -n goodq_zenml python scripts\comprehensive_code_audit.py
if errorlevel 1 (
    echo ❌ Code audit failed
    pause
    exit /b 1
)

echo.
echo ═══════════════════════════════════════════════════════════════
echo PHASE 2: SYSTEM READINESS
echo ═══════════════════════════════════════════════════════════════
echo.
conda run -n goodq_zenml python scripts\system_readiness_check.py
if errorlevel 1 (
    echo ❌ System readiness check failed
    pause
    exit /b 1
)

echo.
echo ═══════════════════════════════════════════════════════════════
echo PHASE 3: DATABASE HEALTH
echo ═══════════════════════════════════════════════════════════════
echo.
conda run -n goodq_zenml python scripts\check_db_status.py

echo.
echo ═══════════════════════════════════════════════════════════════
echo PHASE 4: CLEAN TEST RUN
echo ═══════════════════════════════════════════════════════════════
echo.
echo About to clear databases and run full pipeline test...
pause

conda run -n goodq_zenml python scripts\test_clean_run.py
if errorlevel 1 (
    echo ❌ Clean test run failed
    pause
    exit /b 1
)

echo.
echo.
echo ═══════════════════════════════════════════════════════════════
echo ✅ DIAGNOSTIC COMPLETE
echo ═══════════════════════════════════════════════════════════════
echo.
echo Review the output above for any issues.
echo Check L:\goodq4all\docs\AUDIT_REPORT.md for detailed findings.
echo.
pause
