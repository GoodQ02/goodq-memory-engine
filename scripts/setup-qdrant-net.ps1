[CmdletBinding()]
param(
    [string]$RepoRoot = (Get-Location).Path,
    [string]$ServiceName = "GoodQ_Qdrant",
    [int]$Port = 6333,
    [string]$LanCidr = "192.168.1.0/24",
    [string]$WslDistro = $(if ($env:GOODQ_WSL_DISTRO) { $env:GOODQ_WSL_DISTRO } else { "Ubuntu" }),
    [switch]$DisableOtherInboundAllowRules
)

$ErrorActionPreference = "Stop"

function Assert-Admin {
    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).
        IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) {
        throw "Run this script in an elevated PowerShell session (Administrator)."
    }
}

function Test-JsonEndpoint {
    param([Parameter(Mandatory = $true)][string]$Url)

    try {
        $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 6
        $null = $resp.Content | ConvertFrom-Json
        return [pscustomobject]@{
            Url        = $Url
            Success    = $true
            StatusCode = [int]$resp.StatusCode
            Error      = $null
        }
    }
    catch {
        $statusCode = $null
        if ($_.Exception.Response) {
            try { $statusCode = [int]$_.Exception.Response.StatusCode.value__ } catch {}
        }
        return [pscustomobject]@{
            Url        = $Url
            Success    = $false
            StatusCode = $statusCode
            Error      = $_.Exception.Message
        }
    }
}

function Convert-ToWslPath {
    param([Parameter(Mandatory = $true)][string]$WindowsPath)
    $p = $WindowsPath -replace '\\', '/'
    if ($p -match '^([A-Za-z]):/(.*)$') {
        return "/mnt/$($matches[1].ToLower())/$($matches[2])"
    }
    return $p
}

Assert-Admin
$null = Get-Command wsl -ErrorAction Stop

$configPath = Join-Path $RepoRoot "vendor\qdrant\config.yaml"
if (-not (Test-Path $configPath)) {
    throw "Qdrant config not found: $configPath"
}

# 1) Set Qdrant binding host to 0.0.0.0
$raw = Get-Content -Path $configPath -Raw -Encoding UTF8
$configUpdated = $false
$pattern127 = '(?m)^(\s*host:\s*)127\.0\.0\.1(\s*(?:#.*)?)$'
$patternAll = '(?m)^\s*host:\s*0\.0\.0\.0\b'

if ($raw -match $pattern127) {
    $updated = [regex]::Replace($raw, $pattern127, '${1}0.0.0.0${2}', 1)
    if ($updated -ne $raw) {
        Set-Content -Path $configPath -Value $updated -Encoding UTF8
        $configUpdated = $true
    }
}
elseif ($raw -match $patternAll) {
    $updated = $raw
}
else {
    throw "No host binding line found to update in $configPath."
}

# 2) Firewall rules: restrict 6333 to LAN on Private profile
$inRuleName = "GoodQ Qdrant 6333 Inbound Private LAN"
$outRuleName = "GoodQ Qdrant 6333 Outbound Private LAN"
$blockNonPrivateRuleName = "GoodQ Qdrant 6333 Inbound Block NonPrivate"

Get-NetFirewallRule -DisplayName $inRuleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
Get-NetFirewallRule -DisplayName $outRuleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
Get-NetFirewallRule -DisplayName $blockNonPrivateRuleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule

New-NetFirewallRule -DisplayName $inRuleName `
    -Direction Inbound -Protocol TCP -LocalPort $Port `
    -Action Allow -RemoteAddress $LanCidr -Profile Private | Out-Null

New-NetFirewallRule -DisplayName $outRuleName `
    -Direction Outbound -Protocol TCP -LocalPort $Port `
    -Action Allow -RemoteAddress $LanCidr -Profile Private | Out-Null

New-NetFirewallRule -DisplayName $blockNonPrivateRuleName `
    -Direction Inbound -Protocol TCP -LocalPort $Port `
    -Action Block -RemoteAddress Any -Profile Domain,Public | Out-Null

if ($DisableOtherInboundAllowRules) {
    $ourRules = @($inRuleName, $blockNonPrivateRuleName)
    $candidateRules = Get-NetFirewallRule -Direction Inbound -Action Allow -Enabled True | Where-Object {
        $_.DisplayName -notin $ourRules
    }

    foreach ($r in $candidateRules) {
        $pf = Get-NetFirewallPortFilter -AssociatedNetFirewallRule $r -ErrorAction SilentlyContinue
        if ($pf -and $pf.Protocol -eq "TCP" -and $pf.LocalPort -eq "$Port") {
            Disable-NetFirewallRule -Name $r.Name | Out-Null
        }
    }
}

# 3) Restart service
Restart-Service -Name $ServiceName -Force
Start-Sleep -Seconds 2
$svc = Get-Service -Name $ServiceName
if ($svc.Status -ne "Running") {
    Start-Sleep -Seconds 2
    $svc = Get-Service -Name $ServiceName
}
if ($svc.Status -ne "Running") {
    throw "Service $ServiceName is not running after restart."
}

# 4) PowerShell reachability tests
$localhostUrl = "http://localhost:$Port/collections"
$localTest = Test-JsonEndpoint -Url $localhostUrl

$privateIfIndexes = @(
    Get-NetConnectionProfile -ErrorAction SilentlyContinue |
    Where-Object { $_.NetworkCategory -eq "Private" } |
    Select-Object -ExpandProperty InterfaceIndex
)

$ipCandidates = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
        $_.IPAddress -notlike "127.*" -and
        $_.IPAddress -notlike "169.254.*" -and
        ($privateIfIndexes.Count -eq 0 -or $privateIfIndexes -contains $_.InterfaceIndex)
    } |
    Sort-Object InterfaceMetric, SkipAsSource, IPAddress

$interfaceTest = $null
$interfaceIp = $null
if ($ipCandidates -and $ipCandidates.Count -gt 0) {
    $interfaceIp = $ipCandidates[0].IPAddress
    $interfaceUrl = "http://$interfaceIp`:$Port/collections"
    $interfaceTest = Test-JsonEndpoint -Url $interfaceUrl
}

# 5) Deploy + run WSL validator script
$bashPathWin = Join-Path $RepoRoot "scripts\wsl\qdrant_network_validator.sh"
$bashDir = Split-Path -Parent $bashPathWin
if (-not (Test-Path $bashDir)) { New-Item -ItemType Directory -Path $bashDir -Force | Out-Null }

$bashScript = @'
#!/usr/bin/env bash
set -u

PORT="${1:-6333}"
PATH_SUFFIX="/collections"

echo "========================================"
echo "WSL Qdrant Reachability Check"
echo "========================================"

WIN_HOST_IP="$(ip route 2>/dev/null | awk '/^default/ {print $3; exit}')"
if [[ -z "${WIN_HOST_IP}" ]]; then
  echo "[FAIL] Could not detect Windows host IP from routing table"
  exit 2
fi

echo "[INFO] Windows host IP: ${WIN_HOST_IP}"
echo "[INFO] Port: ${PORT}"

if timeout 3 bash -lc ":</dev/tcp/${WIN_HOST_IP}/${PORT}" 2>/dev/null; then
  echo "[PASS] TCP ${WIN_HOST_IP}:${PORT} reachable"
  tcp_ok=1
else
  echo "[WARN] TCP ${WIN_HOST_IP}:${PORT} not reachable"
  tcp_ok=0
fi

check_json() {
  local label="$1"
  local url="$2"
  local tmp code body

  tmp="$(mktemp)"
  code="$(curl -sS --max-time 6 -o "$tmp" -w "%{http_code}" "$url" 2>/dev/null || echo 000)"
  body="$(cat "$tmp" 2>/dev/null || true)"
  rm -f "$tmp"

  echo "[CHECK] ${label}: ${url}"
  echo "[INFO] HTTP ${code}"

  if [[ "${code}" =~ ^2[0-9][0-9]$ ]] && printf '%s' "$body" | python3 -c 'import sys,json; json.load(sys.stdin)' >/dev/null 2>&1; then
    echo "[PASS] ${label} returned valid JSON"
    return 0
  fi

  echo "[FAIL] ${label} did not return valid JSON"
  return 1
}

local_ok=0
host_ok=0

check_json "WSL localhost" "http://localhost:${PORT}${PATH_SUFFIX}" && local_ok=1 || true
check_json "Windows host IP" "http://${WIN_HOST_IP}:${PORT}${PATH_SUFFIX}" && host_ok=1 || true

echo "========================================"
echo "WSL Summary"
echo "========================================"
echo "[INFO] tcp_ok=${tcp_ok}"
echo "[INFO] local_ok=${local_ok}"
echo "[INFO] host_ok=${host_ok}"

if [[ "${local_ok}" -eq 1 || "${host_ok}" -eq 1 ]]; then
  exit 0
else
  exit 1
fi
'@

$bashScript = $bashScript -replace "`r`n", "`n"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($bashPathWin, $bashScript, $utf8NoBom)

$bashPathWsl = Convert-ToWslPath -WindowsPath $bashPathWin
$bashCmd = "chmod +x '$bashPathWsl' && '$bashPathWsl' $Port"

$wslOutput = & wsl -d $WslDistro -- bash -lc $bashCmd 2>&1 | Out-String
$wslExitCode = $LASTEXITCODE

# 6) Summary health output
$ruleSet = Get-NetFirewallRule -DisplayName "GoodQ Qdrant 6333 *" -ErrorAction SilentlyContinue |
    Select-Object DisplayName, Enabled, Direction, Action, Profile

$summary = [pscustomobject]@{
    ConfigPath      = $configPath
    ConfigUpdated   = $configUpdated
    ServiceName     = $ServiceName
    ServiceStatus   = $svc.Status
    Port            = $Port
    LanCidr         = $LanCidr
    FirewallRules   = $ruleSet
    PowerShellTests = [pscustomobject]@{
        Localhost = $localTest
        Interface = $interfaceTest
    }
    InterfaceIP     = $interfaceIp
    WslDistro       = $WslDistro
    WslExitCode     = $wslExitCode
    WslOutput       = $wslOutput.Trim()
    Success         = (
        $svc.Status -eq "Running" -and
        $localTest.Success -and
        ($wslExitCode -eq 0)
    )
}

$summary | ConvertTo-Json -Depth 8

if ($summary.Success) { exit 0 } else { exit 1 }
