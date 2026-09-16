param(
    [Parameter(Mandatory = $true)]
    [string]$AssetRoot,
    [Parameter(Mandatory = $true)]
    [string]$PrebuildReceipt,
    [string]$ExpectedVersion,
    [ValidateSet("PUBLIC_CPU_BASELINE", "PUBLIC_GPU_ENHANCED", "PERSONAL_AIR_GAP")]
    [string]$Profile = "PUBLIC_CPU_BASELINE"
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$assetRoot = [System.IO.Path]::GetFullPath($AssetRoot)
$prebuildReceiptPath = [System.IO.Path]::GetFullPath($PrebuildReceipt)
if (-not (Test-Path -LiteralPath $prebuildReceiptPath -PathType Leaf)) {
    throw "Prebuild readiness receipt is missing"
}
try {
    $prebuild = Get-Content -LiteralPath $prebuildReceiptPath -Raw | ConvertFrom-Json
} catch {
    throw "Prebuild readiness receipt is unreadable: $_"
}
if ($prebuild.schema -ne "goodq.prebuild-readiness.v1" -or $prebuild.status -ne "passed") {
    throw "Prebuild readiness receipt is not terminal passing evidence"
}
$prebuildReceiptSha256 = (Get-FileHash -LiteralPath $prebuildReceiptPath -Algorithm SHA256).Hash.ToLower()
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
$payloadManifestName = "GoodQ4All_Setup_$productVersion.payload_manifest.json"
$payloadManifestPath = Join-Path $assetRoot $payloadManifestName
$payloadSignatureName = "$payloadManifestName.sig"
$payloadSignaturePath = Join-Path $assetRoot $payloadSignatureName
if (-not (Test-Path $payloadManifestPath)) { throw "Payload manifest not found at $payloadManifestPath" }
if (-not (Test-Path $payloadSignaturePath)) { throw "Payload manifest signature not found at $payloadSignaturePath" }
try {
    $payloadManifest = Get-Content $payloadManifestPath -Raw | ConvertFrom-Json
    $payloadPacks = @($payloadManifest.packs)
} catch {
    throw "Payload manifest is unreadable: $_"
}
if ($payloadManifest.schema_version -ne 2 -or $payloadManifest.pack_format -ne "zip_stored_zip64" -or $payloadPacks.Count -lt 1) {
    throw "Payload manifest must declare schema version 2, ZIP_STORED ZIP64, and at least one pack"
}
$payloadMembers = @($payloadManifest.members)
if ($payloadMembers.Count -lt 1 -or [int]$payloadManifest.member_count -ne $payloadMembers.Count) {
    throw "Payload manifest schema v2 must bind every archive member"
}
foreach ($digestName in @(
    "member_inventory_sha256",
    "selected_capabilities_sha256",
    "selected_asset_selector_sha256",
    "selected_asset_inventory_sha256",
    "model_member_manifest_sha256",
    "model_member_inventory_sha256"
)) {
    $digest = [string]$payloadManifest.$digestName
    if ($digest -notmatch '^[0-9a-f]{64}$') {
        throw "Payload manifest has an invalid $digestName binding"
    }
}
$payloadPackRecords = @()
foreach ($pack in $payloadPacks) {
    $relativePath = [string]$pack.path
    if ([string]::IsNullOrWhiteSpace($relativePath) -or [IO.Path]::IsPathRooted($relativePath) -or $relativePath -match '(^|[\\/])\.\.([\\/]|$)') {
        throw "Payload manifest contains an unsafe pack path: $relativePath"
    }
    $packPath = Join-Path $assetRoot $relativePath
    if (-not (Test-Path -LiteralPath $packPath -PathType Leaf)) { throw "Payload pack is missing: $relativePath" }
    $actualHash = (Get-FileHash -LiteralPath $packPath -Algorithm SHA256).Hash.ToLower()
    if ($actualHash -ne ([string]$pack.sha256).ToLower()) { throw "Payload pack hash mismatch: $relativePath" }
    if ((Get-Item -LiteralPath $packPath).Length -ne [int64]$pack.size_bytes) { throw "Payload pack size mismatch: $relativePath" }
    $payloadPackRecords += [ordered]@{ path = $relativePath; sha256 = $actualHash; size_bytes = [int64]$pack.size_bytes }
}

$sourceCommit = (git -C $repoRoot rev-parse HEAD).Trim()
$sourceTree = (git -C $repoRoot rev-parse 'HEAD:').Trim()
$dirtyFiles = git -C $repoRoot status --porcelain
if (-not [string]::IsNullOrWhiteSpace($dirtyFiles)) {
    throw "Refusing to generate a release manifest from a dirty source tree."
}
if (
    $prebuild.version -ne $productVersion -or
    $prebuild.source.initial_commit -ne $sourceCommit -or
    $prebuild.source.observed_commit -ne $sourceCommit -or
    $prebuild.source.initial_tree -ne $sourceTree -or
    $prebuild.source.observed_tree -ne $sourceTree
) {
    throw "Source commit/tree/version does not match the prebuild readiness receipt"
}

$excludedComponents = if ($Profile -eq "PUBLIC_CPU_BASELINE") {
    @("wsl_audio", "local_vlm", "local_llm_serving", "gpu_enhanced")
} elseif ($Profile -eq "PUBLIC_GPU_ENHANCED") {
    @("wsl_audio", "local_vlm", "local_llm_serving")
} else {
    @("local_vlm", "local_llm_serving")
}
$componentDispositions = [ordered]@{
    local_vlm = [ordered]@{ status = "policy_excluded" }
    local_llm_serving = [ordered]@{ status = "policy_excluded" }
    wsl_audio = if ($Profile -eq "PERSONAL_AIR_GAP") {
        [ordered]@{
            status = "host_prerequisite"
            distro = "Ubuntu-22.04"
            wsl_version = 2
            packaged = $false
            receipt_phases = @("pre_install", "post_install")
            allowed_warnings = @("torchcodec_unavailable")
        }
    } else {
        [ordered]@{ status = "excluded"; packaged = $false }
    }
}

$manifest = [ordered]@{
    manifest_version = "1.1.0"
    installer_filename = $installerName
    sha256 = (Get-FileHash -Path $installerPath -Algorithm SHA256).Hash.ToLower()
    launcher_filename = "LAUNCH_GOODQ.exe"
    launcher_sha256 = (Get-FileHash -Path $launcherPath -Algorithm SHA256).Hash.ToLower()
    payload_manifest_filename = $payloadManifestName
    payload_manifest_sha256 = (Get-FileHash -Path $payloadManifestPath -Algorithm SHA256).Hash.ToLower()
    payload_manifest_signature_filename = $payloadSignatureName
    payload_manifest_signature_sha256 = (Get-FileHash -Path $payloadSignaturePath -Algorithm SHA256).Hash.ToLower()
    payload_packs = $payloadPackRecords
    product_version = $productVersion
    source_commit = $sourceCommit
    source_tree = $sourceTree
    source_tree_clean = $true
    prebuild_readiness_schema = [string]$prebuild.schema
    prebuild_readiness_sha256 = $prebuildReceiptSha256
    profile = $Profile
    excluded_optional_components = $excludedComponents
    component_dispositions = $componentDispositions
    status = "verified_offline"
}
$manifestPath = Join-Path $assetRoot "GoodQ4All_Setup_$productVersion.release_manifest.json"
$manifest | ConvertTo-Json -Depth 5 | Set-Content -Path $manifestPath -Encoding utf8
$checksumPath = Join-Path $assetRoot "GoodQ4All_Setup_$productVersion.sha256"
$checksumEntries = Get-ChildItem -LiteralPath $assetRoot -File -Recurse |
    Where-Object { $_.FullName -ne $checksumPath } |
    ForEach-Object {
        $relativePath = $_.FullName.Substring($assetRoot.Length).TrimStart([char[]]'\\').Replace('\', '/')
        "$((Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower()) *$relativePath"
    } |
    Sort-Object
$checksumEntries | Set-Content -Path $checksumPath -Encoding ascii
Write-Host "[OK] Release manifest and checksums generated in $assetRoot" -ForegroundColor Green
