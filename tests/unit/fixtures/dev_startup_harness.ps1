param(
    [Parameter(Mandatory=$true)][string]$StartupScript,
    [Parameter(Mandatory=$true)][string]$PythonExe,
    [Parameter(Mandatory=$true)][string]$SandboxRoot,
    [Parameter(Mandatory=$true)][int]$Port,
    [Parameter(Mandatory=$true)][string]$Scenario,
    [Parameter(Mandatory=$true)][string]$ReceiptPath,
    [int]$ForeignPid = 0,
    [switch]$Supervise,
    [switch]$CheckStart,
    [int]$MaxRestarts = 0,
    [double]$RestartBackoffSeconds = 0.6,
    [double]$DrainTimeoutSeconds = 2
)

$ErrorActionPreference = 'Stop'
$global:GoodQStartupTest = @{
    Owned=[Collections.Generic.List[Diagnostics.Process]]::new()
    Messages=[Collections.Generic.List[string]]::new()
    Starts=[Collections.Generic.List[string]]::new()
    ServiceRequests=0
}

# Only the external service and unrestricted machine-wide process scan are
# replaced. Listener ownership, HTTP, child creation, exit and cleanup are real.
function Get-Service {
    [CmdletBinding()]param($Name)
    if ($Name -ne 'GoodQ_Qdrant') { throw 'Unexpected service query.' }
    $status = if ($Scenario -eq 'service_already_running') { 'Running' } else { 'Stopped' }
    [pscustomobject]@{ Status=$status }
}
function Start-Service {
    [CmdletBinding()]param($Name)
    if ($Name -ne 'GoodQ_Qdrant') { throw 'Unexpected service request.' }
    $global:GoodQStartupTest.ServiceRequests++
    if ($Scenario -eq 'service_already_running') { throw 'Redundant start requires unnecessary service control rights.' }
    if ($Scenario -eq 'startup_owner_wait') {
        [IO.File]::WriteAllText((Join-Path $SandboxRoot 'awaiting-store.json'), ($Port | ConvertTo-Json))
        $deadline = [DateTime]::UtcNow.AddSeconds(15)
        while (-not (Test-Path -LiteralPath (Join-Path $SandboxRoot 'release-store'))) {
            if ([DateTime]::UtcNow -ge $deadline) { throw 'Fixture store wait timed out.' }
            Start-Sleep -Milliseconds 50
        }
    }
}
function Get-CimInstance {
    [CmdletBinding()]param($ClassName, $Filter)
    if ($ClassName -ne 'Win32_Process' -or $Filter -ne "name='python.exe'") {
        throw 'Unexpected unrestricted process query.'
    }
    # No pre-existing GoodQ children in this isolated deployment.
}
function Get-NetTCPConnection {
    [CmdletBinding()]param($LocalPort, $State)
    if ($LocalPort -and $LocalPort -notin @(30000, $Port)) {
        throw 'Unexpected port query.'
    }
    # The legacy script hardcodes 30000. Redirect only that deployment setting;
    # every returned connection and owner belongs to the real isolated port.
    NetTCPIP\Get-NetTCPConnection -State Listen -ErrorAction Stop |
        Where-Object LocalPort -eq $Port
}
function Write-Host {
    param([Parameter(ValueFromRemainingArguments=$true)]$Object)
    $global:GoodQStartupTest.Messages.Add(($Object -join ' '))
}
function Invoke-WebRequest {
    [CmdletBinding()]param([switch]$UseBasicParsing, $Uri, $TimeoutSec, $MaximumRedirection)
    $response = Microsoft.PowerShell.Utility\Invoke-WebRequest @PSBoundParameters
    $exitMarker = Join-Path $SandboxRoot 'exit-after-http.json'
    if (Test-Path -LiteralPath $exitMarker) {
        # Deterministic real-process exit between HTTP success and the launcher's
        # ownership recheck. The process must be one of this fixture's handles.
        $requestedPid = (Get-Content -LiteralPath $exitMarker -Raw | ConvertFrom-Json).pid
        $child = @($global:GoodQStartupTest.Owned | Where-Object Id -eq $requestedPid)
        if ($child.Count -ne 1) { throw 'Fault injection requested a child outside fixture ownership.' }
        Remove-Item -LiteralPath $exitMarker
        $child[0].Kill()
        $child[0].WaitForExit(5000) | Out-Null
    }
    $response
}
function Stop-Process {
    [CmdletBinding()]param($Id, $InputObject, [switch]$Force)
    $requested = @($Id) + @($InputObject | ForEach-Object Id)
    $allowed = @($ForeignPid) + @($global:GoodQStartupTest.Owned | ForEach-Object Id)
    foreach ($candidate in $requested) {
        if ($candidate -and $candidate -notin $allowed) {
            throw "Refusing termination outside test ownership: $candidate"
        }
    }
    if ($InputObject) {
        Microsoft.PowerShell.Management\Stop-Process -InputObject $InputObject -Force:$Force -ErrorAction Stop
    } else {
        Microsoft.PowerShell.Management\Stop-Process -Id $Id -Force:$Force -ErrorAction Stop
    }
}
function Start-Process {
    [CmdletBinding()]param(
        $FilePath, $ArgumentList, $WorkingDirectory, $WindowStyle,
        [switch]$PassThru, $RedirectStandardOutput, $RedirectStandardError
    )
    $arguments = $ArgumentList -join ' '
    if ([IO.Path]::GetFullPath($WorkingDirectory) -ne [IO.Path]::GetFullPath($SandboxRoot)) {
        throw 'Refusing a child outside the isolated deployment.'
    }
    if ($FilePath -notin @($PythonExe, 'powershell', 'powershell.exe')) {
        throw "Unexpected child executable: $FilePath"
    }
    if ($arguments -notmatch '-m (api\.server|cli\.watchdog)') {
        throw 'Unexpected child command.'
    }
    $role = if ($arguments -match 'api\.server') { 'api' } else { 'watchdog' }
    $global:GoodQStartupTest.Starts.Add($role)
    $parameters = @{
        FilePath=$FilePath; ArgumentList=($arguments -replace '-WindowStyle Minimized', '-WindowStyle Hidden')
        WorkingDirectory=$SandboxRoot; WindowStyle='Hidden'; PassThru=$true; ErrorAction='Stop'
    }
    if ($RedirectStandardOutput) { $parameters.RedirectStandardOutput = $RedirectStandardOutput }
    if ($RedirectStandardError) { $parameters.RedirectStandardError = $RedirectStandardError }
    if ($FilePath -in @('powershell', 'powershell.exe')) {
        $parameters.ArgumentList = '-NoProfile -NonInteractive ' + $parameters.ArgumentList
    }
    if ($Scenario -eq 'api_launch_error' -and $role -eq 'api') {
        # Exercise a real OS launch failure, not a synthetic successful process.
        $parameters.FilePath = Join-Path $SandboxRoot 'missing-python.exe'
        $parameters.ErrorAction = $ErrorActionPreference
    }
    $child = Microsoft.PowerShell.Management\Start-Process @parameters
    if ($child) {
        # The launcher may dispose its own handle. Keep an independent handle
        # for fixture observation/cleanup, bound while this child is still alive.
        $trackedChild = [Diagnostics.Process]::GetProcessById($child.Id)
        $null = $trackedChild.Handle
        $global:GoodQStartupTest.Owned.Add($trackedChild)
        # Publish each cleanup identity once. Rewriting one shared fixture file
        # introduced its own Windows sharing failure during a seeded restart.
        $identityPath = Join-Path $SandboxRoot "owned-process-$($trackedChild.Id).json"
        $identity = [pscustomobject]@{Pid=$trackedChild.Id; Created=$trackedChild.StartTime.ToUniversalTime().ToString('o')}
        [IO.File]::WriteAllText(($identityPath + '.tmp'), ($identity | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
        [IO.File]::Move(($identityPath + '.tmp'), $identityPath)
        if ($PassThru) { $child }
    }
}

$completed = $false
$failure = $null
$children = @()
try {
    try {
        $parameters = @{ApiPort=$Port; StartupTimeoutSeconds=4; StabilizationSeconds=0.4}
        if ($CheckStart) { $parameters.CheckStart = $true }
        if ($Supervise) {
            $parameters.Supervise = $true
            $parameters.MaxRestarts = $MaxRestarts
            $parameters.RestartBackoffSeconds = $RestartBackoffSeconds
            $parameters.HealthIntervalSeconds = 0.2
            # The old script has no drain argument; let its missing stop
            # behavior be observed rather than failing parameter binding here.
            if ((Get-Command $StartupScript).Parameters.ContainsKey('DrainTimeoutSeconds')) {
                $parameters.DrainTimeoutSeconds = $DrainTimeoutSeconds
            }
        }
        & $StartupScript @parameters | Out-Null
        $completed = $true
    } catch {
        $failure = $_.Exception.Message + "`n" + $_.ScriptStackTrace
    }
    # Observe launched legacy wrappers long enough for their actual Python child
    # to start or exit. This does not change the launcher's completion decision.
    $observationDeadline = [DateTime]::UtcNow.AddSeconds(3)
    do {
        $missing = @($global:GoodQStartupTest.Starts | Where-Object {
            -not (Test-Path -LiteralPath (Join-Path $SandboxRoot "$_.json"))
        })
        if (-not $missing.Count) { break }
        Start-Sleep -Milliseconds 50
    } while ([DateTime]::UtcNow -lt $observationDeadline)
    foreach ($role in @('api', 'watchdog')) {
        $marker = Join-Path $SandboxRoot "$role.json"
        if (Test-Path -LiteralPath $marker) {
            $record = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
            $process = Get-Process -Id $record.pid -ErrorAction SilentlyContinue
            $children += [pscustomobject]@{Role=$role; Pid=$record.pid; Alive=[bool]$process; Record=$record}
        }
    }
    $receipt = [ordered]@{
        Completed=$completed; Failure=$failure; ChildStarts=@($global:GoodQStartupTest.Starts)
        Children=$children; Messages=@($global:GoodQStartupTest.Messages); ServiceRequests=$global:GoodQStartupTest.ServiceRequests
        ForeignAlive=[bool]($ForeignPid -and (Get-Process -Id $ForeignPid -ErrorAction SilentlyContinue))
        SourceSha256=(Get-FileHash -LiteralPath $StartupScript -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $receipt | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath $ReceiptPath -Encoding utf8
} finally {
    # The legacy launcher owns PowerShell wrappers. Only collect Python children
    # whose parent is one of those exact test-owned wrapper process objects.
    foreach ($record in $children) {
        $process = CimCmdlets\Get-CimInstance Win32_Process -Filter "ProcessId=$($record.Pid)" -ErrorAction SilentlyContinue
        if ($process -and $process.ParentProcessId -in @($global:GoodQStartupTest.Owned | ForEach-Object Id)) {
            $child = Get-Process -Id $record.Pid -ErrorAction SilentlyContinue
            if ($child) { $child.Kill(); $child.WaitForExit(5000) | Out-Null; $child.Dispose() }
        }
    }
    foreach ($child in $global:GoodQStartupTest.Owned) {
        if (-not $child.HasExited) { $child.Kill(); $child.WaitForExit(5000) | Out-Null }
        $child.Dispose()
    }
}
