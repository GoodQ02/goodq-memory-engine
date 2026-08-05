[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$BuildScript,
    [Parameter(Mandatory)]
    [string]$OutputRoot,
    [string]$CondaExe = $env:CONDA_EXE,
    [switch]$ElevatedRelaunch,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Resolve-CondaLauncher {
    param([string]$Candidate)
    if ([string]::IsNullOrWhiteSpace($Candidate) -or -not (Test-Path -LiteralPath $Candidate)) {
        throw "A full Conda launcher path is required before temporary network containment starts."
    }
    $resolved = (Resolve-Path -LiteralPath $Candidate).Path
    if ([IO.Path]::GetExtension($resolved) -ieq ".bat") {
        $executable = Join-Path (Split-Path $resolved -Parent) "..\Scripts\conda.exe"
        if (Test-Path -LiteralPath $executable) {
            return (Resolve-Path -LiteralPath $executable).Path
        }
    }
    return $resolved
}

function Write-Receipt {
    param([hashtable]$Receipt)
    $path = Join-Path $OutputRoot "network-toggle-receipt.json"
    $Receipt.updated_at = [DateTime]::UtcNow.ToString("o")
    $Receipt | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $path -Encoding UTF8
}

function Test-PublicConnectivity {
    try {
        return [bool](Test-NetConnection -ComputerName github.com -Port 443 -InformationLevel Quiet -WarningAction SilentlyContinue)
    } catch {
        return $false
    }
}

if (-not (Test-Path -LiteralPath $BuildScript)) {
    throw "Offline build script is missing: $BuildScript"
}
$CondaExe = Resolve-CondaLauncher $CondaExe

New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
$receipt = @{
    schema = "goodq.offline-network-containment.v1"
    started_at = [DateTime]::UtcNow.ToString("o")
    build_script = [System.IO.Path]::GetFullPath($BuildScript)
    output_root = [System.IO.Path]::GetFullPath($OutputRoot)
    firewall_rule_name = "GoodQ4All-OfflineBuild-$([Guid]::NewGuid().ToString('N'))"
    mode = if ($DryRun) { "dry_run" } else { "run" }
}

if (-not $DryRun -and -not (Test-Administrator)) {
    if ($ElevatedRelaunch) {
        throw "The elevated offline containment wrapper did not receive administrator privileges."
    }
    Write-Host "[INFO] Administrator approval is required only to add and remove the temporary outbound firewall rule." -ForegroundColor Cyan
    $process = Start-Process -FilePath "powershell.exe" -Verb RunAs -Wait -PassThru -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $PSCommandPath,
        "-BuildScript", $BuildScript, "-OutputRoot", $OutputRoot,
        "-CondaExe", $CondaExe, "-ElevatedRelaunch"
    )
    exit $process.ExitCode
}

$adapterBefore = @(Get-NetAdapter -Physical | Select-Object Name, InterfaceDescription, Status, AdminStatus, ifIndex)
$receipt.adapter_state_before = $adapterBefore
$receipt.connectivity_before = Test-PublicConnectivity
Write-Receipt $receipt

if ($DryRun) {
    Write-Host "[READY] Dry run complete. No firewall rule or adapter state was changed." -ForegroundColor Green
    exit 0
}

$ruleCreated = $false
$buildExitCode = 1
$restored = $false
$previousOutputRoot = $env:GOODQ_RELEASE_OUTPUT_ROOT
try {
    Write-Host "[1/4] Applying a temporary outbound containment rule (adapters remain enabled)..." -ForegroundColor Cyan
    New-NetFirewallRule -Name $receipt.firewall_rule_name -DisplayName $receipt.firewall_rule_name `
        -Group "GoodQ4All Offline Build" -Direction Outbound -Action Block -RemoteAddress Any `
        -Profile Any -PolicyStore ActiveStore -ErrorAction Stop | Out-Null
    $ruleCreated = $true
    $receipt.containment_applied = $true
    Write-Receipt $receipt

    Write-Host "[2/4] Running the existing physical-offline preflight and build..." -ForegroundColor Cyan
    $env:GOODQ_AUTO_NETWORK_TOGGLE = "1"
    $env:CONDA_EXE = $CondaExe
    $env:GOODQ_RELEASE_OUTPUT_ROOT = $OutputRoot
    & $BuildScript
    $buildExitCode = $LASTEXITCODE
    $receipt.build_exit_code = $buildExitCode
    Write-Receipt $receipt
}
finally {
    Remove-Item Env:GOODQ_AUTO_NETWORK_TOGGLE -ErrorAction SilentlyContinue
    if ($null -eq $previousOutputRoot) {
        Remove-Item Env:GOODQ_RELEASE_OUTPUT_ROOT -ErrorAction SilentlyContinue
    } else {
        $env:GOODQ_RELEASE_OUTPUT_ROOT = $previousOutputRoot
    }
    if ($ruleCreated) {
        Write-Host "[3/4] Removing the exact temporary containment rule..." -ForegroundColor Cyan
        Remove-NetFirewallRule -Name $receipt.firewall_rule_name -PolicyStore ActiveStore -ErrorAction Stop
        $restored = $true
    }
    $receipt.containment_removed = $restored
    $receipt.adapter_state_after = @(Get-NetAdapter -Physical | Select-Object Name, InterfaceDescription, Status, AdminStatus, ifIndex)
    Start-Sleep -Seconds 2
    $receipt.connectivity_after = Test-PublicConnectivity
    Write-Receipt $receipt
}

Write-Host "[4/4] Adapter state was never modified; temporary firewall rule removed: $restored" -ForegroundColor Green
if ($receipt.connectivity_before -and -not $receipt.connectivity_after) {
    Write-Warning "The rule was removed, but the public connectivity probe has not recovered yet. Check the receipt before retrying."
    exit 2
}
exit $buildExitCode
