@echo off
setlocal EnableExtensions

set "FAILED_STAGE="

echo.
echo ============================================================
echo   GoodQ Bootstrap Validation
echo ============================================================
echo.

echo [Stage 1] Environment Info
echo ------------------------------------------------------------
python --version
if errorlevel 1 (
  set "FAILED_STAGE=1 (python unavailable)"
  goto :fail
)
for /f "delims=" %%i in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set "GIT_BRANCH=%%i"
for /f "delims=" %%i in ('git rev-parse --short HEAD 2^>nul') do set "GIT_COMMIT=%%i"
if not defined GIT_BRANCH set "GIT_BRANCH=unknown"
if not defined GIT_COMMIT set "GIT_COMMIT=unknown"
echo Branch: %GIT_BRANCH%
echo Commit: %GIT_COMMIT%
echo CWD   : %CD%
echo.

echo [Stage 2] Documentation Governance
echo ------------------------------------------------------------
python scripts\docs\doc_drift_lint.py
if errorlevel 1 (
  set "FAILED_STAGE=2 (doc_drift_lint)"
  goto :fail
)
echo Stage 2 PASS
echo.

echo [Stage 3] Bootstrap Sanity
echo ------------------------------------------------------------
python scripts\bootstrap_verify.py --json
if errorlevel 1 (
  set "FAILED_STAGE=3 (bootstrap_verify error)"
  goto :fail
)
echo Stage 3 PASS (warnings are non-fatal)
echo.

echo [Stage 4] Test Suite
echo ------------------------------------------------------------
python -m pytest -q
if errorlevel 1 (
  set "FAILED_STAGE=4 (pytest)"
  goto :fail
)
echo Stage 4 PASS
echo.

echo [Stage 5] Optional System Signals (non-fatal)
echo ------------------------------------------------------------
if exist vendor\qdrant\qdrant.exe (
  echo Qdrant binary: PRESENT ^(vendor\qdrant\qdrant.exe^)
) else (
  echo Qdrant binary: MISSING
)

wsl --status >nul 2>nul
if errorlevel 1 (
  echo WSL: NOT AVAILABLE
) else (
  echo WSL: AVAILABLE
)

python -c "import importlib.util; s=importlib.util.find_spec('torch'); print('CUDA visible:', __import__('torch').cuda.is_available() if s else 'torch not installed')"
if errorlevel 1 (
  echo CUDA probe: unable to evaluate (non-fatal)
)
echo.

echo ============================================================
echo   BOOTSTRAP VALIDATION: PASS
echo ============================================================
echo.
exit /b 0

:fail
echo.
echo ============================================================
echo   BOOTSTRAP VALIDATION: FAIL
echo   Failed at stage: %FAILED_STAGE%
echo ============================================================
echo.
exit /b 1
