# The existing systemd service owns vLLM. This caller verifies its outcome;
# it never kills a process by a model name or changes service configuration.
[CmdletBinding()]
param([ValidateRange(1, 65535)][int]$Port = 38005)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_lib\interpreter_bindings.ps1')
$distro = Get-GoodQWslDistro -RequireConfigured
$unit = 'vllm-llama1b.service'

function Get-WslNames([switch]$Running) {
    $arguments = @('--list', '--quiet')
    if ($Running) { $arguments += '--running' }
    $names = @(& wsl.exe @arguments)
    if ($LASTEXITCODE -ne 0) { throw 'Cannot establish WSL distribution state.' }
    return @($names | ForEach-Object { ($_ -replace [char]0, '').Trim() } | Where-Object { $_ })
}

function Assert-WindowsEndpointAbsent {
    $client = [Net.Sockets.TcpClient]::new()
    try {
        $connection = $client.ConnectAsync('127.0.0.1', $Port)
        if (-not $connection.Wait(5000)) { throw 'Windows endpoint probe timed out; absence is unverified.' }
        throw "Port $Port still accepts connections; preserve dependencies and inspect its owner."
    } catch {
        $cause = $_.Exception.GetBaseException()
        if ($cause -is [Net.Sockets.SocketException] -and
            $cause.SocketErrorCode -eq [Net.Sockets.SocketError]::ConnectionRefused) { return }
        throw
    } finally { $client.Dispose() }
}

if (@(Get-WslNames -Running) -notcontains $distro) {
    if (@(Get-WslNames) -notcontains $distro) { throw 'The configured WSL distribution is not installed.' }
    Assert-WindowsEndpointAbsent
    Write-Host 'The configured vLLM distro is already stopped; no WSL compute command was run.'
    return
}

& wsl.exe -d $distro -u root --exec systemctl stop $unit
if ($LASTEXITCODE -ne 0) { throw 'The systemd vLLM stop failed; its keepalive and distro are preserved.' }

$lines = @(& wsl.exe -d $distro -u root --exec systemctl show $unit --property=LoadState,ActiveState,SubState,Result,MainPID,ControlGroup)
if ($LASTEXITCODE -ne 0) { throw 'Cannot read the vLLM stop result; release is unverified.' }
$state = ($lines -join [Environment]::NewLine) | ConvertFrom-StringData
if ($state.LoadState -ne 'loaded' -or $state.ActiveState -ne 'inactive' -or
    $state.SubState -ne 'dead' -or $state.Result -ne 'success' -or
    $state.MainPID -ne '0' -or -not $state.ContainsKey('ControlGroup') -or $state.ControlGroup) {
    throw 'The systemd owner does not attest successful release; inspect its state and journal.'
}

# Windows socket inventories can omit WSL-forwarded endpoints. Query Linux too,
# and refuse unknown/manual model processes rather than sweeping them away.
$listeners = @(& wsl.exe -d $distro -u root --exec ss -H -ltn "sport = :$Port")
if ($LASTEXITCODE -ne 0 -or $listeners.Count) { throw 'The Linux endpoint is present or its absence is unverified.' }
# --exec preserves the regex as one argv value; the default Linux shell would
# interpret its pipe and the keepalive pattern's space below.
& wsl.exe -d $distro -u root --exec pgrep -f '[v]llm.entrypoints.openai.api_server|[V]LLM::EngineCore' | Out-Null
if ($LASTEXITCODE -ne 1) { throw 'Model processes remain or their absence is unverified; no process sweep was attempted.' }
Assert-WindowsEndpointAbsent

# Terminate only the exact sleep anchor created by the accepted startup script,
# inside this distro. Its Windows wsl.exe clients should then exit naturally.
& wsl.exe -d $distro --exec pkill -TERM -f '^goodq-vllm-keepalive infinity$'
if ($LASTEXITCODE -notin @(0, 1)) { throw 'The selected keepalive could not be released.' }
$distroPattern = '(?:^|\s)(?:-d|--distribution)\s+(?:"' + [regex]::Escape($distro) + '"|' + [regex]::Escape($distro) + ')(?=\s|$)'
$wait = [Diagnostics.Stopwatch]::StartNew()
do {
    & wsl.exe -d $distro --exec pgrep -f '^goodq-vllm-keepalive infinity$' | Out-Null
    if ($LASTEXITCODE -notin @(0, 1)) { throw 'Cannot verify selected Linux keepalive absence.' }
    $linuxAnchorAbsent = $LASTEXITCODE -eq 1
    $clients = @(Get-CimInstance Win32_Process -Filter "Name='wsl.exe'" -ErrorAction Stop |
        Where-Object { $_.CommandLine -match $distroPattern -and
                      $_.CommandLine -match 'exec -a goodq-vllm-keepalive sleep infinity' })
    if ($linuxAnchorAbsent -and -not $clients.Count) { break }
    if ($wait.Elapsed.TotalSeconds -ge 5) { throw 'A selected Linux/Windows keepalive remains; distro release is blocked.' }
    Start-Sleep -Milliseconds 100
} while ($true)
Write-Host 'The systemd vLLM runtime, Linux/Windows endpoint and selected keepalive are released.'
Write-Host 'This verifies resource release; the upstream runtime owns completion of its requests.'
