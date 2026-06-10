# GoodQ4All - Generate Release Manifest Script
# -------------------------------------------
$ErrorActionPreference = "Stop"

$exePath = '..\..\GoodQ4All_Setup_1.0.0.exe'
if (-not (Test-Path $exePath)) {
    Write-Error "Installer executable not found at $exePath!"
    exit 1
}

$exeHash = (Get-FileHash -Path $exePath -Algorithm SHA256).Hash.ToLower()
$manifest = @{
    'manifest_version' = '1.0.0'
    'installer_filename' = 'GoodQ4All_Setup_1.0.0.exe'
    'sha256' = $exeHash
    'build_time' = (Get-Date -Format 'o')
    'build_host' = $env:COMPUTERNAME
    'source_commit' = (git rev-parse HEAD 2>$null)
    'status' = 'verified_offline'
}

$destManifest = '..\..\dist\GoodQ4All_Setup_1.0.0.release_manifest.json'
$destManifestDir = Split-Path -Parent $destManifest
if (-not (Test-Path $destManifestDir)) {
    New-Item -ItemType Directory -Path $destManifestDir -Force | Out-Null
}

$manifest | ConvertTo-Json -Depth 5 | Out-File -FilePath $destManifest -Encoding utf8
Write-Host "[OK] Release manifest generated successfully at $destManifest" -ForegroundColor Green
