# GoodQ4All - Preflight Build Audit & Containment Check
# ---------------------------------------------------
$ErrorActionPreference = "Stop"

function Fail-Build {
    param(
        [string]$Message,
        [int]$ExitCode
    )
    Write-Host "ERROR: $Message" -ForegroundColor Red
    [Console]::Error.WriteLine("ERROR: $Message")
    exit $ExitCode
}

$ResolvedManifestPath = [System.IO.Path]::GetFullPath('..\..\configs\offline_dependencies_manifest.json')
if (-not (Test-Path $ResolvedManifestPath)) {
    Fail-Build "Manifest missing at $ResolvedManifestPath!" 1
}

Write-Host "Checking for poison payloads in staging directories..." -ForegroundColor Cyan
$poisonFiles = @()
$poisonPatterns = @('.env.local', '*.key', '*.pem', 'token', 'huggingface/token', 'memory.db', 'knowledge_graph.db')
foreach ($pat in $poisonPatterns) {
    $found = Get-ChildItem -Path 'staged_cache', 'staged' -Filter $pat -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne "cacert.pem" }
    if ($found) { $poisonFiles += $found }
}
if ($poisonFiles.Count -gt 0) {
    Fail-Build "Poison files detected in staging paths: $poisonFiles. Aborting compilation!" 10
}

Write-Host "Auditing packaging scripts for forbidden online commands..." -ForegroundColor Cyan
$scripts = @('build_installer.bat', 'goodq4all_installer.nsi', 'sandbox_env_setup.py')
$onlineCommands = @('curl ', 'wget ', 'Invoke-WebRequest', 'git clone', 'huggingface-cli download', 'pip download')
foreach ($s in $scripts) {
    if (Test-Path $s) {
        $lines = Get-Content -Path $s
        foreach ($line in $lines) {
            # Skip comments and the scanner command definitions themselves
            if ($line.Trim().StartsWith('::') -or $line.Trim().StartsWith('#') -or $line -like '*onlineCommands*') { continue }
            foreach ($cmd in $onlineCommands) {
                if ($line -like "*$cmd*") {
                    Fail-Build "Forbidden online command '$cmd' found in packaging file '$s'. Line: $line" 11
                }
            }
            # Check for pip installs without --no-index
            if ($line -like '*pip install*' -and $line -notlike '*--no-index*') {
                Fail-Build "Forbidden online pip install found in packaging file '$s'. Line: $line" 12
            }
        }
    }
}

if ($env:GOODQ_BYPASS_NETWORK_CHECK -eq "1") {
    Write-Host "[BYPASS] Physical network containment check bypassed for development compilation." -ForegroundColor Yellow
} else {
    Write-Host "Verifying physical network containment..." -ForegroundColor Cyan
    $networkActive = $false
    try {
        $res = [System.Net.Dns]::GetHostAddresses('github.com')
        $networkActive = $true
    } catch {
        # Expected failure in offline environment
    }

    if ($networkActive) {
        Fail-Build "Network adapter is active. Physical containment block not detected at OS-level." 13
    } else {
        Write-Host "[OK] Host system is verified offline." -ForegroundColor Green
    }
}

