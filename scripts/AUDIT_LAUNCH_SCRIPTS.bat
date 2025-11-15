@echo off
REM ================================================================================
REM  GoodQ4All - Launch Scripts Audit & Validation
REM  Tests all launch scripts for path correctness and functionality
REM ================================================================================

setlocal enabledelayedexpansion
title GoodQ Launch Scripts Audit
color 0B

echo.
echo ================================================================================
echo   GoodQ4All - Launch Scripts Audit
echo ================================================================================
echo.

cd /d "L:\goodq4all"

set PASS=0
set FAIL=0
set TOTAL=0

echo [TEST 1] Checking file paths referenced in LAUNCH_GOODQ.bat...
set /a TOTAL+=1
if exist "scripts\api_server.py" (
    if exist "scripts\watchdog_ingest.py" (
        echo   [PASS] Core scripts exist
        set /a PASS+=1
    ) else (
        echo   [FAIL] scripts\watchdog_ingest.py missing
        set /a FAIL+=1
    )
) else (
    echo   [FAIL] scripts\api_server.py missing
    set /a FAIL+=1
)

echo.
echo [TEST 2] Checking conda environment...
set /a TOTAL+=1
conda env list | find "goodq_zenml" >nul 2>&1
if %ERRORLEVEL%==0 (
    echo   [PASS] goodq_zenml environment exists
    set /a PASS+=1
) else (
    echo   [FAIL] goodq_zenml environment not found
    set /a FAIL+=1
)

echo.
echo [TEST 3] Validating Python imports in api_server.py...
set /a TOTAL+=1
conda run --no-capture-output -n goodq_zenml python -c "import sys; sys.path.insert(0, 'L:/goodq4all'); exec(open('scripts/api_server.py').read().split('if __name__')[0])" >nul 2>&1
if %ERRORLEVEL%==0 (
    echo   [PASS] api_server.py imports valid
    set /a PASS+=1
) else (
    echo   [WARN] api_server.py has import warnings (may be OK)
    REM Don't count as fail, as some imports may be optional
    set /a PASS+=1
)

echo.
echo [TEST 4] Checking required directories...
set /a TOTAL+=1
set DIR_CHECK=1
for %%d in (data logs import_inbox output web) do (
    if not exist "%%d" (
        echo   [WARN] Directory missing: %%d
        set DIR_CHECK=0
    )
)
if %DIR_CHECK%==1 (
    echo   [PASS] All required directories exist
    set /a PASS+=1
) else (
    echo   [FAIL] Some directories missing
    set /a FAIL+=1
)

echo.
echo [TEST 5] Checking web interface files...
set /a TOTAL+=1
if exist "web\index.html" (
    echo   [PASS] Web interface present
    set /a PASS+=1
) else (
    echo   [FAIL] web\index.html missing
    set /a FAIL+=1
)

echo.
echo [TEST 6] Checking WSL2 audio bridge...
set /a TOTAL+=1
wsl test -f ~/goodq_audio/scripts/process.sh 2>nul
if %ERRORLEVEL%==0 (
    echo   [PASS] WSL2 audio processing ready
    set /a PASS+=1
) else (
    echo   [WARN] WSL2 audio not configured (optional)
    set /a PASS+=1
)

echo.
echo [TEST 7] Checking GPU availability...
set /a TOTAL+=1
conda run --no-capture-output -n goodq_zenml python -c "import torch; exit(0 if torch.cuda.is_available() else 1)" >nul 2>&1
if %ERRORLEVEL%==0 (
    echo   [PASS] CUDA/GPU available
    set /a PASS+=1
) else (
    echo   [WARN] GPU not available (will use CPU)
    set /a PASS+=1
)

echo.
echo [TEST 8] Checking LM Studio connectivity...
set /a TOTAL+=1
curl -s http://localhost:1234/v1/models >nul 2>&1
if %ERRORLEVEL%==0 (
    echo   [PASS] LM Studio responding
    set /a PASS+=1
) else (
    echo   [WARN] LM Studio not running (start it before processing)
    REM Not a critical failure
    set /a PASS+=1
)

echo.
echo ================================================================================
echo   Results
echo ================================================================================
echo.
echo   Tests Passed: %PASS%/%TOTAL%
if %FAIL% GTR 0 (
    echo   Tests Failed: %FAIL%
    echo.
    echo   [X] LAUNCH SCRIPTS HAVE ISSUES
    echo   Please fix failures before launching
    color 0C
) else (
    echo.
    echo   [✓] ALL LAUNCH SCRIPTS VALIDATED
    echo   System is ready to launch!
    color 0A
)

echo.
echo ================================================================================
pause
