<#
.SYNOPSIS
  Creates clean-install evidence and removes only explicitly approved GoodQ roots.

.DESCRIPTION
  Intended for an approved disposable follower. The helper writes before/after
  manifests beneath ValidationRoot and refuses any target outside the exact
  GoodQ4All program and data roots supplied by the caller.
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$ValidationRoot,
    [string]$ProgramRoot = "$env:ProgramFiles\GoodQ4All",
    [string]$DataRoot = "$env:ProgramData\GoodQ4All"
)

$ErrorActionPreference = "Stop"
$approvedRoots = @(
    [IO.Path]::GetFullPath("$env:ProgramFiles\GoodQ4All"),
    [IO.Path]::GetFullPath("$env:ProgramData\GoodQ4All")
)
$requestedRoots = @(
    [IO.Path]::GetFullPath($ProgramRoot),
    [IO.Path]::GetFullPath($DataRoot)
)
if (Compare-Object -ReferenceObject ($approvedRoots | Sort-Object) -DifferenceObject ($requestedRoots | Sort-Object)) {
    throw "Only the exact GoodQ4All program and data roots may be removed."
}

function Get-RootRecord([string]$Path) {
    $exists = Test-Path -LiteralPath $Path
    $files = if ($exists) { @(Get-ChildItem -LiteralPath $Path -Force -Recurse -File -ErrorAction Stop) } else { @() }
    [pscustomobject]@{
        path = $Path
        exists = $exists
        file_count = $files.Count
        bytes = [int64](($files | Measure-Object -Property Length -Sum).Sum)
    }
}

function Get-ActiveProcesses {
    @(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match '^(GoodQ|Qdrant|python|msiexec)' -or $_.CommandLine -match 'GoodQ4All'
    } | Select-Object ProcessId, Name, CommandLine)
}

New-Item -ItemType Directory -Force -Path $ValidationRoot | Out-Null
$preManifest = Join-Path $ValidationRoot "pre_removal_manifest.json"
$postManifest = Join-Path $ValidationRoot "post_removal_manifest.json"

[pscustomobject]@{
    timestamp_utc = (Get-Date).ToUniversalTime().ToString("o")
    target_hostname = $env:COMPUTERNAME
    validation_root = [IO.Path]::GetFullPath($ValidationRoot)
    approved_removal_roots = @($requestedRoots | ForEach-Object { Get-RootRecord $_ })
    active_processes = Get-ActiveProcesses
    action = "approved clean validation removal of exact GoodQ4All program and data roots"
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $preManifest -Encoding utf8

foreach ($target in $requestedRoots) {
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction Stop
    }
}

[pscustomobject]@{
    timestamp_utc = (Get-Date).ToUniversalTime().ToString("o")
    approved_removal_roots = @($requestedRoots | ForEach-Object { Get-RootRecord $_ })
    active_processes = Get-ActiveProcesses
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $postManifest -Encoding utf8

if (@($requestedRoots | Where-Object { Test-Path -LiteralPath $_ }).Count -ne 0) {
    throw "An approved removal root remains after reset."
}

[pscustomobject]@{
    pass = $true
    validation_root = [IO.Path]::GetFullPath($ValidationRoot)
    pre_removal_manifest = $preManifest
    post_removal_manifest = $postManifest
} | ConvertTo-Json -Compress
