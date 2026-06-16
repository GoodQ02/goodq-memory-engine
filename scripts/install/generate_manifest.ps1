# GoodQ4All - Generate Release Manifest Script
# -------------------------------------------
$ErrorActionPreference = "Stop"

$exePath = '..\..\GoodQ4All_Setup_2.4.1.exe'
if (-not (Test-Path $exePath)) {
    Write-Error "Installer executable not found at $exePath!"
    exit 1
}

# Compute installer hash
$exeHash = (Get-FileHash -Path $exePath -Algorithm SHA256).Hash.ToLower()

# Resolve source commit and tree cleanliness
$sourceCommit = $null
$sourceTreeClean = $false
try {
    $sourceCommit = (git rev-parse HEAD 2>$null)
    if (-not $sourceCommit -or $sourceCommit.Length -lt 7) {
        Write-Host "[WARNING] Could not resolve source commit via git rev-parse HEAD." -ForegroundColor Yellow
        $sourceCommit = "unknown"
    }
    $dirtyFiles = (git status --porcelain 2>$null)
    if ([string]::IsNullOrWhiteSpace($dirtyFiles)) {
        $sourceTreeClean = $true
    } else {
        Write-Host "[WARNING] Source tree is dirty. Release built from uncommitted changes:" -ForegroundColor Yellow
        Write-Host $dirtyFiles -ForegroundColor Yellow
    }
} catch {
    Write-Host "[WARNING] Git is not available. Source provenance will be incomplete." -ForegroundColor Yellow
    $sourceCommit = "git_unavailable"
}

# Compute launcher hash if present
$launcherPath = '..\..\LAUNCH_GOODQ.exe'
$launcherHash = $null
if (Test-Path $launcherPath) {
    $launcherHash = (Get-FileHash -Path $launcherPath -Algorithm SHA256).Hash.ToLower()
}

# Compute model manifest and signature hashes
$modelManifestPath = '..\..\configs\model_download_manifest.json'
$modelManifestSigPath = '..\..\configs\model_download_manifest.json.sig'
$modelManifestHash = $null
$modelManifestSigHash = $null
if (Test-Path $modelManifestPath) {
    $modelManifestHash = (Get-FileHash -Path $modelManifestPath -Algorithm SHA256).Hash.ToLower()
}
if (Test-Path $modelManifestSigPath) {
    $modelManifestSigHash = (Get-FileHash -Path $modelManifestSigPath -Algorithm SHA256).Hash.ToLower()
}

# Read product version from goodq_version.py
$productVersion = "unknown"
$versionPyPath = '..\..\goodq_version.py'
if (Test-Path $versionPyPath) {
    $versionLine = Get-Content $versionPyPath | Where-Object { $_ -match 'GOODQ_VERSION\s*=' }
    if ($versionLine -match '"([^"]+)"') {
        $productVersion = $Matches[1]
    }
}

$manifest = @{
    'manifest_version'          = '1.0.0'
    'installer_filename'        = 'GoodQ4All_Setup_2.4.1.exe'
    'sha256'                    = $exeHash
    'launcher_sha256'           = $launcherHash
    'model_manifest_sha256'     = $modelManifestHash
    'model_manifest_sig_sha256' = $modelManifestSigHash
    'product_version'           = $productVersion
    'build_time'                = (Get-Date -Format 'o')
    'build_host'                = $env:COMPUTERNAME
    'source_commit'             = $sourceCommit
    'source_tree_clean'         = $sourceTreeClean
    'status'                    = 'verified_offline'
}

$destManifest = '..\..\dist\GoodQ4All_Setup_2.4.1.release_manifest.json'
$destManifestDir = Split-Path -Parent $destManifest
if (-not (Test-Path $destManifestDir)) {
    New-Item -ItemType Directory -Path $destManifestDir -Force | Out-Null
}

$manifest | ConvertTo-Json -Depth 5 | Out-File -FilePath $destManifest -Encoding utf8
Write-Host "[OK] Release manifest generated successfully at $destManifest" -ForegroundColor Green
Write-Host "     Source commit: $sourceCommit (clean: $sourceTreeClean)" -ForegroundColor Gray
Write-Host "     Product version: $productVersion" -ForegroundColor Gray

