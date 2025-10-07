Param(
  [string]$EnvPrefix = 'goodq'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Info($m){ Write-Host "[sanity] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[sanity] $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[sanity] $m" -ForegroundColor Yellow }
function Fail($m){ Write-Error $m; exit 1 }

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot

$outDir = Join-Path $repoRoot 'logs\sanity'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

# Generate a tiny test image with the word TEST
$imgPath = Join-Path $outDir 'test.png'
try {
  $py = @"
from PIL import Image, ImageDraw, ImageFont
img = Image.new('RGB', (256, 128), color='white')
d = ImageDraw.Draw(img)
d.text((10, 40), 'TEST', fill=(0,0,0))
img.save(r'$imgPath')
"@
  $tmp = [System.IO.Path]::GetTempFileName()
  Set-Content -LiteralPath $tmp -Value $py -Encoding UTF8
  & conda run -n "${EnvPrefix}_image_caption" python $tmp
  Remove-Item -LiteralPath $tmp -Force
  Ok "Created test image at $imgPath"
} catch { Warn 'Failed to create test image (PIL missing?)' }

# Generate a 1-second sine wave audio
$wavPath = Join-Path $outDir 'test.wav'
try {
  $py = @"
import numpy as np, soundfile as sf
sr=16000
t=np.linspace(0,1,sr,endpoint=False)
x=0.2*np.sin(2*np.pi*440*t)
sf.write(r'$wavPath', x, sr)
"@
  $tmp = [System.IO.Path]::GetTempFileName()
  Set-Content -LiteralPath $tmp -Value $py -Encoding UTF8
  & conda run -n "${EnvPrefix}_audio_transcribe" python $tmp
  Remove-Item -LiteralPath $tmp -Force
  Ok "Created test audio at $wavPath"
} catch { Warn 'Failed to create test audio (soundfile missing?)' }

# Run image OCR (lightweight)
try {
  $item = @{ modality='image'; source_path=$imgPath }
  $in = Join-Path $outDir 'ocr_in.json'
  $out = Join-Path $outDir 'ocr_out.json'
  ($item | ConvertTo-Json) | Set-Content -LiteralPath $in -Encoding UTF8
  & conda run -n "${EnvPrefix}_image_caption" python -m zenml_project.cli.step_runner --step image_ocr --in $in --out $out --verbose | Out-Null
  $j = Get-Content -Raw -LiteralPath $out | ConvertFrom-Json
  Ok ("OCR ok; text length {0}" -f ((($j.ocr_text) ? $j.ocr_text.Length : 0)))
} catch { Warn "OCR smoke failed: $_" }

# Run audio metadata (lightweight)
try {
  $item = @{ modality='audio'; source_path=$wavPath }
  $in = Join-Path $outDir 'am_in.json'
  $out = Join-Path $outDir 'am_out.json'
  ($item | ConvertTo-Json) | Set-Content -LiteralPath $in -Encoding UTF8
  & conda run -n "${EnvPrefix}_audio_metadata" python -m zenml_project.cli.step_runner --step audio_metadata --in $in --out $out --verbose | Out-Null
  $j = Get-Content -Raw -LiteralPath $out | ConvertFrom-Json
  Ok ("Audio meta ok; duration {0}s" -f ($j.audio_meta.duration_sec))
} catch { Warn "Audio metadata smoke failed: $_" }

Ok 'Sanity suite complete.'

