# GoodQ4All developer startup. The canonical endpoint remains loopback:30000;
# an explicit port override supports isolated acceptance, never port fallback.
param(
    [ValidateRange(1, 65535)][int]$ApiPort = 30000,
    [ValidateRange(0.1, 300)][double]$StartupTimeoutSeconds = 60,
    [ValidateRange(0.1, 30)][double]$StabilizationSeconds = 2,
    # Explicit qualification mode; live shortcut selection is a separate gate.
    [switch]$Supervise,
    [ValidateRange(0.1, 60)][double]$HealthIntervalSeconds = 5,
    [ValidateRange(0, 10)][int]$MaxRestarts = 3,
    [ValidateRange(0.1, 60)][double]$RestartBackoffSeconds = 2,
    [ValidateRange(0.1, 86400)][double]$DrainTimeoutSeconds = 300,
    [string]$StopReceipt,
    # Dev Off discovers this checkout's surviving invocation, then waits for
    # the owner's terminal drain evidence. Explicit StopReceipt remains request-only.
    [switch]$StopCurrent,
    [switch]$CheckStart
)

$ErrorActionPreference = 'Stop'
$rootDir = $PSScriptRoot
function Initialize-GoodQLifecycleTypes {
    if ('GoodQ.RuntimeJobQuery' -as [type]) { return }
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
namespace GoodQ {
    public static class RuntimeJobQuery {
        [StructLayout(LayoutKind.Sequential)] struct Accounting {
            public long User, Kernel, PeriodUser, PeriodKernel;
            public uint PageFaults, Total, Active, Terminated;
        }
        [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
        static extern IntPtr OpenJobObject(uint access, bool inherit, string name);
        [DllImport("kernel32.dll", SetLastError=true)]
        static extern bool QueryInformationJobObject(IntPtr job, int kind, out Accounting info, uint size, IntPtr length);
        [DllImport("kernel32.dll", SetLastError=true)]
        static extern bool IsProcessInJob(IntPtr process, IntPtr job, out bool result);
        [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
        static IntPtr Open(string name) {
            IntPtr job = OpenJobObject(4, false, name);
            if (job == IntPtr.Zero) {
                int error = Marshal.GetLastWin32Error();
                if (error != 2) throw new Win32Exception(error);
            }
            return job;
        }
        public static bool Contains(string name, IntPtr process) {
            IntPtr job = Open(name);
            if (job == IntPtr.Zero) return false;
            try {
                bool result;
                if (!IsProcessInJob(process, job, out result)) throw new Win32Exception(Marshal.GetLastWin32Error());
                return result;
            } finally { CloseHandle(job); }
        }
        public static uint ActiveProcesses(string name) {
            IntPtr job = Open(name);
            if (job == IntPtr.Zero) return 0;
            try {
                Accounting info;
                if (!QueryInformationJobObject(job, 1, out info, (uint)Marshal.SizeOf(typeof(Accounting)), IntPtr.Zero))
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                return info.Active;
            } finally { CloseHandle(job); }
        }
    }
}
'@
}
function Assert-GoodQRuntimeAbsent {
    $listeners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -eq $ApiPort)
    $unmanaged = @(Get-CimInstance Win32_Process -Filter "name='python.exe'" -ErrorAction Stop |
        Where-Object { $_.CommandLine -match '(?i)(?:^|\s)-m\s+(?:api\.server|cli\.watchdog|cli\.dog)(?:\s|$)' })
    if ($listeners.Count -or $unmanaged.Count) {
        throw 'GoodQ processes or an API listener remain without a verified drain; preserve dependencies and inspect the owning runtime.'
    }
}
if ($StopCurrent -or $CheckStart) {
    if ($StopReceipt -or $Supervise -or ($StopCurrent -and $CheckStart)) { throw 'Select exactly one runtime control action.' }
    Initialize-GoodQLifecycleTypes
    $candidates = @()
    $armedSupervisors = @()
    # Reuse the existing per-invocation evidence; no latest-PID file or second
    # state writer. A newer historical receipt cannot override a live owner.
    foreach ($directory in @(Get-ChildItem -LiteralPath ([IO.Path]::GetTempPath()) -Directory -Filter 'goodq-startup-*')) {
        $path = Join-Path $directory.FullName 'supervisor.json'
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { $path = Join-Path $directory.FullName 'startup.json' }
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
        try { $record = [IO.File]::ReadAllText($path) | ConvertFrom-Json }
        catch { Write-Warning "Cannot read runtime receipt $path; it cannot establish ownership."; continue }
        if (-not $record.repository -or
            [IO.Path]::GetFullPath($record.repository) -ne [IO.Path]::GetFullPath($rootDir) -or
            $record.api_endpoint -ne "http://127.0.0.1:$ApiPort" -or
            $record.lifecycle_protocol -ne 'windows_event_job_v1' -or
            $record.stop_event -cnotmatch '^Local\\GoodQRuntime-[0-9a-f]{32}$') { continue }
        $active = $false
        foreach ($role in @('api', 'watchdog')) {
            $identity = $record.$role
            if (-not $identity) { $identity = @{pid=$record.($role + '_pid')} }
            if ($identity.pid -and [GoodQ.RuntimeJobQuery]::ActiveProcesses("$($record.stop_event).$role.$($identity.pid)")) {
                $active = $true
            }
        }
        if ($record.supervisor_pid -and $record.supervisor_started_at_utc -and
            -not ($record.state -eq 'stopped' -and $record.drain_verified -eq $true)) {
            try { $writer = [Diagnostics.Process]::GetProcessById([int]$record.supervisor_pid) }
            catch [ArgumentException] { $writer = $null }
            if ($writer) {
                try {
                    if (-not $writer.HasExited -and $writer.StartTime.ToUniversalTime().Ticks -eq
                        [DateTimeOffset]::Parse($record.supervisor_started_at_utc).UtcDateTime.Ticks) {
                        $armedSupervisors += $writer.Id
                    }
                } finally { $writer.Dispose() }
            }
        }
        if ($active) { $candidates += $path }
    }
    if ($CheckStart -and ($candidates.Count -or $armedSupervisors.Count)) {
        throw 'An existing supervisor or owned runtime remains; refusing competing startup.'
    }
    if ($StopCurrent) {
        if ($candidates.Count -gt 1 -or @($armedSupervisors | Sort-Object -Unique).Count -gt 1) {
            throw 'Multiple surviving GoodQ invocations found; refusing an ambiguous stop.'
        }
        if (-not $candidates.Count) {
            # A live owner can still launch/restart when no role is present. Its
            # PID/birth claim only blocks release; it never authorizes an event signal.
            if ($armedSupervisors.Count) {
                throw 'A live supervisor is starting or awaiting recovery; no owned role can attest drain yet. Dependencies are preserved.'
            }
            Assert-GoodQRuntimeAbsent
            Write-Host 'GoodQ runtime is already absent. No work-completion claim is made.'
            return
        }
        $StopReceipt = $candidates[0]
    }
}
if ($StopReceipt) {
    # Stop is a request to this receipt's invocation, never a process search or
    # startup action. It is also usable after the supervisor has failed/exited.
    $receipt = [IO.File]::ReadAllText([IO.Path]::GetFullPath($StopReceipt)) | ConvertFrom-Json
    if ([IO.Path]::GetFullPath($receipt.repository) -ne [IO.Path]::GetFullPath($rootDir) -or
        $receipt.lifecycle_protocol -ne 'windows_event_job_v1' -or
        $receipt.stop_event -cnotmatch '^Local\\GoodQRuntime-[0-9a-f]{32}$') {
        throw 'Stop receipt does not identify this repository and lifecycle protocol.'
    }
    Initialize-GoodQLifecycleTypes
    $matched = 0
    foreach ($role in @('api', 'watchdog')) {
        $identity = $receipt.$role
        if (-not $identity) {
            $identity = @{pid=$receipt.($role + '_pid'); started_at_utc=$receipt.($role + '_started_at_utc')}
        }
        if (-not $identity.pid) { continue }
        try { $child = [Diagnostics.Process]::GetProcessById([int]$identity.pid) }
        catch [ArgumentException] { continue } # This owner has already exited.
        try {
            $null = $child.Handle
            if ($child.HasExited) { continue }
            if ($child.StartTime.ToUniversalTime().Ticks -ne [DateTimeOffset]::Parse($identity.started_at_utc).UtcDateTime.Ticks) {
                throw 'Stop receipt process identity no longer matches; refusing request.'
            }
            if (-not [GoodQ.RuntimeJobQuery]::Contains("$($receipt.stop_event).$role.$($child.Id)", $child.Handle)) {
                throw 'Stop receipt event does not match the child lifecycle ownership.'
            }
            $matched++
        } finally { $child.Dispose() }
    }
    if (-not $matched) { throw 'Stop receipt has no surviving owned runtime.' }
    $event = [Threading.EventWaitHandle]::OpenExisting($receipt.stop_event)
    try { $null = $event.Set() } finally { $event.Dispose() }
    Write-Host 'Graceful stop requested. Completion requires a stopped receipt with drain_verified=true.'
    if ($StopCurrent) {
        $terminalPath = Join-Path (Split-Path -Parent $StopReceipt) 'supervisor.json'
        $drainClock = [Diagnostics.Stopwatch]::StartNew()
        do {
            if (Test-Path -LiteralPath $terminalPath -PathType Leaf) {
                $terminal = [IO.File]::ReadAllText($terminalPath) | ConvertFrom-Json
                if ($terminal.stop_event -ne $receipt.stop_event -or $terminal.repository -ne $receipt.repository) {
                    throw 'Runtime identity changed while waiting for drain; dependencies are preserved.'
                }
                if ($terminal.state -eq 'stopped' -and $terminal.drain_verified -eq $true) {
                    foreach ($role in @('api', 'watchdog')) {
                        if ([GoodQ.RuntimeJobQuery]::ActiveProcesses("$($terminal.stop_event).$role.$($terminal.$role.pid)")) {
                            throw 'A stopped receipt still has active descendants; dependencies are preserved.'
                        }
                    }
                    Assert-GoodQRuntimeAbsent
                    Write-Host 'GoodQ API and Watchdog drain verified; compute dependencies may now be released.'
                    return
                }
                if ($terminal.state -in @('failed', 'unsupervised')) {
                    throw 'Supervisor cannot attest a successful drain; preserve dependencies and inspect its receipt.'
                }
            }
            if ($drainClock.Elapsed.TotalSeconds -ge $DrainTimeoutSeconds) {
                throw 'Waiting for verified drain timed out; busy processes and compute dependencies are preserved.'
            }
            Start-Sleep -Milliseconds 100
        } while ($true)
    }
    return
}
$startupLogDir = Join-Path ([IO.Path]::GetTempPath()) ('goodq-startup-' + [Guid]::NewGuid().ToString('N'))
$stopEvent = $null
$stopEventName = $null
$startupDrainVerified = $false
$startupDrainReason = $null
$apiPid = $null
$watchdogPid = $null
$apiStartedAt = $null
$watchdogStartedAt = $null
$startupVerified = $false
function Write-GoodQReceiptText([string]$Path, [string]$Record) {
    $temporary = $Path + '.tmp'
    [IO.File]::WriteAllText($temporary, $Record, [Text.UTF8Encoding]::new($false))
    $publicationTimer = [Diagnostics.Stopwatch]::StartNew()
    $warned = $false
    while ($true) {
        try {
            # Windows PowerShell coerces $null to an empty .NET string. Use an
            # explicit null string for no backup; never remove the old receipt.
            if ([IO.File]::Exists($Path)) {
                [IO.File]::Replace($temporary, $Path, [System.Management.Automation.Language.NullString]::Value)
            } else { [IO.File]::Move($temporary, $Path) }
            return
        } catch {
            $code = $_.Exception.GetBaseException().HResult -band 0xffff
            # Concurrent Windows readers may briefly prevent replacement. These
            # errors retain both original names; other failures are not retried.
            if ($code -notin @(5, 32, 33, 1175) -or $publicationTimer.Elapsed.TotalSeconds -ge 1) { throw }
            if (-not $warned) {
                Write-Warning "Receipt replacement temporarily blocked (win32=$code); retrying for at most one second."
                $warned = $true
            }
            Start-Sleep -Milliseconds 50
        }
    }
}
function Write-GoodQStartupReceipt([string]$State, [string]$Reason) {
    $record = [ordered]@{
        state=$State; captured_at_utc=[DateTime]::UtcNow.ToString('o')
        repository=$rootDir; api_endpoint="http://127.0.0.1:$ApiPort"
        python_executable=$pyExe; api_pid=$apiPid; watchdog_pid=$watchdogPid
        supervisor_pid=$(if ($Supervise) { $PID } else { $null })
        supervisor_started_at_utc=$(if ($Supervise) { (Get-Process -Id $PID).StartTime.ToUniversalTime().ToString('o') } else { $null })
        api_started_at_utc=$apiStartedAt; watchdog_started_at_utc=$watchdogStartedAt
        ongoing_health_verified=$false; reason=$Reason
        lifecycle_protocol=$(if ($Supervise) { 'windows_event_job_v1' } else { $null }); stop_event=$stopEventName
        drain_verified=$startupDrainVerified; drain_reason=$startupDrainReason
    } | ConvertTo-Json
    $path = Join-Path $startupLogDir 'startup.json'
    Write-GoodQReceiptText $path $record
}
trap {
    $failure = $_
    try { if (-not $startupVerified) { Write-GoodQStartupReceipt 'failed' $failure.Exception.Message } }
    catch { Write-Warning "Could not persist startup failure: $($_.Exception.Message)" }
    throw $failure
}
[IO.Directory]::CreateDirectory($startupLogDir) | Out-Null
Write-Host "GoodQ startup logs: $startupLogDir"
. (Join-Path $rootDir 'scripts\_lib\interpreter_bindings.ps1')
if ((Get-GoodQCondaEnv) -ne 'goodq_core') {
    throw 'Developer startup requires the goodq_core interpreter binding.'
}
$pyExe = Get-GoodQPythonExe
if (-not [IO.Path]::IsPathRooted($pyExe) -or -not (Test-Path -LiteralPath $pyExe -PathType Leaf)) {
    throw 'The resolved goodq_core Python executable is unavailable; refusing PATH fallback.'
}

function Get-GoodQApiListeners {
    # Query errors must not masquerade as an unused port. Filtering the complete
    # listener table avoids the cmdlet's no-matching-port error on a cold start.
    Get-NetTCPConnection -State Listen -ErrorAction Stop |
        Where-Object LocalPort -eq $ApiPort
}

function Assert-GoodQChildRunning($Child, [string]$Role) {
    $Child.Refresh()
    if ($Child.HasExited) {
        throw "$Role exited during startup (exit=$($Child.ExitCode)). Logs: $startupLogDir"
    }
}

function Test-GoodQJobEmpty([string]$Role, $Child) {
    $Child.Refresh()
    if (-not $Child.HasExited) { return $false }
    return [GoodQ.RuntimeJobQuery]::ActiveProcesses("$stopEventName.$Role.$($Child.Id)") -eq 0
}

function Test-GoodQChildLifecycle([string]$Role, $Child) {
    return [GoodQ.RuntimeJobQuery]::Contains("$stopEventName.$Role.$($Child.Id)", $Child.Handle)
}

function Wait-GoodQStartupDrain {
    $null = $stopEvent.Set()
    $drainClock = [Diagnostics.Stopwatch]::StartNew()
    while ($true) {
        $pending = @($ownedChildren | Where-Object { -not $_.HasExited })
        $jobsEmpty = $true
        if ($apiChild -and -not (Test-GoodQJobEmpty 'api' $apiChild)) { $jobsEmpty = $false }
        if ($watchdogChild -and -not (Test-GoodQJobEmpty 'watchdog' $watchdogChild)) { $jobsEmpty = $false }
        if (-not $pending.Count -and $jobsEmpty) {
            if (@($ownedChildren | Where-Object ExitCode -ne 0).Count) {
                throw 'A startup child exited unsuccessfully; work completion is unverified.'
            }
            return
        }
        if ($drainClock.Elapsed.TotalSeconds -ge $DrainTimeoutSeconds) {
            throw 'Startup drain timed out; busy owned children are preserved.'
        }
        Start-Sleep -Milliseconds 100
    }
}

function Get-GoodQApiReadiness($Child) {
    Assert-GoodQChildRunning $Child 'API'
    $listeners = @(Get-GoodQApiListeners)
    if (@($listeners | Where-Object OwningProcess -ne $Child.Id).Count) {
        throw "Port $ApiPort acquired by another process during startup; refusing takeover."
    }
    if (-not @($listeners | Where-Object LocalAddress -eq '127.0.0.1').Count) {
        return @{Ready=$false; Detail='Owned API has not bound the exact loopback endpoint.'}
    }
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$ApiPort/" -TimeoutSec 2 -MaximumRedirection 0 -ErrorAction Stop
    } catch {
        return @{Ready=$false; Detail=$_.Exception.Message}
    }
    Assert-GoodQChildRunning $Child 'API'
    $listeners = @(Get-GoodQApiListeners)
    if (@($listeners | Where-Object OwningProcess -ne $Child.Id).Count) {
        throw "Port $ApiPort changed ownership during the health request."
    }
    $healthy = $response.StatusCode -eq 200 -and @($listeners | Where-Object LocalAddress -eq '127.0.0.1').Count -gt 0
    if ($Supervise -and $healthy -and -not (Test-GoodQChildLifecycle 'api' $Child)) {
        throw 'Responsive API lacks this invocation''s lifecycle ownership.'
    }
    return @{Ready=$healthy; Detail="HTTP status $($response.StatusCode); exact endpoint ownership rechecked."}
}

function Invoke-GoodQSupervision($ApiChild, $WatchdogChild) {
    $clock = [Diagnostics.Stopwatch]::StartNew()
    $roles = [ordered]@{
        api=@{Child=$ApiChild; Restarts=0; ExitObserved=$false; RetryAt=$null; Stabilizing=$false; Responsive=$true}
        watchdog=@{Child=$WatchdogChild; Restarts=0; ExitObserved=$false; RetryAt=$null; Stabilizing=$false; Responsive=$null}
    }
    $cycle = 0
    $lastState = $null
    $terminalWritten = $false
    $stopRequestedAt = $null
    $supervisorStartedAt = (Get-Process -Id $PID).StartTime.ToUniversalTime().ToString('o')
    foreach ($role in $roles.Keys) {
        $roles[$role].StartedAt = $roles[$role].Child.StartTime.ToUniversalTime().ToString('o')
        $roles[$role].ObservedAt = [DateTime]::UtcNow.ToString('o')
    }

    function Write-SupervisorEvent([string]$Event, [hashtable]$Detail) {
        $record = [ordered]@{
            event=$Event; captured_at_utc=[DateTime]::UtcNow.ToString('o')
            elapsed_seconds=$clock.Elapsed.TotalSeconds
        }
        foreach ($key in $Detail.Keys) { $record[$key] = $Detail[$key] }
        [IO.File]::AppendAllText((Join-Path $startupLogDir 'supervisor.events.jsonl'),
            (($record | ConvertTo-Json -Compress) + [Environment]::NewLine), [Text.UTF8Encoding]::new($false))
    }

    function Write-SupervisorReceipt([string]$State, [string]$Reason) {
        $record = [ordered]@{
            state=$State; reason=$Reason; captured_at_utc=[DateTime]::UtcNow.ToString('o')
            supervisor_pid=$PID; supervisor_started_at_utc=$supervisorStartedAt
            repository=$rootDir; python_executable=$pyExe; api_endpoint="http://127.0.0.1:$ApiPort"
            cycle=$cycle; model_readiness_verified=$false
            lifecycle_protocol='windows_event_job_v1'; stop_event=$stopEventName
            drain_verified=($State -eq 'stopped')
        }
        foreach ($role in $roles.Keys) {
            $entry = $roles[$role]
            $entry.Child.Refresh()
            $alive = -not $entry.Child.HasExited
            $record[$role] = [ordered]@{
                pid=$entry.Child.Id; started_at_utc=$entry.StartedAt; alive=$alive
                observed_at_utc=$entry.ObservedAt; restarts=$entry.Restarts
                responsive=$(if ($role -eq 'api') { $alive -and $entry.Responsive } else { $null })
            }
        }
        $path = Join-Path $startupLogDir 'supervisor.json'
        Write-GoodQReceiptText $path ($record | ConvertTo-Json -Depth 4)
    }

    try {
        while ($true) {
            $cycle++
            if ($stopEvent.WaitOne(0)) {
                if ($null -eq $stopRequestedAt) {
                    $stopRequestedAt = $clock.Elapsed.TotalSeconds
                    Write-SupervisorEvent 'stop_requested' @{}
                }
                $drained = $true
                foreach ($role in $roles.Keys) {
                    $roles[$role].ObservedAt = [DateTime]::UtcNow.ToString('o')
                    if (-not (Test-GoodQJobEmpty $role $roles[$role].Child)) { $drained = $false }
                }
                if ($drained) {
                    if (@($roles.Values | Where-Object { $_.Child.ExitCode -ne 0 }).Count) {
                        throw 'A child exited unsuccessfully during drain; work completion is unverified.'
                    }
                    Write-SupervisorReceipt 'stopped' 'Both roles exited successfully and their Windows jobs are empty.'
                    $terminalWritten = $true
                    return
                }
                Write-SupervisorReceipt 'stopping' 'Stop requested; waiting for active work and owned descendants.'
                if ($clock.Elapsed.TotalSeconds - $stopRequestedAt -ge $DrainTimeoutSeconds) {
                    throw 'Active-work drain timed out; busy owned children are preserved.'
                }
                Start-Sleep -Milliseconds 100
                continue # Never restart a role once stop has been requested.
            }
            # Observe every child before considering any restart. Backoff is a
            # deadline, not a blocking sleep that hides the other child's exit.
            foreach ($role in $roles.Keys) {
                $entry = $roles[$role]
                $entry.Child.Refresh()
                $entry.ObservedAt = [DateTime]::UtcNow.ToString('o')
                if ($entry.Child.HasExited -and -not $entry.ExitObserved) {
                    $entry.ExitObserved = $true
                    $entry.Responsive = $false
                    Write-SupervisorEvent 'child_exit' @{role=$role; pid=$entry.Child.Id; exit_code=$entry.Child.ExitCode}
                    if ($entry.Restarts -ge $MaxRestarts) {
                        throw "$role exhausted its restart budget ($MaxRestarts); running peers are preserved."
                    }
                    $delay = [Math]::Min([double]60, $RestartBackoffSeconds * [Math]::Pow(2, $entry.Restarts))
                    $entry.RetryAt = $clock.Elapsed.TotalSeconds + $delay
                    Write-SupervisorEvent 'restart_scheduled' @{role=$role; pid=$entry.Child.Id; delay_seconds=$delay}
                }
            }
            foreach ($role in $roles.Keys) {
                $entry = $roles[$role]
                if ($null -eq $entry.RetryAt -or $clock.Elapsed.TotalSeconds -lt $entry.RetryAt) { continue }
                if (-not (Test-GoodQJobEmpty $role $entry.Child)) {
                    if ($clock.Elapsed.TotalSeconds - $entry.RetryAt -ge $StartupTimeoutSeconds) {
                        throw "$role descendants did not exit; replacement is blocked."
                    }
                    continue
                }
                Write-SupervisorEvent 'descendants_exited' @{role=$role; pid=$entry.Child.Id}
                if ($role -eq 'api') {
                    $listeners = @(Get-GoodQApiListeners)
                    if ($listeners.Count) {
                        $owners = ($listeners.OwningProcess | Sort-Object -Unique) -join ', '
                        throw "Port $ApiPort is owned by PID(s) $owners before API restart; refusing takeover."
                    }
                } elseif ($roles.api.Child.HasExited -or -not $roles.api.Responsive -or $roles.api.Stabilizing) {
                    # Keep the initial API-before-Watchdog readiness dependency.
                    continue
                }
                $entry.Restarts++
                $module = if ($role -eq 'api') { 'api.server' } else { 'cli.watchdog' }
                $stdout = Join-Path $startupLogDir "$role.restart-$($entry.Restarts).stdout.log"
                $stderr = Join-Path $startupLogDir "$role.restart-$($entry.Restarts).stderr.log"
                $child = Start-Process -FilePath $pyExe -ArgumentList @('-u', '-m', $module) -WorkingDirectory $rootDir -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr -ErrorAction Stop
                $ownedChildren.Add($child)
                $null = $child.Handle
                $entry.Child = $child
                $entry.StartedAt = $child.StartTime.ToUniversalTime().ToString('o')
                $entry.ObservedAt = [DateTime]::UtcNow.ToString('o')
                $entry.ExitObserved = $false
                $entry.RetryAt = $null
                $entry.Stabilizing = $true
                $entry.LaunchedAt = $clock.Elapsed.TotalSeconds
                $entry.HealthySince = $null
                Write-SupervisorEvent 'child_started' @{role=$role; pid=$child.Id; attempt=$entry.Restarts; stdout=$stdout; stderr=$stderr}
            }

            $detail = 'Owned API responds; owned Watchdog process is alive. Model and active-work health are separate.'
            if (-not $roles.api.Child.HasExited) {
                try { $readiness = Get-GoodQApiReadiness $roles.api.Child }
                catch {
                    # An exit can occur inside the HTTP/owner recheck window.
                    # Let the same exit observer and retry budget handle it.
                    $roles.api.Child.Refresh()
                    if ($roles.api.Child.HasExited) {
                        $roles.api.Responsive = $false
                        continue
                    }
                    throw
                }
                $roles.api.Responsive = $readiness.Ready
                $roles.api.ObservedAt = [DateTime]::UtcNow.ToString('o')
                $detail = $readiness.Detail
            }
            foreach ($role in $roles.Keys) {
                $entry = $roles[$role]
                if ($entry.Stabilizing -and -not $entry.Child.HasExited) {
                    if (($role -eq 'watchdog' -or $entry.Responsive) -and (Test-GoodQChildLifecycle $role $entry.Child)) {
                        if ($null -eq $entry.HealthySince) { $entry.HealthySince = $clock.Elapsed.TotalSeconds }
                        if ($clock.Elapsed.TotalSeconds - $entry.HealthySince -ge $StabilizationSeconds) {
                            $entry.Stabilizing = $false
                        }
                    } else { $entry.HealthySince = $null }
                    if ($entry.Stabilizing -and $clock.Elapsed.TotalSeconds - $entry.LaunchedAt -ge $StartupTimeoutSeconds) {
                        throw "$role restart readiness timed out; running children are preserved. $detail"
                    }
                }
            }
            $state = if ($roles.api.Child.HasExited -or $roles.watchdog.Child.HasExited) { 'backoff' }
                elseif (-not $roles.api.Responsive) { 'degraded' }
                elseif ($roles.api.Stabilizing -or $roles.watchdog.Stabilizing) { 'recovering' }
                else { 'monitoring' }
            if ($state -ne $lastState) {
                Write-SupervisorEvent 'health_changed' @{state=$state; detail=$detail}
                $lastState = $state
            }
            # This is a dated observation, never a timeless readiness flag.
            Write-SupervisorReceipt $state $detail
            Start-Sleep -Milliseconds ([int]($HealthIntervalSeconds * 1000))
        }
    } catch {
        $supervisionFailure = $_
        try {
            Write-SupervisorEvent 'supervision_failed' @{reason=$supervisionFailure.Exception.Message}
            Write-SupervisorReceipt 'failed' $supervisionFailure.Exception.Message
        } catch {
            Write-Warning "Could not persist supervisor failure: $($_.Exception.Message). Original failure: $($supervisionFailure.Exception.Message)"
        }
        $terminalWritten = $true
        throw $supervisionFailure
    } finally {
        if (-not $terminalWritten) {
            Write-SupervisorReceipt 'unsupervised' 'Supervision stopped; remaining children were not drained or terminated.'
        }
    }
}

$existing = @(Get-GoodQApiListeners)
if ($existing.Count) {
    $owners = ($existing.OwningProcess | Sort-Object -Unique) -join ', '
    throw "Port $ApiPort is already owned by PID(s) $owners; refusing to stop or adopt existing processes."
}
if ($CheckStart) {
    Assert-GoodQRuntimeAbsent
    Write-Host 'GoodQ interpreter and startup ownership preflight passed; no services were started.'
    return
}

$ownedChildren = [Collections.Generic.List[Diagnostics.Process]]::new()
$previousHost = $env:GOODQ_API_HOST
$previousPort = $env:GOODQ_API_PORT
$previousStopEvent = $env:GOODQ_RUNTIME_STOP_EVENT
try {
    # Clear inherited control bindings; only this explicit invocation may create
    # the event passed to its children. No global environment changes are made.
    $env:GOODQ_RUNTIME_STOP_EVENT = $null
    if ($Supervise) {
        Initialize-GoodQLifecycleTypes
        $stopEventName = 'Local\GoodQRuntime-' + [Guid]::NewGuid().ToString('N')
        $created = $false
        $stopEvent = [Threading.EventWaitHandle]::new($false, [Threading.EventResetMode]::ManualReset, $stopEventName, [ref]$created)
        if (-not $created) { throw 'Runtime stop event already exists; refusing adoption.' }
        $env:GOODQ_RUNTIME_STOP_EVENT = $stopEventName
        Write-GoodQStartupReceipt 'starting' 'Supervisor is armed; dependencies and runtime children are not yet started.'
    }
    # A running store needs query access only; requesting SERVICE_START can fail
    # for an ordinary logon even though the required dependency is available.
    if ((Get-Service -Name 'GoodQ_Qdrant' -ErrorAction Stop).Status -ne 'Running') {
        Start-Service -Name 'GoodQ_Qdrant' -ErrorAction Stop
    }
    # Bind the actual children to the same endpoint the launcher verifies.
    $env:GOODQ_API_HOST = '127.0.0.1'
    $env:GOODQ_API_PORT = [string]$ApiPort
    $apiChild = Start-Process -FilePath $pyExe -ArgumentList @('-u', '-m', 'api.server') -WorkingDirectory $rootDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $startupLogDir 'api.stdout.log') -RedirectStandardError (Join-Path $startupLogDir 'api.stderr.log') -ErrorAction Stop
    $ownedChildren.Add($apiChild)
    # Retain the process handle, not a shell wrapper or a rediscovered PID.
    $null = $apiChild.Handle
    $apiPid = $apiChild.Id
    $apiStartedAt = $apiChild.StartTime.ToUniversalTime().ToString('o')
    if ($Supervise) { Write-GoodQStartupReceipt 'starting' 'API process started; readiness and drain are unverified.' }
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $healthySince = $null
    do {
        if ($Supervise -and $stopEvent.WaitOne(0)) { throw 'Stop requested during startup.' }
        $readiness = Get-GoodQApiReadiness $apiChild
        if ($readiness.Ready) {
            if ($null -eq $healthySince) { $healthySince = $timer.Elapsed.TotalSeconds }
            if ($timer.Elapsed.TotalSeconds - $healthySince -ge $StabilizationSeconds) { break }
        } else {
            $healthySince = $null
        }
        if ($timer.Elapsed.TotalSeconds -ge $StartupTimeoutSeconds) {
            throw "API startup health timed out on port $ApiPort. $($readiness.Detail) Logs: $startupLogDir"
        }
        Start-Sleep -Milliseconds 100
    } while ($true)

    $watchdogChild = Start-Process -FilePath $pyExe -ArgumentList @('-u', '-m', 'cli.watchdog') -WorkingDirectory $rootDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $startupLogDir 'watchdog.stdout.log') -RedirectStandardError (Join-Path $startupLogDir 'watchdog.stderr.log') -ErrorAction Stop
    $ownedChildren.Add($watchdogChild)
    $null = $watchdogChild.Handle
    $watchdogPid = $watchdogChild.Id
    $watchdogStartedAt = $watchdogChild.StartTime.ToUniversalTime().ToString('o')
    if ($Supervise) { Write-GoodQStartupReceipt 'starting' 'Both roles started; readiness and drain are unverified.' }
    $timer.Restart()
    $watchdogHealthySince = $null
    do {
        if ($Supervise -and $stopEvent.WaitOne(0)) { throw 'Stop requested during startup.' }
        Assert-GoodQChildRunning $watchdogChild 'Watchdog'
        $readiness = Get-GoodQApiReadiness $apiChild
        if (-not $readiness.Ready) {
            throw "API lost startup health while Watchdog was starting. $($readiness.Detail)"
        }
        Assert-GoodQChildRunning $watchdogChild 'Watchdog'
        if (-not $Supervise -or (Test-GoodQChildLifecycle 'watchdog' $watchdogChild)) {
            if ($null -eq $watchdogHealthySince) { $watchdogHealthySince = $timer.Elapsed.TotalSeconds }
            if ($timer.Elapsed.TotalSeconds - $watchdogHealthySince -ge $StabilizationSeconds) { break }
        } else { $watchdogHealthySince = $null }
        if ($timer.Elapsed.TotalSeconds -ge $StartupTimeoutSeconds) {
            throw 'Watchdog lifecycle ownership did not become ready during startup.'
        }
        Start-Sleep -Milliseconds 100
    } while ($true)
    Write-GoodQStartupReceipt 'startup_verified' 'Owned API startup health and Watchdog liveness passed the bounded startup window.'
    $startupVerified = $true
    Write-Host "API startup health verified (PID $($apiChild.Id)); Watchdog remains running (PID $($watchdogChild.Id)). Ongoing health and recovery are not established by this startup check."
    if ($Supervise) { Invoke-GoodQSupervision $apiChild $watchdogChild }
} catch {
    $startupFailure = $_
    if ($startupVerified) {
        # A working peer may own ingestion. Startup rollback is not a qualified
        # active-job shutdown protocol, so never apply it after startup passed.
        Write-Warning "Supervision failed; running owned children are preserved. Logs: $startupLogDir"
        throw $startupFailure
    }
    if ($Supervise -and $stopEvent) {
        try {
            Wait-GoodQStartupDrain
            $startupDrainVerified = $true
            $startupDrainReason = 'Owned startup children exited successfully and their Windows jobs are empty.'
        } catch {
            $startupDrainReason = $_.Exception.Message
            Write-Warning $startupDrainReason
        }
        throw $startupFailure
    }
    # Roll back only process objects created by this invocation. Never search
    # names, kill a port owner, or touch another instance's Watchdog lock.
    for ($i = $ownedChildren.Count - 1; $i -ge 0; $i--) {
        $child = $ownedChildren[$i]
        try {
            if (-not $child.HasExited) {
                $child.Kill()
                if (-not $child.WaitForExit(5000)) { Write-Warning "Owned PID $($child.Id) did not exit during startup rollback." }
            }
        } catch {
            Write-Warning "Could not stop owned startup child PID $($child.Id): $($_.Exception.Message)"
        }
    }
    throw $startupFailure
} finally {
    $env:GOODQ_API_HOST = $previousHost
    $env:GOODQ_API_PORT = $previousPort
    $env:GOODQ_RUNTIME_STOP_EVENT = $previousStopEvent
    if ($stopEvent) { $stopEvent.Dispose() }
    foreach ($child in $ownedChildren) { $child.Dispose() }
}
