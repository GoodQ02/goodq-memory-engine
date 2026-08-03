param(
    [Parameter(Mandatory = $true)]
    [string]$AssetRoot,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedVersion,
    [string]$ExpectedCommit
)

$ErrorActionPreference = "Stop"
$assetRoot = [System.IO.Path]::GetFullPath($AssetRoot)
$installerName = "GoodQ4All_Setup_$ExpectedVersion.exe"
$manifestName = "GoodQ4All_Setup_$ExpectedVersion.release_manifest.json"
$checksumName = "GoodQ4All_Setup_$ExpectedVersion.sha256"
$expectedNames = @($installerName, "LAUNCH_GOODQ.exe", $manifestName, $checksumName) | Sort-Object
$actualNames = @(Get-ChildItem -File $assetRoot | Select-Object -ExpandProperty Name | Sort-Object)
if (Compare-Object -ReferenceObject $expectedNames -DifferenceObject $actualNames) {
    throw "Release asset set must contain exactly: $($expectedNames -join ', ')"
}

$manifestPath = Join-Path $assetRoot $manifestName
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
if ($manifest.product_version -ne $ExpectedVersion) { throw "Manifest version does not match $ExpectedVersion" }
if ($ExpectedCommit -and $manifest.source_commit -ne $ExpectedCommit) { throw "Manifest commit does not match $ExpectedCommit" }
if (-not $manifest.source_tree_clean) { throw "Manifest does not prove a clean source tree" }
if ($manifest.profile -ne "BASELINE") { throw "Manifest profile is not BASELINE" }
if (@($manifest.excluded_optional_components) -notcontains "wsl_audio") { throw "Manifest must exclude WSL audio" }
if (@($manifest.excluded_optional_components) -notcontains "local_llm_serving") { throw "Manifest must exclude local LLM serving" }

$installerHash = (Get-FileHash (Join-Path $assetRoot $installerName) -Algorithm SHA256).Hash.ToLower()
$launcherHash = (Get-FileHash (Join-Path $assetRoot "LAUNCH_GOODQ.exe") -Algorithm SHA256).Hash.ToLower()
if ($manifest.sha256 -ne $installerHash) { throw "Installer SHA256 does not match manifest" }
if ($manifest.launcher_sha256 -ne $launcherHash) { throw "Launcher SHA256 does not match manifest" }
$checksumText = Get-Content (Join-Path $assetRoot $checksumName) -Raw
foreach ($pair in @("$installerHash *$installerName", "$launcherHash *LAUNCH_GOODQ.exe")) {
    if ($checksumText -notmatch [regex]::Escape($pair)) { throw "Checksum file lacks $pair" }
}
$serializedManifest = Get-Content $manifestPath -Raw
foreach ($privateToken in @('C:\\Users\\', 'L:\\', 'OneDrive', 'GOODCUBE', 'GoodQ_Data')) {
    if ($serializedManifest -match [regex]::Escape($privateToken)) { throw "Manifest contains private token $privateToken" }
}
[pscustomobject]@{ pass = $true; version = $ExpectedVersion; source_commit = $manifest.source_commit; assets = $actualNames } | ConvertTo-Json -Depth 3
