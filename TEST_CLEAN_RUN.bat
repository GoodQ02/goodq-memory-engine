@echo off
REM ============================================================================
REM GoodQ Clean Test Run
REM Clears databases and runs full pipeline on sample.mp4
REM ============================================================================

title GoodQ Clean Test Run

echo.
echo ╔═══════════════════════════════════════════════════════════════╗
echo ║                 GoodQ Clean Test Run                          ║
echo ║        Full pipeline test with fresh databases                ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.
echo ⚠️  WARNING: This will clear all existing databases!
echo.
pause

cd /d L:\goodq4all

conda run -n goodq_zenml python scripts\test_clean_run.py

echo.
echo ═══════════════════════════════════════════════════════════════
echo Test complete! Check output above for results.
echo ═══════════════════════════════════════════════════════════════
echo.
pause
