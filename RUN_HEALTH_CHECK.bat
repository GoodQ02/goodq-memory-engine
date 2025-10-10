@echo off
REM Quick health check after overnight audit
echo ========================================
echo GoodQ Health Check
echo ========================================
echo.
echo Running quick health check...
echo.
conda run -n goodq_zenml python scripts\quick_health_check.py
echo.
echo ========================================
echo.
echo For full details, see:
echo   - WELCOME_BACK.md
echo   - OVERNIGHT_AUDIT_SUMMARY.md
echo   - LINT_CLEAN_SESSION.md
echo.
pause
