@echo off
setlocal EnableExtensions
title GoodQ4All v3.0.1 Offline GPU Release Build

echo.
echo ============================================================
echo   GoodQ4All v3.0.1 GPU installer - receipt-bound offline build
echo ============================================================
echo.

for %%I in ("%~dp0") do set "BUILD_ROOT=%%~fI"
for %%I in ("%BUILD_ROOT%\..\..") do set "REPO_ROOT=%%~fI"
call "%REPO_ROOT%\scripts\_lib\interpreter_bindings.bat"
if "%CONDA_EXE%"=="" (
    echo [BLOCKED] Could not resolve the private Conda launcher.
    goto :failed
)
for %%I in ("%CONDA_EXE%") do set "GOODQ_CONDA_SCRIPTS=%%~dpI"
for %%I in ("%GOODQ_CONDA_SCRIPTS%..") do set "GOODQ_CONDA_ROOT=%%~fI"
set "GOODQ_DEV_PYTHON=%GOODQ_CONDA_ROOT%\envs\%GOODQ_CONDA_ENV%\python.exe"
if not exist "%GOODQ_DEV_PYTHON%" (
    echo [BLOCKED] Could not find the private %GOODQ_CONDA_ENV% CPython interpreter.
    goto :failed
)
"%GOODQ_DEV_PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 10) else 1)"
if errorlevel 1 (
    echo [BLOCKED] goodq_core is not the CPython 3.10 installer target.
    goto :failed
)

if "%GOODQ_RELEASE_OUTPUT_ROOT%"=="" (
    echo [BLOCKED] Missing release output. Set GOODQ_RELEASE_OUTPUT_ROOT to an external unused directory.
    goto :failed
)
if "%GOODQ_PREBUILD_RECEIPT%"=="" (
    echo [BLOCKED] Missing terminal prebuild evidence. Set GOODQ_PREBUILD_RECEIPT.
    goto :failed
)
if not exist "%GOODQ_PREBUILD_RECEIPT%" (
    echo [BLOCKED] Prebuild readiness receipt is unavailable: %GOODQ_PREBUILD_RECEIPT%
    goto :failed
)
if "%GOODQ_PRIVATE_BUILD_ROOT%"=="" (
    echo [BLOCKED] Missing private compiler/cache root. Set GOODQ_PRIVATE_BUILD_ROOT.
    goto :failed
)
if not exist "%GOODQ_PRIVATE_BUILD_ROOT%" (
    echo [BLOCKED] Private compiler/cache root is unavailable: %GOODQ_PRIVATE_BUILD_ROOT%
    goto :failed
)
if "%GOODQ_RUNTIME_CONFIG_ROOT%"=="" (
    echo [BLOCKED] Missing active runtime config root. Set GOODQ_RUNTIME_CONFIG_ROOT.
    goto :failed
)
if not exist "%GOODQ_RUNTIME_CONFIG_ROOT%\configs\config.yaml" (
    echo [BLOCKED] Active runtime config root is unavailable: %GOODQ_RUNTIME_CONFIG_ROOT%
    goto :failed
)
if "%GOODQ_ASSET_VAULT_ROOT%"=="" (
    echo [BLOCKED] Missing sealed asset vault. Set GOODQ_ASSET_VAULT_ROOT.
    goto :failed
)
if not exist "%GOODQ_ASSET_VAULT_ROOT%" (
    echo [BLOCKED] Sealed asset vault is unavailable: %GOODQ_ASSET_VAULT_ROOT%
    goto :failed
)
if "%GOODQ_FIXTURE_PACK_ROOT%"=="" (
    echo [BLOCKED] Missing sealed witness pack. Set GOODQ_FIXTURE_PACK_ROOT.
    goto :failed
)
if not exist "%GOODQ_FIXTURE_PACK_ROOT%" (
    echo [BLOCKED] Sealed witness pack is unavailable: %GOODQ_FIXTURE_PACK_ROOT%
    goto :failed
)
if "%GOODQ_WSL_DISTRO%"=="" set "GOODQ_WSL_DISTRO=Ubuntu-22.04"
if /I not "%GOODQ_WSL_DISTRO%"=="Ubuntu-22.04" (
    echo [BLOCKED] v3.0.1 Personal readiness is bound to Ubuntu-22.04.
    goto :failed
)
if "%GOODQ_WSL_AUDIO_WORKSPACE%"=="" (
    echo [BLOCKED] Missing preserved WSL audio workspace. Set GOODQ_WSL_AUDIO_WORKSPACE.
    goto :failed
)
if "%GOODQ_INSTALLER_PROFILE%"=="" (
    echo [BLOCKED] Select PUBLIC_GPU_ENHANCED or PERSONAL_AIR_GAP explicitly.
    goto :failed
)
if /I not "%GOODQ_INSTALLER_PROFILE%"=="PUBLIC_GPU_ENHANCED" if /I not "%GOODQ_INSTALLER_PROFILE%"=="PERSONAL_AIR_GAP" (
    echo [BLOCKED] v3.0.1 readiness authorizes only PUBLIC_GPU_ENHANCED or PERSONAL_AIR_GAP.
    goto :failed
)

for /f "tokens=2 delims== " %%I in ('findstr /b /c:"GOODQ_VERSION =" "%REPO_ROOT%\goodq_version.py"') do set "EXPECTED_VERSION=%%~I"
for /f %%I in ('git -C "%REPO_ROOT%" rev-parse HEAD') do set "EXPECTED_COMMIT=%%I"
for /f %%I in ('git -C "%REPO_ROOT%" rev-parse HEAD:') do set "EXPECTED_TREE=%%I"
if "%EXPECTED_VERSION%"=="" (
    echo [BLOCKED] Could not determine the canonical GoodQ version.
    goto :failed
)
if "%EXPECTED_COMMIT%"=="" (
    echo [BLOCKED] Could not determine the source commit.
    goto :failed
)
if "%EXPECTED_TREE%"=="" (
    echo [BLOCKED] Could not determine the source tree.
    goto :failed
)
if exist "%GOODQ_RELEASE_OUTPUT_ROOT%" (
    for /f "delims=" %%I in ('dir /b /a "%GOODQ_RELEASE_OUTPUT_ROOT%" 2^>nul') do (
        echo [BLOCKED] Release output root is not unused: %GOODQ_RELEASE_OUTPUT_ROOT%
        goto :failed
    )
)
set "GOODQ_PRIVATE_CACHE_ROOT=%GOODQ_PRIVATE_BUILD_ROOT%\staged_cache"

pushd "%BUILD_ROOT%"
echo [1/5] Revalidating the terminal prebuild receipt and every bound input...
"%GOODQ_DEV_PYTHON%" "%REPO_ROOT%\scripts\install\prebuild_readiness.py" verify --receipt "%GOODQ_PREBUILD_RECEIPT%" --repo-root "%REPO_ROOT%" --phase prebuild --runtime-config-root "%GOODQ_RUNTIME_CONFIG_ROOT%" --private-build-root "%GOODQ_PRIVATE_BUILD_ROOT%" --vault-root "%GOODQ_ASSET_VAULT_ROOT%" --fixture-root "%GOODQ_FIXTURE_PACK_ROOT%" --future-output-root "%GOODQ_RELEASE_OUTPUT_ROOT%" --wsl-distro "%GOODQ_WSL_DISTRO%" --wsl-workspace "%GOODQ_WSL_AUDIO_WORKSPACE%"
if errorlevel 1 (
    echo [BLOCKED] The prebuild readiness receipt is stale or incomplete. No output was created.
    popd
    goto :failed
)

echo [2/5] Verifying installer semantic compatibility before opening output...
"%GOODQ_DEV_PYTHON%" "%REPO_ROOT%\scripts\install\verify_installer_semantic_contract.py" --check --repo-root "%REPO_ROOT%"
if errorlevel 1 (
    echo [BLOCKED] Installer components are semantically incompatible. No output was created.
    popd
    goto :failed
)

echo [3/5] Checking physical network containment before opening the output root...
powershell -NoProfile -ExecutionPolicy Bypass -File .\preflight_check.ps1
if errorlevel 1 (
    echo [BLOCKED] Offline containment did not pass. No output was created.
    popd
    goto :failed
)

if not exist "%GOODQ_RELEASE_OUTPUT_ROOT%" mkdir "%GOODQ_RELEASE_OUTPUT_ROOT%"
set "ASSET_ROOT=%GOODQ_RELEASE_OUTPUT_ROOT%\assets"
set "GOODQ_INSTALLER_STAGING_ROOT=%GOODQ_RELEASE_OUTPUT_ROOT%\staging"
mkdir "%ASSET_ROOT%"
if errorlevel 1 (
    echo [BLOCKED] Could not create the external release asset root.
    popd
    goto :failed
)
set "BUILD_LOG=%GOODQ_RELEASE_OUTPUT_ROOT%\offline_build.log"
set "RECEIPT=%GOODQ_RELEASE_OUTPUT_ROOT%\offline_build_receipt.txt"

echo [4/5] Building the %GOODQ_INSTALLER_PROFILE% installer from receipt-bound inputs...
set "GOODQ_INSTALLER_BUILD_ROOT=%BUILD_ROOT%"
set "GOODQ_INSTALLER_OUTPUT_ROOT=%ASSET_ROOT%"
call .\build_installer.bat > "%BUILD_LOG%" 2>&1
if errorlevel 1 (
    echo [FAILED] Build stopped. See:
    echo          %BUILD_LOG%
    popd
    goto :failed
)

echo [5/5] Verifying the exact release asset receipt...
powershell -NoProfile -ExecutionPolicy Bypass -File .\verify_release_asset.ps1 -AssetRoot "%ASSET_ROOT%" -ExpectedVersion "%EXPECTED_VERSION%" -ExpectedCommit "%EXPECTED_COMMIT%" -ExpectedTree "%EXPECTED_TREE%" -ExpectedProfile "%GOODQ_INSTALLER_PROFILE%" -PrebuildReceipt "%GOODQ_PREBUILD_RECEIPT%" > "%RECEIPT%" 2>&1
if errorlevel 1 (
    echo [FAILED] Asset verification did not pass. See:
    echo          %RECEIPT%
    popd
    goto :failed
)
popd

echo.
echo [READY] Offline GPU installer build and verification passed.
echo         Assets are in: %ASSET_ROOT%
echo         Receipt and log are in: %GOODQ_RELEASE_OUTPUT_ROOT%
echo.
echo You may reconnect to the internet now, then return to Codex for review.
if "%GOODQ_AUTO_NETWORK_TOGGLE%"=="1" exit /b 0
pause
exit /b 0

:failed
echo.
echo The release build did not complete. Preserve any created output as failure evidence.
if "%GOODQ_AUTO_NETWORK_TOGGLE%"=="1" exit /b 1
pause
exit /b 1
