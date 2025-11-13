@echo off
REM ================================================================================
REM  GoodQ4All - Pre-Launch System Check
REM  Verify all systems are ready before starting
REM ================================================================================

setlocal enabledelayedexpansion
title GoodQ Pre-Launch Check
color 0E

echo.
echo ================================================================================
echo   GoodQ4All - Pre-Launch System Check
echo ================================================================================
echo.

cd /d "L:\goodq4all"

set PASS_COUNT=0
set FAIL_COUNT=0
set WARN_COUNT=0

REM Check 1: Environment exists
echo [1/8] Checking Conda Environment...
conda env list | find "goodq_zenml" >nul 2>&1
if %ERRORLEVEL%==0 (
    echo       [PASS] goodq_zenml environment exists
    set /a PASS_COUNT+=1
) else (
    echo       [FAIL] goodq_zenml environment not found!
    set /a FAIL_COUNT+=1
)

REM Check 2: GPU environments
echo [2/8] Checking GPU Environments...
set GPU_ENV_COUNT=0
for %%e in (goodq_audio_diarize goodq_audio_transcribe goodq_face_embed goodq_emotion_classify goodq_video_scene_detect) do (
    conda env list | find "%%e" >nul 2>&1
    if !ERRORLEVEL!==0 set /a GPU_ENV_COUNT+=1
)
if %GPU_ENV_COUNT%==5 (
    echo       [PASS] All 5 GPU environments present
    set /a PASS_COUNT+=1
) else (
    echo       [WARN] Only %GPU_ENV_COUNT%/5 GPU environments found
    set /a WARN_COUNT+=1
)

REM Check 3: CUDA availability
echo [3/8] Checking CUDA/GPU...
conda run --no-capture-output -n goodq_zenml python -c "import torch; exit(0 if torch.cuda.is_available() else 1)" >nul 2>&1
if %ERRORLEVEL%==0 (
    echo       [PASS] CUDA is available
    set /a PASS_COUNT+=1
) else (
    echo       [WARN] CUDA not detected
    set /a WARN_COUNT+=1
)

REM Check 4: Required directories
echo [4/8] Checking Directory Structure...
set DIR_OK=1
if not exist "L:\goodq4all\data" set DIR_OK=0
if not exist "L:\goodq4all\logs" set DIR_OK=0
if not exist "L:\goodq4all\import_inbox" set DIR_OK=0
if not exist "L:\goodq4all\output" set DIR_OK=0

if %DIR_OK%==1 (
    echo       [PASS] All required directories exist
    set /a PASS_COUNT+=1
) else (
    echo       [FAIL] Missing required directories
    set /a FAIL_COUNT+=1
)

REM Check 5: No conflicting processes
echo [5/8] Checking for Running Processes...
tasklist /FI "WINDOWTITLE eq GoodQ API Server*" 2>NUL | find /I /N "python.exe">NUL
if %ERRORLEVEL%==0 (
    echo       [WARN] GoodQ API Server already running
    set /a WARN_COUNT+=1
) else (
    echo       [PASS] No API Server running
    set /a PASS_COUNT+=1
)

tasklist /FI "WINDOWTITLE eq GoodQ Watchdog*" 2>NUL | find /I /N "python.exe">NUL
if %ERRORLEVEL%==0 (
    echo       [WARN] GoodQ Watchdog already running
    set /a WARN_COUNT+=1
) else (
    echo       [PASS] No Watchdog running
    set /a PASS_COUNT+=1
)

REM Check 6: System is clean
echo [6/8] Checking System State...
if exist "L:\goodq4all\logs\progress.json" (
    for /f "delims=" %%i in ('type "L:\goodq4all\logs\progress.json" ^| find "idle"') do set IDLE_FOUND=1
)
if defined IDLE_FOUND (
    echo       [PASS] System is idle and ready
    set /a PASS_COUNT+=1
) else (
    echo       [WARN] System may have stale state
    set /a WARN_COUNT+=1
)

REM Check 7: Video ready for processing
echo [7/8] Checking for Videos in Import Inbox...
dir /b "L:\goodq4all\import_inbox\*.mp4" >nul 2>&1
if %ERRORLEVEL%==0 (
    echo       [PASS] Videos detected in import_inbox
    set /a PASS_COUNT+=1
    dir /b "L:\goodq4all\import_inbox\*.mp4"
) else (
    echo       [WARN] No videos in import_inbox
    set /a WARN_COUNT+=1
    echo       (Drop videos in L:\goodq4all\import_inbox for processing)
)

REM Check 8: API server file exists
echo [8/8] Checking Core Files...
if exist "L:\goodq4all\api_server.py" (
    if exist "L:\goodq4all\scripts\watchdog_ingest.py" (
        echo       [PASS] Core scripts present
        set /a PASS_COUNT+=1
    ) else (
        echo       [FAIL] watchdog_ingest.py missing
        set /a FAIL_COUNT+=1
    )
) else (
    echo       [FAIL] api_server.py missing
    set /a FAIL_COUNT+=1
)

echo.
echo ================================================================================
echo   Results
echo ================================================================================
echo.
echo   [PASS] %PASS_COUNT% checks passed
if %WARN_COUNT% GTR 0 echo   [WARN] %WARN_COUNT% warnings
if %FAIL_COUNT% GTR 0 echo   [FAIL] %FAIL_COUNT% critical failures
echo.

if %FAIL_COUNT% GTR 0 (
    echo   [X] SYSTEM NOT READY
    echo   Please fix critical failures before launching
    color 0C
) else if %WARN_COUNT% GTR 0 (
    echo   [~] SYSTEM READY WITH WARNINGS
    echo   You can proceed, but some features may not work optimally
    color 0E
) else (
    echo   [v] SYSTEM READY TO LAUNCH!
    echo   Run LAUNCH_GOODQ.bat to start
    color 0A
)

echo.
echo ================================================================================
pause
