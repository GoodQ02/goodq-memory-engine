Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Info($m){ Write-Host "[conda] $m" -ForegroundColor Cyan }
function Fail($m){ Write-Error $m; exit 1 }

if (-not (Get-Command conda -ErrorAction SilentlyContinue)) { Fail 'conda not found' }

Info 'Conda info'
& conda info

Info 'Conda environments'
& conda env list

