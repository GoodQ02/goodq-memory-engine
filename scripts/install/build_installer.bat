@echo off
setlocal enabledelayedexpansion
title GoodQ4All Installer Compiler

echo ==============================================
echo GoodQ4All Installer Compilation Runner
echo ==============================================

cd "%~dp0"

:: 1. Load build_toolchain_manifest.json and download dependencies securely via PowerShell
echo Securing and fetching compilers from build_toolchain_manifest.json...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$manifest = Get-Content -Raw -Path '..\..\configs\build_toolchain_manifest.json' | ConvertFrom-Json; foreach ($toolName in $manifest.toolchains.psobject.properties.name) { $tool = $manifest.toolchains.$toolName; $destZip = Join-Path $env:TEMP \"$toolName.zip\"; $destDir = $tool.local_dir; if (-not (Test-Path $destDir)) { Write-Host \"Downloading $toolName from $($tool.url)...\" -ForegroundColor Cyan; Invoke-WebRequest -UserAgent \"Wget\" -UseBasicParsing -Uri $tool.url -OutFile $destZip; $hash = (Get-FileHash -Path $destZip -Algorithm SHA256).Hash.ToLower(); if ($hash -ne $tool.sha256.ToLower()) { Write-Error \"SHA256 checksum mismatch for $toolName (Got: $hash, Expected: $($tool.sha256))\"; exit 1; }; Write-Host \"Extracting $toolName to $destDir...\" -ForegroundColor Green; Expand-Archive -Path $destZip -DestinationPath $destDir -Force; Remove-Item $destZip -ErrorAction SilentlyContinue; } else { Write-Host \"$toolName compiler is already cached.\" -ForegroundColor Yellow; } }"

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to fetch or verify compilers from manifest.
    exit /b 1
)

:: 1a. Sign the model manifest
echo Compiling and running manifest signer...
go_compiler\go\bin\go.exe run sign_manifest.go
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to sign model manifest.
    exit /b 11
)

:: 1b. Embed Version Info & Icon Resource
echo Embedding version metadata and icon into launcher...
if not exist "go_bin\goversioninfo.exe" (
    echo Building goversioninfo compiler helper...
    set GOBIN=%cd%\go_bin
    go_compiler\go\bin\go.exe install github.com/josephspurrier/goversioninfo/cmd/goversioninfo@latest
)
go_bin\goversioninfo.exe
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to compile version resource.
    exit /b 12
)

:: 2. Compile Supervising Launcher LAUNCH_GOODQ.go
echo Compiling LAUNCH_GOODQ.exe supervisor...
if exist "..\..\LAUNCH_GOODQ.exe" del "..\..\LAUNCH_GOODQ.exe"
go_compiler\go\bin\go.exe build -o ..\..\LAUNCH_GOODQ.exe LAUNCH_GOODQ.go
if exist "resource.syso" del "resource.syso"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to compile Go launcher.
    exit /b 2
)
echo [OK] Supervising Go Launcher compiled successfully.

:: 3. Stage Binaries for Installer Bundle
echo Staging embedded Python runtime and DB engines...
if not exist "staged" mkdir "staged"
if not exist "staged\qdrant" mkdir "staged\qdrant"
if not exist "staged\qdrant\config" mkdir "staged\qdrant\config"
if not exist "staged\nssm" mkdir "staged\nssm"
if not exist "staged\runtime" mkdir "staged\runtime"

:: Download embedded Python 3.10.11 if not present
if not exist "staged\python-3.10-embed-amd64.zip" (
    echo Downloading portable Python 3.10.11 zip...
    powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-amd64.zip' -OutFile 'staged\python-3.10-embed-amd64.zip'"
    powershell -NoProfile -Command "Expand-Archive -Path 'staged\python-3.10-embed-amd64.zip' -DestinationPath 'staged\runtime' -Force"
)

:: Ensure python310._pth includes project root and vendor paths
(
echo python310.zip
echo .
echo ..
echo ..\vendor
) > staged\runtime\python310._pth


:: Download Qdrant Windows binary if not present
if not exist "staged\qdrant\qdrant.exe" (
    echo Downloading Qdrant Windows x64 binary...
    powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://github.com/qdrant/qdrant/releases/download/v1.9.0/qdrant-x86_64-pc-windows-msvc.zip' -OutFile 'staged\qdrant.zip'"
    powershell -NoProfile -Command "Expand-Archive -Path 'staged\qdrant.zip' -DestinationPath 'staged\qdrant' -Force"
    del staged\qdrant.zip
)

:: Stage Qdrant Config
if not exist "staged\qdrant\config\qdrant_config.yaml" (
    (
    echo log_level: INFO
    echo telemetry_disabled: true
    echo storage:
    echo   storage_path: C:\ProgramData\GoodQ4All\qdrant\storage
    echo service:
    echo   host: 127.0.0.1
    echo   http_port: 6333
    ) > staged\qdrant\config\qdrant_config.yaml
)

:: Copy NSSM binary from toolchain directory
copy /y nssm_bin\nssm-2.24-103-gdee49fc\win64\nssm.exe staged\nssm\nssm.exe >nul

:: 3a. Stage Swagger / ReDoc Offline Documentation assets
echo Staging offline swagger/redoc assets...
if not exist "..\..\ui\docs_offline" mkdir "..\..\ui\docs_offline"
copy /y "..\..\branding\favicon.ico" "..\..\ui\docs_offline\favicon.ico" >nul

powershell -NoProfile -Command "$files = @{'swagger-ui-bundle.js' = 'https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js'; 'swagger-ui.css' = 'https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css'; 'redoc.standalone.js' = 'https://cdn.jsdelivr.net/npm/redoc/bundles/redoc.standalone.js'}; foreach ($name in $files.Keys) { $path = Join-Path '..\..\ui\docs_offline' $name; if (-not (Test-Path $path)) { Write-Host \"Downloading $name to $path...\" -ForegroundColor Cyan; try { Invoke-WebRequest -UserAgent 'Wget' -UseBasicParsing -Uri $files[$name] -OutFile $path -TimeoutSec 15 } catch { Write-Host \"Warning: Failed to download $name. Docs might not render offline. error: $_\" -ForegroundColor Yellow } } else { Write-Host \"$name is already cached offline.\" -ForegroundColor Yellow } }"

:: 4. Compile NSIS setup package
echo Compiling final NSIS Setup Installer package...
nsis_compiler\nsis-3.09\makensis.exe goodq4all_installer.nsi
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to compile NSIS installer.
    exit /b 3
)

echo ==============================================
echo [OK] Installer compilation successfully complete.
echo Output binary staged at: GoodQ4All_Setup_1.0.0.exe
echo ==============================================
echo Done.
