Param(
  [string]$EnvPrefix = 'goodq'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Note($m){ Write-Host "[test] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[test] $m" -ForegroundColor Green }
function Fail($m){ Write-Error $m; exit 1 }

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot

$envName = "${EnvPrefix}_audio_metadata"

# Prepare temp item with transcript and segments
$tmpDir = New-Item -ItemType Directory -Path ([System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), [System.IO.Path]::GetRandomFileName()))
$inPath = Join-Path $tmpDir 'in.json'
$outPath = Join-Path $tmpDir 'out.json'
$cfgPath = Join-Path $tmpDir 'cfg.json'

$item = @{
  source_path = 'L:\\goodq4all\\import_inbox\\test_me.mp3'
  modality = 'audio'
  transcript = 'We sang happy birthday last night at 7:30 pm. Merry Christmas everyone!'
  transcript_meta = @{ segments = @(@{ start = 10.5; end = 14.0; text = 'happy birthday everyone' }) }
}
(ConvertTo-Json $item -Depth 10) | Set-Content -LiteralPath $inPath -Encoding UTF8
$cfgJson = '{"paths":{"log_dir":"L:\\GoodQ_Data\\logs"}}'
Set-Content -LiteralPath $cfgPath -Value $cfgJson -Encoding UTF8

Note 'Run audio_time_hints'
$py1 = @"
import sys
sys.path.insert(0, "L:\\\\")
from steps.cli.step_runner import main as run
sys.argv = [
    'step_runner',
    '--step','audio_time_hints',
    '--in', r"$inPath",
    '--out', r"$outPath",
    '--cfg', r"$cfgPath",
]
run()
"@
$tmpPy1 = [System.IO.Path]::GetTempFileName()
Set-Content -LiteralPath $tmpPy1 -Value $py1 -Encoding UTF8
& conda run -n $envName python $tmpPy1
if (-not (Test-Path $outPath)) { Fail 'audio_time_hints produced no output' }
$res1 = Get-Content -Raw $outPath | ConvertFrom-Json
if (-not $res1.time_hints) { Fail 'audio_time_hints missing time_hints' }
Ok 'audio_time_hints returned time_hints'

Note 'Run audio_music_events'
Remove-Item -LiteralPath $outPath -Force -ErrorAction SilentlyContinue
$py2 = @"
import sys
sys.path.insert(0, "L:\\\\")
from steps.cli.step_runner import main as run
sys.argv = [
    'step_runner',
    '--step','audio_music_events',
    '--in', r"$inPath",
    '--out', r"$outPath",
    '--cfg', r"$cfgPath",
]
run()
"@
$tmpPy2 = [System.IO.Path]::GetTempFileName()
Set-Content -LiteralPath $tmpPy2 -Value $py2 -Encoding UTF8
& conda run -n $envName python $tmpPy2
if (-not (Test-Path $outPath)) { Fail 'audio_music_events produced no output' }
$res2 = Get-Content -Raw $outPath | ConvertFrom-Json
if ($null -eq $res2.music_events) { Fail 'audio_music_events missing music_events' }
Ok 'audio_music_events returned events'

# Check step_runs.csv got entries (using the same log dir used for the run)
$logDir = 'L:\\GoodQ_Data\\logs'
if (-not (Test-Path $logDir)) { Fail "log dir not found: $logDir" }
$csv = Join-Path $logDir 'step_runs.csv'
if (-not (Test-Path $csv)) { Fail 'step_runs.csv missing' }
$tail = Get-Content $csv -Tail 5
if (-not ($tail -match 'audio_time_hints' -and $tail -match 'audio_music_events')) {
  Fail 'step_runs.csv does not contain both test steps'
}
Ok 'step_runs.csv contains entries for both steps'

Remove-Item -LiteralPath $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
Ok 'Audio steps smoke test passed.'


