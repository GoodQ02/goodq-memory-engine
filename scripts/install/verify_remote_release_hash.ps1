param(
    [Parameter(Mandatory = $true)]
    [string]$AssetRoot,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedVersion,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedCommit,
    [ValidateSet("PUBLIC_CPU_BASELINE", "PUBLIC_GPU_ENHANCED", "PERSONAL_AIR_GAP")]
    [string]$ExpectedProfile,
    [Parameter(Mandatory = $true)]
    [string]$ReceiptPath
)

$ErrorActionPreference = 'Stop'

if (-not ('GoodQExecutionState' -as [type])) {
    Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class GoodQExecutionState {
    [DllImport("kernel32.dll")]
    public static extern uint SetThreadExecutionState(uint flags);
}
'@
}

$ES_CONTINUOUS = [uint32]2147483648
$ES_SYSTEM_REQUIRED = [uint32]0x00000001
$assetRoot = [IO.Path]::GetFullPath($AssetRoot)
$receiptPath = [IO.Path]::GetFullPath($ReceiptPath)
$receiptDirectory = Split-Path -Parent $receiptPath
New-Item -ItemType Directory -Force -Path $receiptDirectory | Out-Null
$results = [System.Collections.Generic.List[object]]::new()
$currentPath = $null
$currentBytesHashed = [int64]0
$currentArtifactSizeBytes = $null
$lastHeartbeatUtc = [DateTime]::MinValue

function Write-Receipt([string]$Status, [string]$ErrorMessage = $null) {
    $receipt = [pscustomobject]@{
        schema_version = 1
        status = $Status
        updated_at_utc = (Get-Date).ToUniversalTime().ToString('o')
        source_commit = $script:manifest.source_commit
        profile = $script:manifest.profile
        current_artifact = $script:currentPath
        current_artifact_bytes_hashed = $script:currentBytesHashed
        current_artifact_size_bytes = $script:currentArtifactSizeBytes
        heartbeat_at_utc = (Get-Date).ToUniversalTime().ToString('o')
        results = @($script:results)
        error = $ErrorMessage
    }
    $temporary = "$script:receiptPath.tmp"
    [IO.File]::WriteAllText(
        $temporary,
        ($receipt | ConvertTo-Json -Depth 6),
        (New-Object Text.UTF8Encoding($false))
    )
    Move-Item -LiteralPath $temporary -Destination $script:receiptPath -Force
}

function Get-Sha256Hex([string]$Path, [Int64]$SizeBytes) {
    $bufferSize = 4MB
    $buffer = [byte[]]::new($bufferSize)
    $stream = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        $sha256 = [Security.Cryptography.SHA256]::Create()
        try {
            while (($read = $stream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                $null = $sha256.TransformBlock($buffer, 0, $read, $buffer, 0)
                $script:currentBytesHashed += $read
                if (((Get-Date).ToUniversalTime() - $script:lastHeartbeatUtc).TotalSeconds -ge 15) {
                    Write-Receipt 'running'
                    $script:lastHeartbeatUtc = (Get-Date).ToUniversalTime()
                }
            }
            $null = $sha256.TransformFinalBlock([byte[]]::new(0), 0, 0)
            return ([BitConverter]::ToString($sha256.Hash)).Replace('-', '').ToLowerInvariant()
        } finally {
            $sha256.Dispose()
        }
    } finally {
        $stream.Dispose()
    }
}

function Verify-Artifact([string]$RelativePath, [string]$ExpectedHash, [Nullable[Int64]]$ExpectedSize) {
    $script:currentPath = $RelativePath
    Write-Receipt 'running'
    $fullPath = Join-Path $script:assetRoot $RelativePath
    if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
        throw "Release asset is missing: $RelativePath"
    }
    $item = Get-Item -LiteralPath $fullPath
    if ($ExpectedSize.HasValue -and $item.Length -ne $ExpectedSize.Value) {
        throw "Release asset size does not match manifest: $RelativePath"
    }
    $script:currentArtifactSizeBytes = [int64]$item.Length
    $script:currentBytesHashed = [int64]0
    $script:lastHeartbeatUtc = (Get-Date).ToUniversalTime()
    $actualHash = Get-Sha256Hex $fullPath ([int64]$item.Length)
    if ($ExpectedHash -and $actualHash -ne $ExpectedHash.ToLowerInvariant()) {
        throw "Release asset SHA256 does not match manifest: $RelativePath"
    }
    $script:results.Add([pscustomobject]@{
        path = $RelativePath
        size_bytes = [int64]$item.Length
        sha256 = $actualHash
        expected_sha256 = $ExpectedHash
        hash_match = if ($ExpectedHash) { $actualHash -eq $ExpectedHash.ToLowerInvariant() } else { $true }
    })
    Write-Receipt 'running'
}

try {
    $null = [GoodQExecutionState]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED)
    $installerName = "GoodQ4All_Setup_$ExpectedVersion.exe"
    $launcherName = 'LAUNCH_GOODQ.exe'
    $manifestName = "GoodQ4All_Setup_$ExpectedVersion.release_manifest.json"
    $manifestPath = Join-Path $assetRoot $manifestName
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw "Release manifest is missing: $manifestName" }
    $script:manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.product_version -ne $ExpectedVersion) { throw "Manifest version does not match $ExpectedVersion" }
    if ($manifest.source_commit -ne $ExpectedCommit) { throw "Manifest commit does not match $ExpectedCommit" }
    if (-not $manifest.source_tree_clean) { throw 'Manifest does not prove a clean source tree' }
    if ($manifest.profile -ne $ExpectedProfile) { throw "Manifest profile is not $ExpectedProfile" }

    $payloadPacks = @($manifest.payload_packs)
    $expectedNames = @(
        $installerName,
        $launcherName,
        $manifestName,
        "GoodQ4All_Setup_$ExpectedVersion.sha256",
        $manifest.payload_manifest_filename,
        $manifest.payload_manifest_signature_filename
    ) + @($payloadPacks | ForEach-Object { [string]$_.path }) | Sort-Object
    $actualNames = @(Get-ChildItem -LiteralPath $assetRoot -Recurse -File | ForEach-Object {
        $_.FullName.Substring($assetRoot.Length).TrimStart([char[]]'\').Replace('\', '/')
    } | Sort-Object)
    if (Compare-Object -ReferenceObject $expectedNames -DifferenceObject $actualNames) {
        throw 'Release asset set does not exactly match the release manifest'
    }

    Verify-Artifact $manifestName $null $null
    Verify-Artifact $installerName ([string]$manifest.sha256) $null
    Verify-Artifact $launcherName ([string]$manifest.launcher_sha256) $null
    Verify-Artifact ([string]$manifest.payload_manifest_filename) ([string]$manifest.payload_manifest_sha256) $null
    Verify-Artifact ([string]$manifest.payload_manifest_signature_filename) ([string]$manifest.payload_manifest_signature_sha256) $null
    foreach ($pack in $payloadPacks) {
        Verify-Artifact ([string]$pack.path) ([string]$pack.sha256) ([Nullable[Int64]][int64]$pack.size_bytes)
    }

    $checksumName = "GoodQ4All_Setup_$ExpectedVersion.sha256"
    $checksumPath = Join-Path $assetRoot $checksumName
    $expectedChecksumLines = @($results | ForEach-Object { "$($_.sha256) *$($_.path)" } | Sort-Object)
    $actualChecksumLines = @(Get-Content -LiteralPath $checksumPath | ForEach-Object { $_.Trim() } | Where-Object { $_ } | Sort-Object)
    if (Compare-Object -ReferenceObject $expectedChecksumLines -DifferenceObject $actualChecksumLines) {
        throw 'Release checksum file does not exactly match the verified assets'
    }
    $script:currentPath = $null
    $script:currentBytesHashed = [int64]0
    $script:currentArtifactSizeBytes = $null
    Write-Receipt 'passed'
} catch {
    Write-Receipt 'failed' $_.Exception.Message
    throw
} finally {
    $null = [GoodQExecutionState]::SetThreadExecutionState($ES_CONTINUOUS)
}
