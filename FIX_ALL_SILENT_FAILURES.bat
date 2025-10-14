@echo off
setlocal EnableDelayedExpansion

:: ╔═══════════════════════════════════════════════════════════════╗
:: ║  🔧 Fix All Silent Failures - Comprehensive                   ║
:: ╚═══════════════════════════════════════════════════════════════╝

call "%~dp0scripts\check_conda.bat" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Conda not configured properly
    pause
    exit /b 1
)

echo ╔═══════════════════════════════════════════════════════════════╗
echo ║  🔧 GoodQ Silent Failure Fixer                                ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.
echo This will automatically fix ALL silent failures found by the audit:
echo   • Bare except: clauses
echo   • Silent exception handlers  
echo   • Functions returning None without logging
echo   • Unused exception variables
echo.
echo Backups will be created in: L:\goodq4all\data\backups\
echo.

set /p CONFIRM="Apply fixes to ALL files? (yes/no): "
if /i not "%CONFIRM%"=="yes" (
    echo.
    echo [CANCELLED] No changes made
    pause
    exit /b 0
)

echo.
echo ════════════════════════════════════════════════════════════════
echo 🔍 STEP 1: Running audit to find issues...
echo ════════════════════════════════════════════════════════════════
echo.

conda run -n goodq_zenml python "%~dp0scripts\audit_all_exceptions.py"
if errorlevel 1 (
    echo [ERROR] Audit failed
    pause
    exit /b 1
)

echo.
echo ════════════════════════════════════════════════════════════════
echo 🔧 STEP 2: Applying fixes...
echo ════════════════════════════════════════════════════════════════
echo.

conda run -n goodq_zenml python -c "from pathlib import Path; import sys; sys.path.insert(0, str(Path('L:/goodq4all'))); from scripts.fix_all_silent_failures import SilentFailureFixer; fixer = SilentFailureFixer('L:/goodq4all/steps'); fixer.fix_all(dry_run=False)"

if errorlevel 1 (
    echo [ERROR] Fixes failed
    pause
    exit /b 1
)

echo.
echo ════════════════════════════════════════════════════════════════
echo ✅ STEP 3: Verifying fixes...
echo ════════════════════════════════════════════════════════════════
echo.

conda run -n goodq_zenml python "%~dp0scripts\audit_all_exceptions.py"

echo.
echo ╔═══════════════════════════════════════════════════════════════╗
echo ║  ✅ COMPLETE                                                   ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.
echo Next steps:
echo   1. Review changes in your code editor
echo   2. Run: CLEAR_AND_REINGEST.bat
echo   3. Test with a sample video
echo.
echo   If issues occur, backups are in:
echo   L:\goodq4all\data\backups\pre_silent_failure_fix\
echo.

pause
