param(
    [Parameter(Mandatory = $true)]
    [string]$AssetRoot,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedVersion,
    [string]$ExpectedCommit,
    [ValidateSet("PUBLIC_CPU_BASELINE", "PUBLIC_GPU_ENHANCED", "PERSONAL_AIR_GAP")]
    [string]$ExpectedProfile = "PUBLIC_CPU_BASELINE"
)

$ErrorActionPreference = "Stop"

function Get-Sha256Hex([string]$Path) {
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        $sha256 = [System.Security.Cryptography.SHA256]::Create()
        try {
            return ([System.BitConverter]::ToString($sha256.ComputeHash($stream))).Replace("-", "").ToLowerInvariant()
        } finally {
            $sha256.Dispose()
        }
    } finally {
        $stream.Dispose()
    }
}

$assetRoot = [System.IO.Path]::GetFullPath($AssetRoot)
$installerName = "GoodQ4All_Setup_$ExpectedVersion.exe"
$manifestName = "GoodQ4All_Setup_$ExpectedVersion.release_manifest.json"
$checksumName = "GoodQ4All_Setup_$ExpectedVersion.sha256"
$expectedNames = @($installerName, "LAUNCH_GOODQ.exe", $manifestName, $checksumName) | Sort-Object
$actualNames = @(Get-ChildItem -File -Recurse $assetRoot | ForEach-Object {
    $_.FullName.Substring($assetRoot.Length).TrimStart([char[]]'\\')
} | Sort-Object)
if (Compare-Object -ReferenceObject $expectedNames -DifferenceObject $actualNames) {
    throw "Release asset set must contain exactly: $($expectedNames -join ', ')"
}

$manifestPath = Join-Path $assetRoot $manifestName
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
if ($manifest.product_version -ne $ExpectedVersion) { throw "Manifest version does not match $ExpectedVersion" }
if ($ExpectedCommit -and $manifest.source_commit -ne $ExpectedCommit) { throw "Manifest commit does not match $ExpectedCommit" }
if (-not $manifest.source_tree_clean) { throw "Manifest does not prove a clean source tree" }
if ($manifest.profile -ne $ExpectedProfile) { throw "Manifest profile is not $ExpectedProfile" }
if (-not (@($manifest.excluded_optional_components) -contains "wsl_audio")) { throw "Manifest must exclude WSL audio" }
if (-not (@($manifest.excluded_optional_components) -contains "local_llm_serving")) { throw "Manifest must exclude local LLM serving" }
if ($ExpectedProfile -eq "PUBLIC_CPU_BASELINE" -and -not (@($manifest.excluded_optional_components) -contains "gpu_enhanced")) { throw "CPU baseline manifest must exclude GPU enhanced mode" }

$installerHash = Get-Sha256Hex (Join-Path $assetRoot $installerName)
$launcherHash = Get-Sha256Hex (Join-Path $assetRoot "LAUNCH_GOODQ.exe")
if ($manifest.sha256 -ne $installerHash) { throw "Installer SHA256 does not match manifest" }
if ($manifest.launcher_sha256 -ne $launcherHash) { throw "Launcher SHA256 does not match manifest" }
$manifestHash = Get-Sha256Hex $manifestPath
$expectedChecksumLines = @(
    "$installerHash *$installerName",
    "$launcherHash *LAUNCH_GOODQ.exe",
    "$manifestHash *$manifestName"
) | Sort-Object
$actualChecksumLines = @(Get-Content (Join-Path $assetRoot $checksumName) |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ } |
    Sort-Object)
if (Compare-Object -ReferenceObject $expectedChecksumLines -DifferenceObject $actualChecksumLines) {
    throw "Checksum file must contain exactly the installer, launcher, and manifest hashes"
}
$serializedManifest = Get-Content $manifestPath -Raw
$normalizedManifest = $serializedManifest.Replace('\\', '\').Replace('/', '\').ToLowerInvariant()
foreach ($privateToken in @('c:\users\', 'l:\', 'onedrive', 'goodcube', 'goodq_data')) {
    if ($normalizedManifest.Contains($privateToken)) {
        throw "Manifest contains private token $privateToken"
    }
}
[pscustomobject]@{ pass = $true; version = $ExpectedVersion; source_commit = $manifest.source_commit; assets = $actualNames } | ConvertTo-Json -Depth 3
