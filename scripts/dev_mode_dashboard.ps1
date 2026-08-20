[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('dev-on', 'dev-off')]
    [string] $Mode,

    [Parameter(Mandatory)]
    [ValidateSet('start', 'node', 'final')]
    [string] $Event,

    [string] $Node,

    [string] $State,

    [string] $Message,

    [switch] $NoColor
)

Set-StrictMode -Version Latest

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

function Write-DashboardLine {
    param(
        [Parameter(Mandatory)]
        [string] $Label,

        [Parameter(Mandatory)]
        [string] $Text
    )

    if ($NoColor) {
        Write-Output "$Label $Text"
        return
    }

    $color = @{
        '[READY]' = 'Green'
        '[INFO]' = 'Cyan'
        '[CHECK]' = 'White'
        '[WARN]' = 'Yellow'
        '[BLOCKED]' = 'Red'
    }[$Label]
    Write-Host $Label -ForegroundColor $color -NoNewline
    Write-Host " $Text"
}

function Get-StateLabel {
    param([Parameter(Mandatory)][string] $Value)

    switch ($Value.ToLowerInvariant()) {
        'pending' { '[INFO]' }
        'check' { '[CHECK]' }
        'ready' { '[READY]' }
        'released' { '[READY]' }
        'retained' { '[INFO]' }
        'warn' { '[WARN]' }
        'blocked' { '[BLOCKED]' }
        default { throw "Unsupported dashboard state: $Value" }
    }
}

if ($Event -eq 'node' -and [string]::IsNullOrWhiteSpace($Node)) {
    Write-Error 'Dashboard node events require -Node.'
    exit 1
}
if ($Event -in 'node', 'final' -and [string]::IsNullOrWhiteSpace($State)) {
    Write-Error "Dashboard $Event events require -State."
    exit 1
}

switch ($Event) {
    'start' {
        $title = if ($Mode -eq 'dev-on') { 'DEV ON / BUILD MODE' } else { 'DEV OFF / OPEN DESKTOP' }
        Write-Output '╔════════════════════════════════════════════════════╗'
        Write-Output "║ $title"
        Write-Output '╠════════════════════════════════════════════════════╣'
        Write-Output '[CONFIG]──○──[WSL AUDIO]──○──[vLLM]──○──[API]'
        Write-Output '                         └──[QDRANT]'
        Write-DashboardLine '[CHECK]' 'Awaiting verified state transitions.'
    }
    'node' {
        $suffix = if ([string]::IsNullOrWhiteSpace($Message)) { '' } else { " — $Message" }
        Write-DashboardLine (Get-StateLabel $State) "$Node$suffix"
    }
    'final' {
        $label = Get-StateLabel $State
        $title = if ($State -eq 'blocked') {
            if ($Mode -eq 'dev-on') { 'BUILD MODE BLOCKED' } else { 'OPEN DESKTOP BLOCKED' }
        } elseif ($Mode -eq 'dev-on') {
            'SYSTEM READY — BUILD MODE'
        } else {
            'OPEN DESKTOP — GPU SERVICES RELEASED'
        }
        Write-Output '╠════════════════════════════════════════════════════╣'
        Write-DashboardLine $label $title
        if (-not [string]::IsNullOrWhiteSpace($Message)) {
            Write-DashboardLine $label $Message
        }
        Write-Output '╚════════════════════════════════════════════════════╝'
    }
}
