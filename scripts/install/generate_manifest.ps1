param(
    [Parameter(Mandatory = $true)]
    [string]$AssetRoot,
    [string]$ExpectedVersion
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$assetRoot = [System.IO.Path]::GetFullPath($AssetRoot)
$versionPath = Join-Path $repoRoot "goodq_version.py"
$versionLine = Get-Content $versionPath | Where-Object { $_ -match 'GOODQ_VERSION\s*=' }
if ($versionLine -notmatch '"([^"]+)"') {
    throw "Could not resolve GOODQ_VERSION from $versionPath"
}
$productVersion = $Matches[1]
if ($ExpectedVersion -and $ExpectedVersion -ne $productVersion) {
    throw "Expected version $ExpectedVersion does not match canonical version $productVersion"
}

$installerName = "GoodQ4All_Setup_$productVersion.exe"
$installerPath = Join-Path $assetRoot $installerName
$launcherPath = Join-Path $assetRoot "LAUNCH_GOODQ.exe"
if (-not (Test-Path $installerPath)) { throw "Installer executable not found at $installerPath" }
if (-not (Test-Path $launcherPath)) { throw "Launcher executable not found at $launcherPath" }

$sourceCommit = (git -C $repoRoot rev-parse HEAD).Trim()
$dirtyFiles = git -C $repoRoot status --porcelain
if (-not [string]::IsNullOrWhiteSpace($dirtyFiles)) {
    throw "Refusing to generate a release manifest from a dirty source tree."
}

$manifest = [ordered]@{
    manifest_version = "1.0.0"
    installer_filename = $installerName
    sha256 = (Get-FileHash -Path $installerPath -Algorithm SHA256).Hash.ToLower()
    launcher_filename = "LAUNCH_GOODQ.exe"
    launcher_sha256 = (Get-FileHash -Path $launcherPath -Algorithm SHA256).Hash.ToLower()
    product_version = $productVersion
    source_commit = $sourceCommit
    source_tree_clean = $true
    profile = "BASELINE"
    excluded_optional_components = @("wsl_audio", "local_llm_serving", "gpu_enhanced")
    status = "verified_offline"
}
$manifestPath = Join-Path $assetRoot "GoodQ4All_Setup_$productVersion.release_manifest.json"
$manifest | ConvertTo-Json -Depth 5 | Set-Content -Path $manifestPath -Encoding utf8
$checksumPath = Join-Path $assetRoot "GoodQ4All_Setup_$productVersion.sha256"
@(
    "$($manifest.sha256) *$installerName"
    "$($manifest.launcher_sha256) *LAUNCH_GOODQ.exe"
    "$((Get-FileHash -Path $manifestPath -Algorithm SHA256).Hash.ToLower()) *$(Split-Path -Leaf $manifestPath)"
) | Set-Content -Path $checksumPath -Encoding ascii
Write-Host "[OK] Release manifest and checksums generated in $assetRoot" -ForegroundColor Green
