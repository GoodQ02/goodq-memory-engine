# Start only the configured GoodQ vLLM owner; never enable boot startup or
# start an unrelated Ollama service.
[CmdletBinding()]
param(
    [ValidateRange(1, 65535)][int]$Port = 38005,
    [ValidateRange(1, 300)][int]$WaitSeconds = 90
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_lib\interpreter_bindings.ps1')
$distro = Get-GoodQWslDistro -RequireConfigured
if ($distro -match '["\r\n]') { throw 'The configured WSL distribution name is invalid.' }
$unit = 'vllm-llama1b.service'
$endpoint = "http://127.0.0.1:$Port/v1/models"

function Get-VllmOwner {
    $lines = @(& wsl.exe -d $distro -u root --exec systemctl show $unit --property=LoadState,ActiveState,MainPID)
    if ($LASTEXITCODE -ne 0) { throw 'Cannot read the configured vLLM systemd owner.' }
    $state = ($lines -join [Environment]::NewLine) | ConvertFrom-StringData
    if ($state.LoadState -ne 'loaded') { throw 'The configured distro has no installed vLLM service.' }
    return $state
}

$before = Get-VllmOwner
$startedHere = $before.ActiveState -ne 'active'
try {
    & wsl.exe -d $distro -u root --exec systemctl start $unit
    if ($LASTEXITCODE -ne 0) { throw 'The systemd vLLM start failed.' }
    $state = Get-VllmOwner
    if ($state.ActiveState -ne 'active' -or [int]$state.MainPID -le 0) {
        throw 'The systemd vLLM owner is not active after start.'
    }

    # An anchor from another distro cannot attest this runtime's lifetime.
    $distroPattern = '(?:^|\s)(?:-d|--distribution)\s+(?:"' + [regex]::Escape($distro) + '"|' + [regex]::Escape($distro) + ')(?=\s|$)'
    $anchors = @(Get-CimInstance Win32_Process -Filter "Name='wsl.exe'" -ErrorAction Stop |
        Where-Object { $_.CommandLine -match $distroPattern -and
                      $_.CommandLine -match 'exec -a goodq-vllm-keepalive sleep infinity' })
    $anchor = $null
    if (-not $anchors.Count) {
        # WSL can treat unnecessary quotes around a simple distro name as
        # literal characters. Quote only names that actually contain spaces.
        $distroArgument = if ($distro -match '\s') { '"' + $distro + '"' } else { $distro }
        $anchor = Start-Process -FilePath 'wsl.exe' -WindowStyle Hidden -PassThru -ArgumentList @(
            '-d', $distroArgument, '--exec', 'bash', '-lc',
            '"exec -a goodq-vllm-keepalive sleep infinity"'
        )
        if (-not $anchor) { throw 'The configured WSL keepalive could not be created.' }
        $null = $anchor.Handle
    } else {
        Write-Host 'Reusing existing WSL keepalive anchor for the configured distro.'
    }

    $wait = [Diagnostics.Stopwatch]::StartNew()
    do {
        if ($anchor) {
            $anchor.Refresh()
            if ($anchor.HasExited) { throw 'The configured WSL keepalive exited before vLLM became ready.' }
        }
        $ready = $false
        try {
            $response = Invoke-RestMethod -Uri $endpoint -TimeoutSec 3 -ErrorAction Stop
            $models = @($response.data | Where-Object { $_.owned_by -eq 'vllm' -and $_.id })
            $ready = $models.Count -gt 0
        } catch {
            # Retry transient startup failures without logging response bodies.
        }
        if ($ready) {
            $state = Get-VllmOwner
            if ($state.ActiveState -ne 'active' -or [int]$state.MainPID -le 0) {
                throw 'The vLLM owner exited during readiness.'
            }
            Write-Host "vLLM speed endpoint is ready at $endpoint. Boot startup was not enabled."
            return
        }
        if ($wait.Elapsed.TotalSeconds -ge $WaitSeconds) { break }
        Start-Sleep -Milliseconds 250
    } while ($true)
    throw "vLLM speed endpoint did not become ready at $endpoint within $WaitSeconds seconds."
} catch {
    $startFailure = $_
    if ($startedHere) {
        try {
            # Reuse Dev Off's verified stop boundary for a failed new start.
            & (Join-Path $PSScriptRoot 'stop_vllm_servers.ps1') -Port $Port
        } catch {
            throw "vLLM startup failed: $($startFailure.Exception.Message) Cleanup is unverified: $($_.Exception.Message)"
        }
    }
    throw $startFailure
}
