[CmdletBinding(PositionalBinding = $false)]
param(
    [ValidateSet("live", "golden")]
    [string]$Profile = "golden",

    [string]$EpochId,

    [switch]$ListOnly,

    [switch]$CollectOnly
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$manifestPath = Join-Path $repoRoot "tests\runtime_evidence_manifest.json"
$pytestRunner = Join-Path $repoRoot "scripts\dev\run_pytest.ps1"
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json

if ($manifest.schema_version -ne 1) {
    throw "Unsupported runtime evidence manifest schema: $($manifest.schema_version)"
}

$goldenEpoch = [string]$manifest.golden.epoch_id
if ($Profile -eq "golden") {
    if ($EpochId -and $EpochId -ne $goldenEpoch) {
        throw "Golden profile is pinned to '$goldenEpoch'; received '$EpochId'."
    }
    $selectedEpoch = $goldenEpoch
}
else {
    if (-not $EpochId) {
        throw "The live profile requires an explicit -EpochId."
    }
    $selectedEpoch = $EpochId
}

$testNodes = @($manifest.golden.required_test_nodes)
if ($testNodes.Count -eq 0) {
    throw "Runtime evidence manifest contains no required test nodes."
}
foreach ($node in $testNodes) {
    $filePart = ([string]$node -split "::", 2)[0]
    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot $filePart) -PathType Leaf)) {
        throw "Runtime evidence test node is missing: $node"
    }
}

Write-Host "[RUNTIME EVIDENCE] profile=$Profile"
Write-Host "[RUNTIME EVIDENCE] epoch=$selectedEpoch"
foreach ($node in $testNodes) {
    Write-Host "[RUNTIME EVIDENCE] node=$node"
}

if ($ListOnly) {
    exit 0
}

$tempRoot = Join-Path ([IO.Path]::GetTempPath()) (
    "goodq-runtime-evidence-" + [guid]::NewGuid().ToString("N")
)
$baseTemp = Join-Path $tempRoot "pytest"
$cacheRoot = Join-Path $tempRoot "cache"
New-Item -ItemType Directory -Path $baseTemp, $cacheRoot -Force | Out-Null

$previousProfile = $env:GOODQ_TEST_PROFILE
$previousTestEpoch = $env:GOODQ_TEST_EPOCH
$previousEpochId = $env:GOODQ_EPOCH_ID
$previousBytecode = $env:PYTHONDONTWRITEBYTECODE

try {
    $env:GOODQ_TEST_PROFILE = $Profile
    $env:GOODQ_TEST_EPOCH = $selectedEpoch
    $env:GOODQ_EPOCH_ID = $selectedEpoch
    $env:PYTHONDONTWRITEBYTECODE = "1"

    $pytestArgs = @(
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $pytestRunner,
        "-TempRoot", $tempRoot,
        "-q",
        "--goodq-test-profile=$Profile",
        "--basetemp=$baseTemp",
        "--override-ini=cache_dir=$cacheRoot"
    )
    if ($CollectOnly) {
        $pytestArgs += "--collect-only"
    }
    $pytestArgs += $testNodes

    Push-Location -LiteralPath $repoRoot
    try {
        & powershell.exe @pytestArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Runtime evidence suite failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    $env:GOODQ_TEST_PROFILE = $previousProfile
    $env:GOODQ_TEST_EPOCH = $previousTestEpoch
    $env:GOODQ_EPOCH_ID = $previousEpochId
    $env:PYTHONDONTWRITEBYTECODE = $previousBytecode
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
