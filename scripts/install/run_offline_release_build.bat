@echo off
setlocal EnableExtensions
title GoodQ4All Offline Baseline Release Build

echo.
echo ============================================================
echo   GoodQ4All baseline installer - offline release build
echo ============================================================
echo.

for %%I in ("%~dp0") do set "BUILD_ROOT=%%~fI"
for %%I in ("%BUILD_ROOT%\..\..") do set "REPO_ROOT=%%~fI"

for /f %%I in ('powershell -NoProfile -Command "[DateTime]::Now.ToString('yyyyMMdd_HHmmss')"') do set "RUN_ID=%%I"
if "%GOODQ_RELEASE_OUTPUT_ROOT%"=="" (
    set "GOODQ_RELEASE_OUTPUT_ROOT=%USERPROFILE%\OneDrive\One_Domingo\GoodQ4All_CleanInstall_Verification\baseline_installer_%RUN_ID%"
)

for /f "tokens=2 delims== " %%I in ('findstr /b /c:"GOODQ_VERSION =" "%REPO_ROOT%\goodq_version.py"') do set "EXPECTED_VERSION=%%~I"
for /f %%I in ('git -C "%REPO_ROOT%" rev-parse HEAD') do set "EXPECTED_COMMIT=%%I"
if "%EXPECTED_VERSION%"=="" (
    echo [BLOCKED] Could not determine the canonical GoodQ version.
    goto :failed
)
if "%EXPECTED_COMMIT%"=="" (
    echo [BLOCKED] Could not determine the source commit.
    goto :failed
)

if not exist "%GOODQ_RELEASE_OUTPUT_ROOT%" mkdir "%GOODQ_RELEASE_OUTPUT_ROOT%"
set "BUILD_LOG=%GOODQ_RELEASE_OUTPUT_ROOT%\offline_build.log"
set "RECEIPT=%GOODQ_RELEASE_OUTPUT_ROOT%\offline_build_receipt.txt"

echo Output: %GOODQ_RELEASE_OUTPUT_ROOT%
echo.
echo [1/3] Checking that this workstation is offline...
pushd "%BUILD_ROOT%"
powershell -NoProfile -ExecutionPolicy Bypass -File .\preflight_check.ps1 > "%BUILD_LOG%" 2>&1
if errorlevel 1 (
    echo [BLOCKED] Offline preflight did not pass. See:
    echo           %BUILD_LOG%
    popd
    goto :failed
)

echo [2/3] Building the baseline installer from the local cache...
set "GOODQ_INSTALLER_BUILD_ROOT=%BUILD_ROOT%"
set "GOODQ_INSTALLER_OUTPUT_ROOT=%GOODQ_RELEASE_OUTPUT_ROOT%"
call .\build_installer.bat >> "%BUILD_LOG%" 2>&1
if errorlevel 1 (
    echo [FAILED] Build stopped. See:
    echo          %BUILD_LOG%
    popd
    goto :failed
)

echo [3/3] Verifying the exact release asset receipt...
powershell -NoProfile -ExecutionPolicy Bypass -File .\verify_release_asset.ps1 -AssetRoot "%GOODQ_RELEASE_OUTPUT_ROOT%" -ExpectedVersion "%EXPECTED_VERSION%" -ExpectedCommit "%EXPECTED_COMMIT%" > "%RECEIPT%" 2>&1
if errorlevel 1 (
    echo [FAILED] Asset verification did not pass. See:
    echo          %RECEIPT%
    popd
    goto :failed
)
popd

echo.
echo [READY] Offline baseline installer build and verification passed.
echo         Assets and receipts are in:
echo         %GOODQ_RELEASE_OUTPUT_ROOT%
echo.
echo You may reconnect to the internet now, then return to Codex for review.
pause
exit /b 0

:failed
echo.
echo The release build did not complete. Leave this window open for the receipt.
pause
exit /b 1
