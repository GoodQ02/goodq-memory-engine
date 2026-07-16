[CmdletBinding(PositionalBinding = $false)]
param(
    [switch]$ListOnly
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$pytestRunner = Join-Path $repoRoot "scripts\dev\run_pytest.ps1"
$gitCommonDir = (& git -C $repoRoot rev-parse --path-format=absolute --git-common-dir).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Unable to resolve the shared Git directory."
}
$primaryCheckout = Split-Path -Parent $gitCommonDir

$reportNames = @("ucf_validation_report.json", "ucf_validation_report.md")
$reportTargets = @(
    foreach ($root in @($repoRoot, $primaryCheckout) | Select-Object -Unique) {
        foreach ($name in $reportNames) {
            Join-Path $root (Join-Path "reports" $name)
        }
    }
)
$testNodes = @(
    "tests/agents/test_mini_agent_client.py",
    "tests/integration/test_ucf_multi_source.py",
    "tests/integration/test_ucf_regression.py",
    "tests/integration/test_ucf_stress.py",
    "tests/integration/test_ucf_validator.py",
    "tests/integration/test_ucf_vector_integrity.py"
)

function Get-ReportEvidence([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return "absent"
    }
    $item = Get-Item -LiteralPath $Path
    $hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
    return "present|$($item.Length)|$($item.LastWriteTimeUtc.Ticks)|$hash"
}

Write-Host "[R18 VALIDATOR] report targets:"
foreach ($target in $reportTargets) {
    Write-Host "[R18 VALIDATOR] report=$target"
}
foreach ($node in $testNodes) {
    Write-Host "[R18 VALIDATOR] node=$node"
}
if ($ListOnly) {
    exit 0
}

$before = @{}
foreach ($target in $reportTargets) {
    $before[$target] = Get-ReportEvidence $target
}

$tempRoot = Join-Path ([IO.Path]::GetTempPath()) (
    "goodq-r18-validator-" + [guid]::NewGuid().ToString("N")
)
$baseTemp = Join-Path $tempRoot "pytest"
$cacheRoot = Join-Path $tempRoot "cache"
$miniAgentHome = Join-Path $tempRoot "mini-agent-home"
New-Item -ItemType Directory -Path $baseTemp, $cacheRoot, $miniAgentHome -Force | Out-Null

$previousProfile = $env:GOODQ_TEST_PROFILE
$previousMiniAgentHome = $env:GOODQ_MINI_AGENT_HOME
$previousBytecode = $env:PYTHONDONTWRITEBYTECODE
$suiteExit = 0
try {
    $env:GOODQ_TEST_PROFILE = "isolated"
    $env:GOODQ_MINI_AGENT_HOME = $miniAgentHome
    $env:PYTHONDONTWRITEBYTECODE = "1"
    $pytestArgs = @(
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $pytestRunner,
        "-TempRoot", $tempRoot,
        "-q",
        "--goodq-test-profile=isolated",
        "--basetemp=$baseTemp",
        "--override-ini=cache_dir=$cacheRoot"
    ) + $testNodes
    Push-Location -LiteralPath $repoRoot
    try {
        & powershell.exe @pytestArgs
        $suiteExit = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}
finally {
    $env:GOODQ_TEST_PROFILE = $previousProfile
    $env:GOODQ_MINI_AGENT_HOME = $previousMiniAgentHome
    $env:PYTHONDONTWRITEBYTECODE = $previousBytecode
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

$changed = @()
foreach ($target in $reportTargets) {
    $after = Get-ReportEvidence $target
    if ($after -ne $before[$target]) {
        $changed += $target
    }
}
if ($changed.Count -gt 0) {
    throw "Validator suite changed operator report evidence: $($changed -join ', ')"
}
if ($suiteExit -ne 0) {
    throw "R-18 validator suite failed with exit code $suiteExit."
}

Write-Host "[R18 VALIDATOR] PASS: tests passed and operator report evidence is unchanged."
