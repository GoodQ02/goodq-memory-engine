@echo off
setlocal EnableExtensions

set "FAILED_STAGE="
set "EXIT_CODE=1"
set "PUSHD_OK="
set "BOUND_ENV_OK="

for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"
pushd "%REPO_ROOT%" >nul 2>nul
if errorlevel 1 (
  set "FAILED_STAGE=0 (repo root resolve)"
  goto :fail
)
set "PUSHD_OK=1"

call "%REPO_ROOT%\scripts\_lib\interpreter_bindings.bat"
if errorlevel 1 (
  set "FAILED_STAGE=0 (interpreter binding)"
  goto :fail
)

if "%CONDA_EXE%"=="conda" (
  where conda >nul 2>nul
  if errorlevel 1 (
    set "FAILED_STAGE=0 (conda unavailable)"
    goto :fail
  )
) else (
  if not exist "%CONDA_EXE%" (
    set "FAILED_STAGE=0 (conda unavailable)"
    goto :fail
  )
)

echo.
echo ============================================================
echo   GoodQ Bootstrap Validation
echo ============================================================
echo.

echo [Stage 1] Environment Info
echo ------------------------------------------------------------
echo Ambient Python:
python --version
if errorlevel 1 (
  set "FAILED_STAGE=1 (python unavailable)"
  goto :fail
)
echo Bound Conda Env: %GOODQ_CONDA_ENV%
"%CONDA_EXE%" run --no-capture-output -n %GOODQ_CONDA_ENV% python --version
if errorlevel 1 (
  set "FAILED_STAGE=1 (bound env unavailable)"
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
"%CONDA_EXE%" run --no-capture-output -n %GOODQ_CONDA_ENV% python "%REPO_ROOT%\scripts\docs\doc_drift_lint.py"
if errorlevel 1 (
  set "FAILED_STAGE=2 (doc_drift_lint)"
  goto :fail
)
echo Stage 2 PASS
echo.

echo [Stage 3] Bootstrap Sanity
echo ------------------------------------------------------------
"%CONDA_EXE%" run --no-capture-output -n %GOODQ_CONDA_ENV% python "%REPO_ROOT%\scripts\bootstrap_verify.py" --json
if errorlevel 1 (
  set "FAILED_STAGE=3 (bootstrap_verify error)"
  goto :fail
)
echo Stage 3 PASS (warnings are non-fatal)
echo.

echo [Stage 4] Test Suite
echo ------------------------------------------------------------
"%CONDA_EXE%" run --no-capture-output -n %GOODQ_CONDA_ENV% python -m pytest -q
if errorlevel 1 (
  set "FAILED_STAGE=4 (pytest)"
  goto :fail
)
echo Stage 4 PASS
echo.

echo [Stage 5] Optional System Signals (non-fatal)
echo ------------------------------------------------------------
if exist "%REPO_ROOT%\vendor\qdrant\qdrant.exe" (
  echo Qdrant binary: PRESENT ^(%REPO_ROOT%\vendor\qdrant\qdrant.exe^)
) else (
  echo Qdrant binary: MISSING
)

wsl --status >nul 2>nul
if errorlevel 1 (
  echo WSL: NOT AVAILABLE
) else (
  echo WSL: AVAILABLE
)

"%CONDA_EXE%" run --no-capture-output -n %GOODQ_CONDA_ENV% python -c "import importlib.util; s=importlib.util.find_spec('torch'); print('CUDA visible:', __import__('torch').cuda.is_available() if s else 'torch not installed')"
if errorlevel 1 (
  echo CUDA probe: unable to evaluate (non-fatal)
)
echo.

echo ============================================================
echo   BOOTSTRAP VALIDATION: PASS
echo ============================================================
echo.
set "EXIT_CODE=0"
goto :cleanup

:fail
echo.
echo ============================================================
echo   BOOTSTRAP VALIDATION: FAIL
echo   Failed at stage: %FAILED_STAGE%
echo ============================================================
echo.
set "EXIT_CODE=1"
goto :cleanup

:cleanup
if defined PUSHD_OK popd >nul 2>nul
exit /b %EXIT_CODE%
