param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$bindings = Join-Path $repoRoot "scripts\_lib\interpreter_bindings.ps1"
. $bindings

$condaExe = Get-GoodQCondaExe
$condaEnv = Get-GoodQCondaEnv
$localTemp = Join-Path $repoRoot "tmp\conda_run"
New-Item -ItemType Directory -Force -Path $localTemp | Out-Null

$previousTemp = $env:TEMP
$previousTmp = $env:TMP

try {
    # Scope temp isolation to this process so conda's launch-time files avoid shared Windows TEMP contention.
    $env:TEMP = $localTemp
    $env:TMP = $localTemp

    $argsToPass = @("run", "--no-capture-output", "-n", $condaEnv, "python", "-m", "pytest")
    if ($PytestArgs -and $PytestArgs.Count -gt 0) {
        $argsToPass += $PytestArgs
    } else {
        $argsToPass += "-q"
    }

    & $condaExe @argsToPass
    exit $LASTEXITCODE
}
finally {
    $env:TEMP = $previousTemp
    $env:TMP = $previousTmp
}
