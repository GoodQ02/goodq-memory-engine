@echo off
setlocal enabledelayedexpansion
title GoodQ4All Hardened Offline Installer Compiler

echo ==============================================
echo GoodQ4All Offline Installer Compilation Runner
echo ==============================================

if "%GOODQ_INSTALLER_BUILD_ROOT%"=="" (
    echo [ERROR] Missing private build input: GOODQ_INSTALLER_BUILD_ROOT.
    exit /b 20
)
if "%GOODQ_INSTALLER_OUTPUT_ROOT%"=="" (
    echo [ERROR] Missing release output: GOODQ_INSTALLER_OUTPUT_ROOT.
    exit /b 21
)
for %%I in ("%GOODQ_INSTALLER_BUILD_ROOT%") do set "BUILD_ROOT=%%~fI"
for %%I in ("%GOODQ_INSTALLER_OUTPUT_ROOT%") do set "OUTPUT_ROOT=%%~fI"
for %%F in ("go_compiler\go\bin\go.exe" "nsis_compiler\nsis-3.09\makensis.exe" "staged_cache" "dev_private_key.hex") do (
    if not exist "%BUILD_ROOT%\%%~F" (
        echo [ERROR] Missing private build input: %BUILD_ROOT%\%%~F
        exit /b 22
    )
)
if not exist "%OUTPUT_ROOT%" mkdir "%OUTPUT_ROOT%"
cd /d "%BUILD_ROOT%"

:: Resolve PowerShell command (pwsh preferred, fallback to powershell)
where pwsh >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PS_CMD=pwsh"
) else (
    set "PS_CMD=powershell"
)

:: 1. Enforce strict offline environment variables
set PIP_NO_INDEX=1
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
set HF_DATASETS_OFFLINE=1
set GOODQ_OFFLINE_BUILD=1
set NETWORK_POLICY=blocked

:: 2. Preflight Check: Run Poison Scan and Script Verification via PowerShell
echo Running pre-build security audits and network blocks...
%PS_CMD% -NoProfile -ExecutionPolicy Bypass -File preflight_check.ps1

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Pre-build security audits failed. Code: %ERRORLEVEL%
    exit /b 1
)

:: 3. Run stage_dependencies.ps1 in Verify and Audit modes
if "%GOODQ_INSTALLER_PROFILE%"=="" set "GOODQ_INSTALLER_PROFILE=PUBLIC_CPU_BASELINE"
if /I not "%GOODQ_INSTALLER_PROFILE%"=="PUBLIC_CPU_BASELINE" if /I not "%GOODQ_INSTALLER_PROFILE%"=="PUBLIC_GPU_ENHANCED" if /I not "%GOODQ_INSTALLER_PROFILE%"=="PERSONAL_AIR_GAP" (
    echo [ERROR] Unknown installer profile: %GOODQ_INSTALLER_PROFILE%
    exit /b 30
)
set "GOODQ_REQUIREMENTS_LOCK=..\..\requirements-baseline-lock.txt"
if /I "%GOODQ_INSTALLER_PROFILE%"=="PUBLIC_GPU_ENHANCED" set "GOODQ_REQUIREMENTS_LOCK=..\..\requirements-gpu-enhanced-lock.txt"
if /I "%GOODQ_INSTALLER_PROFILE%"=="PERSONAL_AIR_GAP" set "GOODQ_REQUIREMENTS_LOCK=..\..\requirements-gpu-enhanced-lock.txt"
set "GOODQ_WHEEL_CACHE_DIR=staged_cache\wheels\%GOODQ_INSTALLER_PROFILE%"
if not exist "%GOODQ_REQUIREMENTS_LOCK%" (
    echo [ERROR] Selected profile requirements lock is missing: %GOODQ_REQUIREMENTS_LOCK%
    exit /b 35
)
echo Running offline cache checksum verification...
%PS_CMD% -NoProfile -ExecutionPolicy Bypass -File stage_dependencies.ps1 -Mode Verify -Profile "%GOODQ_INSTALLER_PROFILE%"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Staging verification failed. Cache files are missing or corrupt.
    exit /b 2
)

echo Running offline licensing compliance audit...
%PS_CMD% -NoProfile -ExecutionPolicy Bypass -File stage_dependencies.ps1 -Mode Audit -Profile "%GOODQ_INSTALLER_PROFILE%"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Staging licensing audit failed. Non-permissive files found.
    exit /b 3
)
if "%GOODQ_ASSET_VAULT_ROOT%"=="" (
    echo [ERROR] Missing sealed asset vault: set GOODQ_ASSET_VAULT_ROOT before building.
    exit /b 26
)
if not exist "%GOODQ_ASSET_VAULT_ROOT%" (
    echo [ERROR] Sealed asset vault does not exist: %GOODQ_ASSET_VAULT_ROOT%
    exit /b 27
)
if "%GOODQ_DEV_PYTHON%"=="" (
    echo [ERROR] Missing CPython staging interpreter: GOODQ_DEV_PYTHON.
    exit /b 28
)
echo Validating installer profile: %GOODQ_INSTALLER_PROFILE%
"%GOODQ_DEV_PYTHON%" ..\..\scripts\install\build_capability_matrix.py --check --profile "%GOODQ_INSTALLER_PROFILE%"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Installer profile contract validation failed.
    exit /b 31
)

:: Create a fresh private staging tree before signing. The tracked source
:: manifest and signature remain untouched throughout the release build.
if exist "staged" rmdir /s /q "staged"
if errorlevel 1 (
    echo [ERROR] Failed to clear the previous staging directory.
    exit /b 24
)
mkdir "staged\configs"
copy /y "..\..\configs\model_download_manifest.json" "staged\configs\model_download_manifest.json" >nul
if errorlevel 1 (
    echo [ERROR] Failed to stage the model download manifest.
    exit /b 25
)
> "staged\configs\installer_profile.txt" echo %GOODQ_INSTALLER_PROFILE%

:: Stage every profile-selected model from immutable source snapshots directly
:: into the runtime cache layout consumed by model_provisioner.
echo Staging sealed profile capability payloads...
"%GOODQ_DEV_PYTHON%" ..\..\scripts\install\stage_profile_model_packs.py --vault-root "%GOODQ_ASSET_VAULT_ROOT%" --staging-root "staged\models" --profile "%GOODQ_INSTALLER_PROFILE%"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Profile capability pack staging failed.
    exit /b 29
)
copy /y "staged\models\selected_capabilities.json" "staged\configs\selected_capabilities.json" >nul
if errorlevel 1 (
    echo [ERROR] Failed to stage the selected capability receipt.
    exit /b 32
)

:: 3a. Sign manifest in release mode (verifies key matches launcher, signs, round-trip verifies)
echo Signing model download manifest with release key...
go_compiler\go\bin\go.exe run sign_manifest.go --mode release --manifest-path staged\configs\model_download_manifest.json --signature-path staged\configs\model_download_manifest.json.sig
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Manifest signing failed. Key mismatch or signing error.
    exit /b 10
)

:: 3b. Independent verify-only gate (reads back the written signature and verifies)
echo Verifying manifest signature independently...
go_compiler\go\bin\go.exe run sign_manifest.go --verify-only --manifest-path staged\configs\model_download_manifest.json --signature-path staged\configs\model_download_manifest.json.sig
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Independent signature verification failed. Do not package.
    exit /b 11
)

echo Signing selected capability receipt with release key...
go_compiler\go\bin\go.exe run sign_manifest.go --mode release --manifest-path staged\configs\selected_capabilities.json --signature-path staged\configs\selected_capabilities.json.sig
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Capability receipt signing failed.
    exit /b 33
)
go_compiler\go\bin\go.exe run sign_manifest.go --verify-only --manifest-path staged\configs\selected_capabilities.json --signature-path staged\configs\selected_capabilities.json.sig
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Capability receipt signature verification failed.
    exit /b 34
)

:: 4a. Sync versioninfo.json and goodq4all_installer.nsi from canonical goodq_version.py
echo Syncing installer version and metadata...
python sync_nsi_version.py
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Version synchronization failed. Aborting build.
    exit /b 12
)

:: 4b. Compile Supervising Launcher LAUNCH_GOODQ.go
echo Compiling LAUNCH_GOODQ.exe supervisor offline...
go_compiler\go\bin\go.exe build -o "%OUTPUT_ROOT%\LAUNCH_GOODQ.exe" LAUNCH_GOODQ.go launcher_windows.go
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to compile Go launcher.
    exit /b 4
)
echo [OK] Supervising Go Launcher compiled successfully.

:: 5. Copy and Stage Checked-out Binaries from Local Cache
echo Extracting and staging components from verified cache...
if not exist "staged\qdrant" mkdir "staged\qdrant"
if not exist "staged\qdrant\config" mkdir "staged\qdrant\config"
if not exist "staged\nssm" mkdir "staged\nssm"
if not exist "staged\runtime" mkdir "staged\runtime"
if not exist "staged\ffmpeg" mkdir "staged\ffmpeg"
if not exist "staged\poppler" mkdir "staged\poppler"
if not exist "staged\binaries" mkdir "staged\binaries"
if exist "staged\wheels" rmdir /s /q "staged\wheels"
if exist "staged\wheels" (
    echo [ERROR] Could not clear stale staged wheelhouse.
    exit /b 9
)
mkdir "staged\wheels"

:: Copy from staged_cache to staging folder
copy /y "staged_cache\runtime\python-3.10-embed-amd64.zip" "staged\python-3.10-embed-amd64.zip" >nul
%PS_CMD% -NoProfile -Command "Expand-Archive -Path 'staged\python-3.10-embed-amd64.zip' -DestinationPath 'staged\runtime' -Force"

(
echo python310.zip
echo .
echo ..
echo Lib\site-packages
echo ..\vendor
echo import site
) > staged\runtime\python310._pth

echo Bootstrapping pip in staged runtime folder...
copy /y "staged_cache\build_tools\get-pip.py" "staged\get-pip.py" >nul
staged\runtime\python.exe staged\get-pip.py --no-warn-script-location --no-index --find-links=%GOODQ_WHEEL_CACHE_DIR%
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to bootstrap pip in staged runtime.
    exit /b 98
)
del staged\get-pip.py

copy /y "staged_cache\db\qdrant.zip" "staged\qdrant.zip" >nul
%PS_CMD% -NoProfile -Command "Expand-Archive -Path 'staged\qdrant.zip' -DestinationPath 'staged\qdrant' -Force"

copy /y "staged_cache\external\ffmpeg-n8.1.2-34-g9b6c8969e0-win64-lgpl-shared-8.1.zip" "staged\ffmpeg.zip" >nul
if errorlevel 1 (
    echo [ERROR] FFmpeg archive is missing from the verified cache.
    exit /b 103
)
%PS_CMD% -NoProfile -Command "Expand-Archive -Path 'staged\ffmpeg.zip' -DestinationPath 'staged\ffmpeg_archive' -Force"
if errorlevel 1 (
    echo [ERROR] Failed to extract the verified FFmpeg archive.
    exit /b 104
)
xcopy /s /e /i /y "staged\ffmpeg_archive\ffmpeg-n8.1.2-34-g9b6c8969e0-win64-lgpl-shared-8.1\bin" "staged\ffmpeg" >nul
copy /y "staged\ffmpeg_archive\ffmpeg-n8.1.2-34-g9b6c8969e0-win64-lgpl-shared-8.1\LICENSE.txt" "staged\ffmpeg\LICENSE.txt" >nul
(
echo FFmpeg source and build information
echo https://github.com/BtbN/FFmpeg-Builds/releases/tag/autobuild-2026-08-03-14-02
echo https://github.com/FFmpeg/FFmpeg
) > "staged\ffmpeg\SOURCE_URL.txt"
if not exist "staged\ffmpeg\ffmpeg.exe" (
    echo [ERROR] FFmpeg executable was not produced by the verified archive.
    exit /b 105
)
if not exist "staged\ffmpeg\ffprobe.exe" (
    echo [ERROR] FFprobe executable was not produced by the verified archive.
    exit /b 106
)
staged\ffmpeg\ffmpeg.exe -version >nul
if errorlevel 1 (
    echo [ERROR] Staged FFmpeg runtime could not execute.
    exit /b 107
)
staged\ffmpeg\ffprobe.exe -version >nul
if errorlevel 1 (
    echo [ERROR] Staged FFprobe runtime could not execute.
    exit /b 108
)

copy /y "staged_cache\external\poppler.zip" "staged\poppler.zip" >nul
if errorlevel 1 (
    echo [ERROR] Poppler archive is missing from the verified cache.
    exit /b 109
)
%PS_CMD% -NoProfile -Command "Expand-Archive -Path 'staged\poppler.zip' -DestinationPath 'staged\poppler_archive' -Force"
if errorlevel 1 (
    echo [ERROR] Failed to extract the verified Poppler archive.
    exit /b 110
)
xcopy /s /e /i /y "staged\poppler_archive\poppler-24.08.0\Library\bin" "staged\poppler" >nul
if not exist "staged\poppler\pdftotext.exe" (
    echo [ERROR] Poppler pdftotext executable was not produced by the verified archive.
    exit /b 111
)
staged\poppler\pdftotext.exe -v >nul
if errorlevel 1 (
    echo [ERROR] Staged Poppler pdftotext runtime could not execute.
    exit /b 112
)

copy /y "staged_cache\host_tools\nssm.zip" "staged\nssm.zip" >nul
if errorlevel 1 (
    echo [ERROR] NSSM archive is missing from the verified cache.
    exit /b 100
)
%PS_CMD% -NoProfile -Command "Expand-Archive -Path 'staged\nssm.zip' -DestinationPath 'staged\nssm_bin' -Force"
if errorlevel 1 (
    echo [ERROR] Failed to extract the verified NSSM archive.
    exit /b 101
)
copy /y staged\nssm_bin\nssm-2.24-103-gdee49fc\win64\nssm.exe staged\nssm\nssm.exe >nul
if errorlevel 1 (
    echo [ERROR] NSSM executable was not produced by the verified archive.
    exit /b 102
)

copy /y "staged_cache\prerequisites\vc_redist.x64.exe" "staged\binaries\vc_redist.x64.exe" >nul
copy /y "staged_cache\external\tesseract_setup.exe" "staged\binaries\tesseract_setup.exe" >nul

:: Copy certifi CA bundle from verified staged_cache
echo Staging certifi CA bundle from verified cache...
if not exist "staged_cache\runtime\cacert.pem" (
    echo [ERROR] cacert.pem missing from staged_cache! Run stage_dependencies.ps1 -Mode Acquire first.
    exit /b 8
)
if not exist "staged\vendor\certifi" mkdir "staged\vendor\certifi"
copy /y "staged_cache\runtime\cacert.pem" "staged\vendor\certifi\cacert.pem" >nul

:: Copy only the selected profile's sealed wheel closure.
xcopy /s /e /y "%GOODQ_WHEEL_CACHE_DIR%" "staged\wheels" >nul
copy /y "%GOODQ_REQUIREMENTS_LOCK%" "staged\requirements-lock.txt" >nul
if errorlevel 1 (
    echo [ERROR] Failed to stage the selected profile requirements lock.
    exit /b 117
)

:: Seal the exact wheel closure before any installer payload is compiled.
:: The SBOM rejects duplicate packages, unlocked direct requirements, and
:: wheels without license evidence.
echo Sealing strict wheelhouse SBOM...
staged\runtime\python.exe ..\..\scripts\install\generate_wheelhouse_sbom.py --wheelhouse "staged\wheels" --requirements "%GOODQ_REQUIREMENTS_LOCK%" --output "staged\wheelhouse-sbom.json"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Strict wheelhouse SBOM gate failed. Resolve staged dependency evidence before rebuilding.
    exit /b 98
)


:: Stage Qdrant Config
(
echo log_level: INFO
echo telemetry_disabled: true
echo storage:
echo   storage_path: C:\ProgramData\GoodQ4All\qdrant\storage
echo service:
echo   host: 127.0.0.1
echo   http_port: 6333
) > staged\qdrant\config\qdrant_config.yaml

:: Stage Offline Swagger/ReDoc
if not exist "..\..\ui\docs_offline" mkdir "..\..\ui\docs_offline"
copy /y "..\..\branding\favicon.ico" "..\..\ui\docs_offline\favicon.ico" >nul

:: Copy staged vendor directory
xcopy /s /e /i /y "..\..\vendor" "staged\vendor" >nul

echo Verifying offline wheels integrity...
staged\runtime\python.exe -m pip install --dry-run --no-index --find-links="staged\wheels" -r "%GOODQ_REQUIREMENTS_LOCK%"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Offline wheelhouse verification failed. Missing dependencies detected.
    exit /b 99
)

:: 6. Materialize bounded external payload packs.  Complete offline profiles
:: exceed NSIS's embedded data-block limit, so the bootstrap remains small and
:: every large payload is signed and kept beside Setup.exe.
for /f "tokens=2 delims== " %%I in ('findstr /b /c:"GOODQ_VERSION =" "..\..\goodq_version.py"') do set "GOODQ_PRODUCT_VERSION=%%~I"
if "%GOODQ_PRODUCT_VERSION%"=="" (
    echo [ERROR] Could not resolve canonical product version for payload packs.
    exit /b 113
)
echo Building bounded signed offline payload packs...
"%GOODQ_DEV_PYTHON%" ..\..\scripts\install\release_payload_packs.py build --staging-root "staged" --output-root "%OUTPUT_ROOT%" --version "%GOODQ_PRODUCT_VERSION%" --profile "%GOODQ_INSTALLER_PROFILE%"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Bounded payload pack build failed.
    exit /b 114
)
set "GOODQ_PAYLOAD_MANIFEST=%OUTPUT_ROOT%\GoodQ4All_Setup_%GOODQ_PRODUCT_VERSION%.payload_manifest.json"
set "GOODQ_PAYLOAD_SIGNATURE=%GOODQ_PAYLOAD_MANIFEST%.sig"
go_compiler\go\bin\go.exe run sign_manifest.go --mode release --manifest-path "%GOODQ_PAYLOAD_MANIFEST%" --signature-path "%GOODQ_PAYLOAD_SIGNATURE%"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Payload manifest signing failed.
    exit /b 115
)
go_compiler\go\bin\go.exe run sign_manifest.go --verify-only --manifest-path "%GOODQ_PAYLOAD_MANIFEST%" --signature-path "%GOODQ_PAYLOAD_SIGNATURE%"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Payload manifest signature verification failed.
    exit /b 116
)

:: 7. Compile NSIS Setup Package Offline
echo Compiling final NSIS Setup Installer package...
nsis_compiler\nsis-3.09\makensis.exe /DGOODQ_INSTALLER_OUTPUT_ROOT="%OUTPUT_ROOT%" /DGOODQ_LAUNCHER_PATH="%OUTPUT_ROOT%\LAUNCH_GOODQ.exe" /DGOODQ_INSTALLER_PROFILE="%GOODQ_INSTALLER_PROFILE%" goodq4all_installer.nsi
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to compile NSIS installer.
    exit /b 5
)

:: 8. Write Release Manifest
echo Generating release manifest and signatures...
%PS_CMD% -NoProfile -ExecutionPolicy Bypass -File generate_manifest.ps1 -AssetRoot "%OUTPUT_ROOT%" -Profile "%GOODQ_INSTALLER_PROFILE%"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Release manifest generation failed.
    exit /b 23
)

echo ==============================================
echo [OK] Installer compilation successfully complete.
echo Output assets staged at %OUTPUT_ROOT%.
echo ==============================================
echo Done.
