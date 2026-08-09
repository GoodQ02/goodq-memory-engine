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
$manifestPath = Join-Path $assetRoot $manifestName
$checksumPath = Join-Path $assetRoot $checksumName
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw "Release manifest is missing: $manifestName" }
if (-not (Test-Path -LiteralPath $checksumPath -PathType Leaf)) { throw "Release checksum is missing: $checksumName" }
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
if ($manifest.product_version -ne $ExpectedVersion) { throw "Manifest version does not match $ExpectedVersion" }
if ($ExpectedCommit -and $manifest.source_commit -ne $ExpectedCommit) { throw "Manifest commit does not match $ExpectedCommit" }
if (-not $manifest.source_tree_clean) { throw "Manifest does not prove a clean source tree" }
if ($manifest.profile -ne $ExpectedProfile) { throw "Manifest profile is not $ExpectedProfile" }
if (-not (@($manifest.excluded_optional_components) -contains "wsl_audio")) { throw "Manifest must exclude WSL audio" }
if (-not (@($manifest.excluded_optional_components) -contains "local_llm_serving")) { throw "Manifest must exclude local LLM serving" }
if ($ExpectedProfile -eq "PUBLIC_CPU_BASELINE" -and -not (@($manifest.excluded_optional_components) -contains "gpu_enhanced")) { throw "CPU baseline manifest must exclude GPU enhanced mode" }

$payloadManifestName = [string]$manifest.payload_manifest_filename
$payloadSignatureName = [string]$manifest.payload_manifest_signature_filename
$payloadPacks = @($manifest.payload_packs)
if ([string]::IsNullOrWhiteSpace($payloadManifestName) -or [string]::IsNullOrWhiteSpace($payloadSignatureName) -or $payloadPacks.Count -lt 1) {
    throw "Release manifest must declare a signed external payload pack set"
}
$payloadManifestPath = Join-Path $assetRoot $payloadManifestName
$payloadSignaturePath = Join-Path $assetRoot $payloadSignatureName
if (-not (Test-Path -LiteralPath $payloadManifestPath -PathType Leaf)) { throw "Payload manifest is missing" }
if (-not (Test-Path -LiteralPath $payloadSignaturePath -PathType Leaf)) { throw "Payload manifest signature is missing" }
if ((Get-Sha256Hex $payloadManifestPath) -ne ([string]$manifest.payload_manifest_sha256).ToLower()) { throw "Payload manifest SHA256 does not match release manifest" }
if ((Get-Sha256Hex $payloadSignaturePath) -ne ([string]$manifest.payload_manifest_signature_sha256).ToLower()) { throw "Payload manifest signature SHA256 does not match release manifest" }
foreach ($pack in $payloadPacks) {
    $relative = [string]$pack.path
    if ([string]::IsNullOrWhiteSpace($relative) -or [IO.Path]::IsPathRooted($relative) -or $relative -match '(^|[\\/])\.\.([\\/]|$)') {
        throw "Release manifest contains an unsafe payload pack path: $relative"
    }
    $packPath = Join-Path $assetRoot $relative
    if (-not (Test-Path -LiteralPath $packPath -PathType Leaf)) { throw "Payload pack is missing: $relative" }
    if ((Get-Item -LiteralPath $packPath).Length -ne [int64]$pack.size_bytes) { throw "Payload pack size does not match release manifest: $relative" }
    if ((Get-Sha256Hex $packPath) -ne ([string]$pack.sha256).ToLower()) { throw "Payload pack SHA256 does not match release manifest: $relative" }
}

$expectedNames = @($installerName, "LAUNCH_GOODQ.exe", $manifestName, $checksumName, $payloadManifestName, $payloadSignatureName) + @($payloadPacks | ForEach-Object { [string]$_.path }) | Sort-Object
$actualNames = @(Get-ChildItem -File -Recurse $assetRoot | ForEach-Object {
    $_.FullName.Substring($assetRoot.Length).TrimStart([char[]]'\\').Replace('\', '/')
} | Sort-Object)
if (Compare-Object -ReferenceObject $expectedNames -DifferenceObject $actualNames) {
    throw "Release asset set must contain exactly the bootstrap, signed payload manifest, and declared payload packs"
}

$installerHash = Get-Sha256Hex (Join-Path $assetRoot $installerName)
$launcherHash = Get-Sha256Hex (Join-Path $assetRoot "LAUNCH_GOODQ.exe")
if ($manifest.sha256 -ne $installerHash) { throw "Installer SHA256 does not match manifest" }
if ($manifest.launcher_sha256 -ne $launcherHash) { throw "Launcher SHA256 does not match manifest" }
$expectedChecksumLines = @(Get-ChildItem -LiteralPath $assetRoot -File -Recurse |
    Where-Object { $_.FullName -ne (Join-Path $assetRoot $checksumName) } |
    ForEach-Object {
        $relativePath = $_.FullName.Substring($assetRoot.Length).TrimStart([char[]]'\\').Replace('\', '/')
        "$(Get-Sha256Hex $_.FullName) *$relativePath"
    } | Sort-Object)
$actualChecksumLines = @(Get-Content (Join-Path $assetRoot $checksumName) |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ } |
    Sort-Object)
if (Compare-Object -ReferenceObject $expectedChecksumLines -DifferenceObject $actualChecksumLines) {
    throw "Checksum file must contain exactly every declared release asset hash"
}
$serializedManifest = Get-Content $manifestPath -Raw
$normalizedManifest = $serializedManifest.Replace('\\', '\').Replace('/', '\').ToLowerInvariant()
foreach ($privateToken in @('c:\users\', 'l:\', 'onedrive', 'goodcube', 'goodq_data')) {
    if ($normalizedManifest.Contains($privateToken)) {
        throw "Manifest contains private token $privateToken"
    }
}
[pscustomobject]@{ pass = $true; version = $ExpectedVersion; source_commit = $manifest.source_commit; assets = $actualNames } | ConvertTo-Json -Depth 3
