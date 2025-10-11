Param(
  [switch]$UseZenMLArtifacts,
  [switch]$Refresh
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function H1($m){ Write-Host "== $m ==" -ForegroundColor Cyan }
function Info($m){ Write-Host "[cc] $m" -ForegroundColor Cyan }
function Warn($m){ Write-Host "[cc] $m" -ForegroundColor Yellow }

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot

function Read-PathsYaml {
  $f = 'configs/paths.yaml'
  $raw = Get-Content -LiteralPath $f -Raw
  $o = @{}
  foreach ($line in $raw -split "`n") {
    if ($line -match '^\s*([A-Za-z0-9_]+):\s*"(.*)"\s*$') {
      $o[$matches[1]] = $matches[2]
    }
  }
  return $o
}

function Show-GPU {
  H1 'GPU'
  if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    try {
      & nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv,noheader,nounits
    } catch {
      & nvidia-smi
    }
  } else {
    Warn 'nvidia-smi not found'
  }
}

function Show-DBAndFAISS {
  H1 'DB / FAISS'
  $p = Read-PathsYaml
  $db = $p['db_path']
  if ($db -and (Test-Path $db)) {
    try {
      $pyScript = @'
import sqlite3, sys, json
p = sys.argv[1]
try:
  con = sqlite3.connect(p)
  cur = con.cursor()
  cur.execute('SELECT COUNT(*) FROM embeddings'); e = cur.fetchone()[0]
  cur.execute('SELECT COUNT(*) FROM links'); l = cur.fetchone()[0]
  con.close()
  print(json.dumps({'embeddings': int(e), 'links': int(l)}))
except Exception:
  print(json.dumps({'embeddings': 0, 'links': 0}))
'@
      $tmpFile = [System.IO.Path]::GetTempFileName()
      Set-Content -LiteralPath $tmpFile -Value $pyScript -Encoding UTF8
      try {
        $out = & conda run -n goodq_zenml python $tmpFile $db
        Write-Host ("DB: {0}" -f $out.Trim())
      } finally {
        Remove-Item -LiteralPath $tmpFile -Force -ErrorAction SilentlyContinue
      }
    } catch { Warn 'DB query failed' }
  } else {
    Warn 'DB not found'
  }
  function _faiss($env,$path){
    if (-not $path) { return 'n/a' }
    if (-not (Test-Path $path)) { return 'missing' }
    try {
      $pyScript = @'
import faiss, sys
try:
  idx = faiss.read_index(sys.argv[1]); print(idx.ntotal)
except Exception:
  print('err')
'@
      $tmpFile = [System.IO.Path]::GetTempFileName()
      Set-Content -LiteralPath $tmpFile -Value $pyScript -Encoding UTF8
      try {
        $n = & conda run -n $env python $tmpFile $path
        if ($n) { return $n.Trim() } else { return 'err' }
      } finally {
        Remove-Item -LiteralPath $tmpFile -Force -ErrorAction SilentlyContinue
      }
    } catch { return 'err' }
  }
  $text = _faiss 'goodq_text_embed' $p['faiss_index_path']
  $dino = _faiss 'goodq_image_caption' $p['faiss_dino_path']
  $clip = _faiss 'goodq_image_caption' $p['faiss_clip_path']
  $audio = _faiss 'goodq_audio_embed' $p['faiss_audio_path']
  Write-Host ("FAISS → text:{0} dino:{1} clip:{2} audio:{3}" -f $text,$dino,$clip,$audio)
}

function Show-HotCache {
  H1 'Hot Cache (HF/Torch)'
  $hf = [Environment]::GetEnvironmentVariable('HF_HOME','User'); if (-not $hf) { $hf = [Environment]::GetEnvironmentVariable('HF_HOME','Process') }
  $th = [Environment]::GetEnvironmentVariable('TORCH_HOME','User'); if (-not $th) { $th = [Environment]::GetEnvironmentVariable('TORCH_HOME','Process') }
  function SizeOf($p){ try { (Get-ChildItem -Recurse -ErrorAction SilentlyContinue -Force -LiteralPath $p | Measure-Object -Property Length -Sum).Sum } catch { 0 } }
  if ($hf -and (Test-Path $hf)) { Write-Host ("HF_HOME: {0} bytes" -f (SizeOf $hf)) } else { Warn 'HF_HOME not set/missing' }
  if ($th -and (Test-Path $th)) { Write-Host ("TORCH_HOME: {0} bytes" -f (SizeOf $th)) } else { Warn 'TORCH_HOME not set/missing' }
}

function Show-LastScenePeek {
  H1 'Last Scene Peek'
  $path = Join-Path $repoRoot 'logs/video_ingest_results.json'
  if (-not (Test-Path $path)) { Warn 'No video summaries yet'; return }
  try { $json = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json } catch { Warn 'Failed to read video summaries'; return }
  $entry = if ($json -is [System.Array]) { $json[-1] } else { $json }
  $scenes = @($entry.scenes)
  if (-not $scenes -or $scenes.Count -eq 0) { Warn 'No scenes'; return }
  $sc = $scenes[-1]
  
  # Check for confidence property
  $conf = if ($sc.PSObject.Properties.Name -contains 'confidence') { [double]$sc.confidence } else { 0.0 }
  Write-Host ("Scene {0:N1}-{1:N1}s conf={2:N2}" -f ([double]$sc.start), ([double]$sc.end), $conf)
  
  if ($sc.PSObject.Properties.Name -contains 'tags' -and $sc.tags) { 
    Write-Host ("  tags: {0}" -f ($sc.tags -join ', ')) 
  }
  if ($sc.PSObject.Properties.Name -contains 'entities' -and $sc.entities) { 
    Write-Host ("  entities: {0}" -f ($sc.entities -join ', ')) 
  }
}
function Show-LatestExport {
  H1 'Latest Export'
  $base = 'L:\\_DATA\\GoodQ_Data\\exports'
  if (-not (Test-Path $base)) { Warn 'No export directory found'; return }
  $dir = Get-ChildItem -LiteralPath $base -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $dir) { Warn 'No exports yet'; return }
  Write-Host ("Dir: {0}" -f $dir.FullName)
  $summary = Join-Path $dir.FullName 'summary.json'
  if (Test-Path $summary) { Write-Host ("summary.json: {0} bytes" -f (Get-Item $summary).Length) }
  Get-ChildItem -LiteralPath $dir.FullName -Filter 'faiss_*.index' | ForEach-Object { Write-Host ("index: {0} bytes" -f $_.Length) }
}

function Show-VideoSummary {
  H1 'Video Summary'
  $path = Join-Path $repoRoot 'logs/video_ingest_results.json'
  if (-not (Test-Path $path)) { Warn 'No video summaries yet'; return }
  try {
    $json = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
  } catch {
    Warn 'Failed to read video summaries'; return
  }
  if (-not $json) { Warn 'Video summary empty'; return }
  $entry = if ($json -is [System.Array]) { $json[-1] } else { $json }
  $video = if ($entry.video) { $entry.video } else { '(unknown)' }
  Write-Host ("Video: {0}" -f $video)
  if ($entry.duration_sec) {
    try {
      $dur = [double]$entry.duration_sec
      Write-Host ("Duration: {0:N1}s" -f $dur)
    } catch {}
  }
  $frameCount = @($entry.frames).Count
  $sceneCount = @($entry.scenes).Count
  Write-Host ("Frames: {0}  Scenes: {1}" -f $frameCount, $sceneCount)
  $audio = $entry.audio
  if ($audio) {
    $clapMeta = $audio.clap_meta
    if ($clapMeta) {
      $status = if ($clapMeta.status) { $clapMeta.status } else { 'unknown' }
      $faissId = $clapMeta.faiss_id
      Write-Host ("CLAP: status={0} id={1}" -f $status, (if ($faissId) { $faissId } else { 'n/a' }))
    }
    
    # Check for sentiment property
    $sentiment = $null
    if ($entry.PSObject.Properties.Name -contains 'sentiment') {
      $sentiment = $entry.sentiment
    }
    if (-not $sentiment -and ($audio.PSObject.Properties.Name -contains 'sentiment')) {
      $sentiment = $audio.sentiment
    }
    
    if ($sentiment) {
      if ($sentiment.score -ne $null) {
        try { $score = [double]$sentiment.score } catch { $score = $null }
      } else { $score = $null }
      if ($score -ne $null) {
        Write-Host ("Sentiment: {0} ({1:P0})" -f $sentiment.label, $score)
      } else {
        Write-Host ("Sentiment: {0}" -f $sentiment.label)
      }
    }
    
    # Check for audio_emotion property
    $emotion = $null
    if ($entry.PSObject.Properties.Name -contains 'audio_emotion') {
      $emotion = $entry.audio_emotion
    }
    if ($emotion -and $emotion.Count -gt 0) {
      Write-Host ("Audio emotion: {0}" -f $emotion[0].label)
    }
  }
  $scenes = @($entry.scenes)
  if ($scenes.Count -gt 0) {
    Write-Host 'Scenes:'
    $scenes | Select-Object -First 3 | ForEach-Object {
      # Safe property access with checks
      $tags = if ($_.PSObject.Properties.Name -contains 'tags' -and $_.tags) { 
        ($_.tags | Select-Object -First 3) -join ', ' 
      } else { '—' }
      
      try { $st = [double]$_.start } catch { $st = 0 }
      try { $en = [double]$_.end } catch { $en = $st }
      
      $tr = if ($_.PSObject.Properties.Name -contains 'top_tracked' -and $_.top_tracked) { 
        ($_.top_tracked | Select-Object -First 2 | ForEach-Object { 
          $lbl = if ($_.label) { $_.label } else { '?' }
          $cnt = if ($_.count) { $_.count } else { 0 }
          "$lbl×$cnt"
        }) -join ', ' 
      } else { '' }
      
      $idx = if ($_.PSObject.Properties.Name -contains 'index') { $_.index } else { 0 }
      $conf = if ($_.PSObject.Properties.Name -contains 'confidence') { [double]$_.confidence } else { 0.0 }
      
      Write-Host ("  #{0} {1:N1}-{2:N1}s conf={3:N2} Tags: {4} Tracks: {5}" -f $idx, $st, $en, $conf, $tags, $tr)
    }
  }
}

function Show-RetrievePreview {
  H1 'Retrieve Preview'
  $query = $env:GOODQ_CC_QUERY
  if (-not $query) { $query = 'test' }
  try {
    $out = & conda run -n goodq_text_embed python -m goodq4all.cli.retrieve --text "$query" --topk 3
    $j = $out | ConvertFrom-Json
    if (-not $j -or -not ($j.PSObject.Properties.Name -contains 'matches') -or -not $j.matches) { 
      Warn 'No matches'; return 
    }
    Write-Host ("Query: {0}" -f $query)
    foreach ($m in $j.matches) {
      $f = if ($m.PSObject.Properties.Name -contains 'source_path' -and $m.source_path) { 
        [System.IO.Path]::GetFileName($m.source_path) 
      } else { '' }
      
      $s = if ($m.PSObject.Properties.Name -contains 'scene' -and $m.scene) { 
        $scStart = if ($m.scene.PSObject.Properties.Name -contains 'start') { [double]$m.scene.start } else { 0 }
        $scEnd = if ($m.scene.PSObject.Properties.Name -contains 'end') { [double]$m.scene.end } else { 0 }
        " [$($scStart.ToString('N1'))-$($scEnd.ToString('N1'))s]"
      } else { '' }
      
      $score = if ($m.PSObject.Properties.Name -contains 'score') { [double]$m.score } else { 0.0 }
      Write-Host ("  {0}  score={1:N3}{2}" -f $f, $score, $s)
    }
  } catch { Warn 'Retrieve preview failed' }
}

function Show-SegmentSentiment {
  H1 'Segment Sentiment'
  $path = Join-Path $repoRoot 'logs/video_ingest_results.json'
  if (-not (Test-Path $path)) { Warn 'No video summaries yet'; return }
  try {
    $json = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
  } catch { Warn 'Failed to read video summaries'; return }
  $entry = if ($json -is [System.Array]) { $json[-1] } else { $json }
  
  # Check if property exists
  if (-not ($entry.PSObject.Properties.Name -contains 'segments_sentiment')) {
    Warn 'No segment sentiments in data'
    return
  }
  
  $segs = @($entry.segments_sentiment)
  if (-not $segs -or $segs.Count -eq 0) { Warn 'No segment sentiments'; return }
  $segs | Select-Object -First 6 | ForEach-Object {
    $label = if ($_.sentiment) { $_.sentiment.label } else { '' }
    $score = if ($_.sentiment) { [double]$_.sentiment.score } else { 0 }
    Write-Host ("  {0:N1}-{1:N1}s  {2} ({3:P0})" -f ([double]$_.start), ([double]$_.end), $label, $score)
  }
}

function Show-MemorySummaries {
  H1 'Memory Snapshots'
  $p = Read-PathsYaml
  $db = $p['db_path']
  if (-not $db -or -not (Test-Path $db)) { Warn 'DB not found for memory snapshots'; return }
  try {
    $pyScript = @'
import json, sqlite3, sys
db = sys.argv[1]
categories = ['ingest_summary','overview','video_ingest']
payload = {c: {'short_term': None, 'long_term': None} for c in categories}
try:
    con = sqlite3.connect(db)
    cur = con.cursor()
    for cat in categories:
        cur.execute("SELECT content, created_at FROM summaries WHERE summary_type='short_term' AND category=? ORDER BY id DESC LIMIT 1", (cat,))
        row = cur.fetchone()
        if row:
            payload[cat]['short_term'] = {'content': row[0], 'created_at': row[1]}
        cur.execute("SELECT content, created_at FROM summaries WHERE summary_type='long_term' AND category=? ORDER BY id DESC LIMIT 1", (cat,))
        row = cur.fetchone()
        if row:
            payload[cat]['long_term'] = {'content': row[0], 'created_at': row[1]}
    con.close()
except Exception:
    payload = None
print(json.dumps(payload))
'@
    $tmpFile = [System.IO.Path]::GetTempFileName()
    Set-Content -LiteralPath $tmpFile -Value $pyScript -Encoding UTF8
    try {
      $json = & conda run -n goodq_zenml python $tmpFile $db
    } finally {
      Remove-Item -LiteralPath $tmpFile -Force -ErrorAction SilentlyContinue
    }
    if (-not $json) { Warn 'No memory data yet'; return }
    $data = $json | ConvertFrom-Json
    if (-not $data) { Warn 'No memory data yet'; return }
    foreach ($cat in @('ingest_summary','overview','video_ingest')) {
      $entry = $data.$cat
      if (-not $entry) { continue }
      Write-Host ("{0}:" -f $cat)
      if ($entry.short_term -and $entry.short_term.content) {
        Write-Host ("  short-term @ {0}" -f $entry.short_term.created_at)
        try {
          $payload = $entry.short_term.content | ConvertFrom-Json
          if ($cat -eq 'ingest_summary' -and $payload.count -ne $null) {
            Write-Host ("    items={0} frames={1}" -f $payload.count, $payload.total_frames)
            if ($payload.top_tags) {
              $tags = ($payload.top_tags | Select-Object -First 3 | ForEach-Object { $_.tag }) -join ', '
              if ($tags) { Write-Host ("    tags: {0}" -f $tags) }
            }
          } elseif ($cat -eq 'overview') {
            if ($payload.video_advisories) {
              $advs = ($payload.video_advisories | Select-Object -First 3 | ForEach-Object { $_.label }) -join ', '
              if ($advs) { Write-Host ("    advisories: {0}" -f $advs) }
            }
          } elseif ($cat -eq 'video_ingest') {
            if ($payload.video_summaries) {
              $first = $payload.video_summaries | Select-Object -First 1
              foreach ($vid in $first) {
                $vidName = if ($vid.video) { $vid.video } else { '(unknown)' }
                Write-Host ("    video: {0}" -f $vidName)
                if ($vid.advisories) {
                  $adv = ($vid.advisories | Select-Object -First 3) -join ', '
                  if ($adv) { Write-Host ("    advisories: {0}" -f $adv) }
                }
              }
            }
          }
        } catch {}
      } else {
        Write-Host '  short-term: (none)'
      }
      if ($entry.long_term -and $entry.long_term.content) {
        Write-Host ("  long-term @ {0}" -f $entry.long_term.created_at)
      } else {
        Write-Host '  long-term: (none)'
      }
    }
  } catch {
    Warn 'Unable to read memory summaries'
  }
}

function Show-RecentSteps {
  H1 'Recent Steps'
  $p = Read-PathsYaml
  $logDir = $p['log_dir']
  if (-not $logDir) { $logDir = (Join-Path $repoRoot 'logs') }
  $csv = Join-Path $logDir 'step_runs.csv'
  if (Test-Path $csv) {
    Get-Content -Tail 15 -LiteralPath $csv
  } else {
    Warn 'No step_runs.csv yet'
  }
}

function Show-StepLogJsonl {
  H1 'Step Log (JSONL tail)'
  $p = Read-PathsYaml
  $logDir = $p['log_dir']
  if (-not $logDir) { $logDir = (Join-Path $repoRoot 'logs') }
  $jsonl = Join-Path $logDir 'step_runs.jsonl'
  if (Test-Path $jsonl) {
    $lines = Get-Content -Tail 10 -LiteralPath $jsonl
    foreach ($ln in $lines) {
      try {
        $j = $ln | ConvertFrom-Json
        $err = if ($j.error) { ' ERR' } else { '' }
        $src = if ($j.source_path) { [System.IO.Path]::GetFileName($j.source_path) } else { '' }
        Write-Host ("{0} [{1}] {2} {3}ms {4} {5}" -f $j.ts, $j.env, $j.step, [int]$j.duration_ms, ($j.status + $err), $src)
      } catch {
        Write-Host $ln
      }
    }
  } else {
    Warn 'No step_runs.jsonl yet'
  }
}

function Show-Drift {
  H1 'DB↔FAISS Drift'
  $p = Read-PathsYaml
  $db = $p['db_path']
  if (-not $db -or -not (Test-Path $db)) { Warn 'DB not found'; return }
  function _faiss($env,$idx){
    if (-not $idx -or -not (Test-Path $idx)) { return $null }
    try {
      $pyScript = @'
import faiss, sys
print(faiss.read_index(sys.argv[1]).ntotal)
'@
      $tmpFile = [System.IO.Path]::GetTempFileName()
      Set-Content -LiteralPath $tmpFile -Value $pyScript -Encoding UTF8
      try {
        $o = & conda run -n $env python $tmpFile $idx
      } finally {
        Remove-Item -LiteralPath $tmpFile -Force -ErrorAction SilentlyContinue
      }
      $s = ($o | Out-String).Trim(); if ($s -match '^[0-9]+$') { return [int]$s } else { return $null }
    } catch { return $null }
  }
  function _count($dbp,$sql){
    try {
      $pyScript = @'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1]); cur = con.cursor(); cur.execute(sys.argv[2]); r = cur.fetchone(); print(int(r[0]) if r else 0); con.close()
'@
      $tmpFile = [System.IO.Path]::GetTempFileName()
      Set-Content -LiteralPath $tmpFile -Value $pyScript -Encoding UTF8
      try {
        $o = & conda run -n goodq_zenml python $tmpFile $dbp $sql
      } finally {
        Remove-Item -LiteralPath $tmpFile -Force -ErrorAction SilentlyContinue
      }
      $s = ($o | Out-String).Trim(); if ($s -match '^[0-9]+$') { return [int]$s } else { return $null }
    } catch { return $null }
  }
  $embTotal = _count $db 'SELECT COUNT(*) FROM embeddings'
  $faissText = _faiss 'goodq_text_embed' $p['faiss_index_path']
  $clipMap = $null; if ($p['clip_id_map_db'] -and (Test-Path $p['clip_id_map_db'])) { $clipMap = _count $p['clip_id_map_db'] 'SELECT COUNT(*) FROM clip_id_map' }
  $dinoMap = $null; if ($p['dino_id_map_db'] -and (Test-Path $p['dino_id_map_db'])) { $dinoMap = _count $p['dino_id_map_db'] 'SELECT COUNT(*) FROM dino_id_map' }
  $clapMap = $null; if ($p['clap_id_map_db'] -and (Test-Path $p['clap_id_map_db'])) { $clapMap = _count $p['clap_id_map_db'] 'SELECT COUNT(*) FROM clap_id_map' }
  function _report($name,$faiss,$dbrows){
    if ($faiss -eq $null -or $dbrows -eq $null) { return }
    $diff = [math]::Abs($faiss - $dbrows)
    $rel = if ($dbrows -gt 0) { $diff / [double]$dbrows } else { 0.0 }
    $msg = ("{0}: faiss={1} db={2} drift={3:P1}" -f $name,$faiss,$dbrows,$rel)
    if ($rel -gt 0.1) { Warn $msg } else { Write-Host $msg }
  }
  _report 'text' $faissText $embTotal
  _report 'dino (id_map)' $(_faiss 'goodq_image_caption' $p['faiss_dino_path']) $dinoMap
  _report 'clip (id_map)' $(_faiss 'goodq_image_caption' $p['faiss_clip_path']) $clipMap
  _report 'audio (id_map)' $(_faiss 'goodq_audio_embed' $p['faiss_audio_path']) $clapMap
}

function Show-Thumbnails {
  H1 'Scene Thumbnails'
  $path = Join-Path $repoRoot 'logs/video_ingest_results.json'
  if (-not (Test-Path $path)) { Warn 'No video summaries yet'; return }
  try { $json = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json } catch { Warn 'Failed to read video summaries'; return }
  $entry = if ($json -is [System.Array]) { $json[-1] } else { $json }
  $scenes = @($entry.scenes)
  if (-not $scenes -or $scenes.Count -eq 0) { Warn 'No scenes'; return }
  $n = [int]([Environment]::GetEnvironmentVariable('GOODQ_CC_THUMBS') ?? '6')
  $scenes | Select-Object -First $n | ForEach-Object {
    # Check if property exists and format display
    $thumb = if ($_.PSObject.Properties.Name -contains 'thumb_path') { $_.thumb_path } else { $null }
    $displayThumb = if ($thumb) { $thumb } else { '(no thumb)' }
    Write-Host ("  {0:N1}-{1:N1}s  {2}" -f ([double]$_.start), ([double]$_.end), $displayThumb)
  }
}

function Show-ZenMLArtifacts {
  if (-not $UseZenMLArtifacts) { return }
  H1 'ZenML Artifacts (latest JSON)'
  $artRoot = Join-Path $repoRoot 'zenml_store/artifacts'
  if (-not (Test-Path $artRoot)) { Warn 'No artifacts yet'; return }
  $f = Get-ChildItem -LiteralPath $artRoot -Filter 'data.json' -Recurse | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $f) { Warn 'No JSON artifacts yet'; return }
  Write-Host ("Artifact: {0}" -f $f.FullName)
  try {
    $json = Get-Content -Raw -LiteralPath $f.FullName | ConvertFrom-Json
    $keys = ($json | Get-Member -MemberType NoteProperty | Select-Object -ExpandProperty Name)
    Write-Host ("Keys: {0}" -f ($keys -join ', '))
    if ($json.db -and $json.faiss) {
      Write-Host ("DB: embeddings={0}, links={1}" -f $json.db.embeddings, $json.db.links)
      Write-Host ("FAISS: text={0} dino={1} clip={2} audio={3}" -f $json.faiss.text,$json.faiss.dino,$json.faiss.clip,$json.faiss.audio)
    }
  } catch {
    Warn 'Failed to read artifact JSON'
  }
}

function Render {
  Clear-Host
  H1 'GoodQ Command Center'
  Show-GPU
  Show-DBAndFAISS
  Show-Drift
  Show-HotCache
  Show-LatestExport
  Show-RetrievePreview
  Show-SegmentSentiment
  Show-Thumbnails
  Show-LastScenePeek
  Show-StepLogJsonl
  Show-MemorySummaries
  Show-VideoSummary
  Show-RecentSteps
  Show-ZenMLArtifacts
}

if ($Refresh) {
  while ($true) {
    Render
    Write-Host "Press Enter to refresh, 'q' to quit" -ForegroundColor Gray
    $k = Read-Host
    if ($k -eq 'q') { break }
  }
} else {
  Render
}
