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
echo Running offline cache checksum verification...
%PS_CMD% -NoProfile -ExecutionPolicy Bypass -File stage_dependencies.ps1 -Mode Verify
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Staging verification failed. Cache files are missing or corrupt.
    exit /b 2
)

echo Running offline licensing compliance audit...
%PS_CMD% -NoProfile -ExecutionPolicy Bypass -File stage_dependencies.ps1 -Mode Audit
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Staging licensing audit failed. Non-permissive files found.
    exit /b 3
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
if not exist "staged\binaries" mkdir "staged\binaries"
if not exist "staged\wheels" mkdir "staged\wheels"

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
staged\runtime\python.exe staged\get-pip.py --no-warn-script-location --no-index --find-links=staged_cache\wheels
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to bootstrap pip in staged runtime.
    exit /b 98
)
del staged\get-pip.py

copy /y "staged_cache\db\qdrant.zip" "staged\qdrant.zip" >nul
%PS_CMD% -NoProfile -Command "Expand-Archive -Path 'staged\qdrant.zip' -DestinationPath 'staged\qdrant' -Force"

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

:: Copy wheels for the CPU-safe baseline. WSL audio remains an optional upgrade.
xcopy /s /e /y "staged_cache\wheels" "staged\wheels" >nul


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
staged\runtime\python.exe -m pip install --dry-run --no-index --find-links="staged\wheels" -r ..\..\requirements-baseline-lock.txt
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Offline wheelhouse verification failed. Missing dependencies detected.
    exit /b 99
)

:: 6. Compile NSIS Setup Package Offline
echo Compiling final NSIS Setup Installer package...
nsis_compiler\nsis-3.09\makensis.exe /DGOODQ_INSTALLER_OUTPUT_ROOT="%OUTPUT_ROOT%" /DGOODQ_LAUNCHER_PATH="%OUTPUT_ROOT%\LAUNCH_GOODQ.exe" goodq4all_installer.nsi
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to compile NSIS installer.
    exit /b 5
)

:: 7. Write Release Manifest
echo Generating release manifest and signatures...
%PS_CMD% -NoProfile -ExecutionPolicy Bypass -File generate_manifest.ps1 -AssetRoot "%OUTPUT_ROOT%"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Release manifest generation failed.
    exit /b 23
)

echo ==============================================
echo [OK] Installer compilation successfully complete.
echo Output assets staged at %OUTPUT_ROOT%.
echo ==============================================
echo Done.
