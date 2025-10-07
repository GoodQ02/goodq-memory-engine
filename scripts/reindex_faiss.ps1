Param(
  [ValidateSet('text','clip','dino','audio')] [string]$IndexKind = 'text',
  [int]$Threshold = 200000,
  [int]$TrainMax = 50000,
  [int]$NList = 4096,
  [int]$M = 16,
  [int]$NBITS = 8
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Info($m){ Write-Host "[reindex] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[reindex] $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[reindex] $m" -ForegroundColor Yellow }
function Fail($m){ Write-Error $m; exit 1 }

$repoRoot = (Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')).FullName
Set-Location $repoRoot

function Read-PathsYaml {
  $f = 'configs/paths.yaml'
  $raw = Get-Content -LiteralPath $f -Raw
  $o = @{}
  foreach ($line in $raw -split "`n") {
    if ($line -match '^\s*([A-Za-z0-9_]+):\s*"(.*)"\s*$') { $o[$matches[1]] = $matches[2] }
  }
  return $o
}

$p = Read-PathsYaml
switch ($IndexKind) {
  'text' { $idx = $p['faiss_index_path']; $envName = 'goodq_text_embed' }
  'clip' { $idx = $p['faiss_clip_path']; $envName = 'goodq_image_caption' }
  'dino' { $idx = $p['faiss_dino_path']; $envName = 'goodq_image_caption' }
  'audio' { $idx = $p['faiss_audio_path']; $envName = 'goodq_audio_embed' }
}
if (-not $idx -or -not (Test-Path $idx)) { Fail 'Index file not found' }

Info ("Evaluating index size: {0}" -f $idx)
$nt = & conda run -n $envName python - <<'PY'
import faiss, sys
idx = faiss.read_index(sys.argv[1])
print(getattr(idx, 'ntotal', 0))
PY
 -ArgumentList $idx
$ntotal = [int](($nt | Out-String).Trim())
Info ("ntotal={0}" -f $ntotal)
if ($ntotal -lt $Threshold) { Ok ("Below threshold ({0}); skipping" -f $Threshold); exit 0 }

Info 'Rebuilding as IVF-PQ using reconstructed vectors (best effort)'
$py = @"
import faiss, numpy as np, sys, time
path, nlist, m, nbits, train_max = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
idx = faiss.read_index(path)
d = idx.d
ntotal = getattr(idx, 'ntotal', 0)
recs = min(ntotal, train_max)
if recs <= 0:
    print('ERR: no vectors to train')
    raise SystemExit(1)
X = np.zeros((recs, d), dtype='float32')
for i in range(recs):
    try:
        X[i] = idx.reconstruct(i)
    except Exception:
        # cannot reconstruct; bail out
        print('ERR: reconstruct not supported')
        raise SystemExit(2)
quantizer = faiss.IndexFlatL2(d)
new_index = faiss.IndexIVFPQ(quantizer, d, nlist, m, nbits)
new_index.train(X)
# add all vectors to new index in batches
bs = 10000
for i in range(0, ntotal, bs):
    n = min(bs, ntotal - i)
    xb = np.vstack([idx.reconstruct(j) for j in range(i, i+n)]).astype('float32')
    new_index.add(xb)
faiss.write_index(new_index, path + '.ivfpq')
print('OK')
"@
$tmp = [System.IO.Path]::GetTempFileName()
Set-Content -LiteralPath $tmp -Value $py -Encoding UTF8
$res = & conda run -n $envName python $tmp $idx $NList $M $NBITS $TrainMax
Remove-Item -LiteralPath $tmp -Force
if (-not $res -or -not (($res | Out-String).Trim() -like 'OK*')) { Warn 'IVF-PQ rebuild may have failed (reconstruct unsupported or other error).' } else { Ok 'Wrote IVF-PQ index (.ivfpq).' }

