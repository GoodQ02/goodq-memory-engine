Param(
  [string]$OutDir = 'logs/gallery'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Info($m){ Write-Host "[gallery] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[gallery] $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[gallery] $m" -ForegroundColor Yellow }
function Fail($m){ Write-Error $m; exit 1 }

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot

$jsonPath = Join-Path $repoRoot 'logs/video_ingest_results.json'
if (-not (Test-Path $jsonPath)) { Fail 'No video_ingest_results.json found' }
$data = Get-Content -Raw -LiteralPath $jsonPath | ConvertFrom-Json
$entry = if ($data -is [System.Array]) { $data[-1] } else { $data }
$videoHash = $entry.video_hash
if (-not $videoHash) { $videoHash = (Get-Random) }
$outBase = Join-Path $repoRoot $OutDir
$dir = Join-Path $outBase $videoHash
New-Item -ItemType Directory -Force -Path $dir | Out-Null

$html = @()
$html += '<!doctype html><html><head><meta charset="utf-8"><title>Scene Gallery</title>'
$html += '<style>body{font-family:sans-serif;} .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px;} .card{border:1px solid #ccc;padding:8px;border-radius:6px;} img{width:100%;height:auto;border-radius:4px;}</style>'
$html += '</head><body>'
$html += ("<h1>Scene Gallery – {0}</h1>" -f ($entry.video ?? '(unknown)'))
$html += '<div class="grid">'
foreach ($sc in @($entry.scenes)) {
  $thumb = $sc.thumb_path
  $meta = "Duration: {0:N1}s – Confidence: {1:N2}" -f ([double]$sc.duration), ([double]$sc.confidence)
  $html += '<div class="card">'
  if ($thumb -and (Test-Path $thumb)) {
    $rel = Resolve-Path -LiteralPath $thumb
    $html += ("<img src='file:///{0}' alt='scene'/>" -f ($rel -replace '\\','/'))
  } else {
    $html += '<div style="width:100%;height:180px;background:#eee;display:flex;align-items:center;justify-content:center;color:#888">(no thumbnail)</div>'
  }
  $html += ("<div><b>{0:N1}-{1:N1}s</b></div>" -f ([double]$sc.start), ([double]$sc.end))
  $html += ("<div>{0}</div>" -f $meta)
  $tags = ($sc.tags -join ', ')
  if ($tags) { $html += ("<div>Tags: {0}</div>" -f $tags) }
  $ents = ($sc.entities -join ', ')
  if ($ents) { $html += ("<div>Entities: {0}</div>" -f $ents) }
  $html += '</div>'
}
$html += '</div></body></html>'

Set-Content -LiteralPath (Join-Path $dir 'index.html') -Value ($html -join "`n") -Encoding UTF8
Ok ("Wrote gallery to {0}" -f (Join-Path $dir 'index.html'))

