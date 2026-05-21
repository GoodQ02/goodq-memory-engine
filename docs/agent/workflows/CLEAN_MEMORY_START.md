<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_RUNBOOK -->
<!-- DOC_LAST_VERIFIED: 2026-05-21 -->

# Clean Memory Start Workflow

Use this runbook before running personal or home-movie media through GoodQ4All
after a proving-ground/test-memory phase.

## Safety Boundary

This workflow may delete Qdrant collections whose names begin with `goodq_`.
Do not delete filesystem epochs until they have been measured and the operator
has confirmed bulk artifact cleanup is desired.

## 1. Capture The Qdrant Manifest

Record collection names and point counts before deletion:

```powershell
python - <<'PY'
import json, urllib.request, urllib.parse, pathlib
base='http://127.0.0.1:6333'
out=pathlib.Path('reports/local_housekeeping/2026-05-20-memory-clean-start')
out.mkdir(parents=True, exist_ok=True)
collections=json.load(urllib.request.urlopen(base + '/collections', timeout=5))['result']['collections']
rows=[]
for col in sorted(collections, key=lambda c: c['name']):
    name=col['name']
    info=json.load(urllib.request.urlopen(base + '/collections/' + urllib.parse.quote(name, safe=''), timeout=5))['result']
    rows.append({
        'name': name,
        'points_count': info.get('points_count'),
        'vectors_count': info.get('vectors_count'),
        'status': info.get('status'),
        'segments_count': info.get('segments_count'),
    })
payload={'kind':'qdrant_pre_cleanup_manifest','date':'2026-05-20','collection_count':len(rows),'collections':rows}
(out / 'qdrant_pre_cleanup_manifest.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
print(json.dumps({'collections': len(rows), 'points': sum(int(r.get('points_count') or 0) for r in rows)}, indent=2))
PY
```

## 2. Point Local Runtime At A Fresh Epoch

Use local ignored config for operator-specific paths. The active fresh epoch for
this machine is recorded in `docs/agent/CURRENT_STATE.md` and
`docs/agent/current_state.json`.

The original cleanup pass used:

```text
epoch_2026_05_20_home_memory_clean
```

After the 2026-05-20 power-loss audit, the clean rerun target advanced to:

```text
epoch_2026_05_20_home_memory_clean_02
```

The 2026-05-21 FAISS validation pass then used this validation epoch:

```text
epoch_2026_05_21_family_full_clean_01
```

That epoch contains probe data and one legacy audio FAISS residue from earlier
tests. Treat it as validation evidence, not the broad-run seed.

For the next broad home-memory run, create or select a fresh epoch and confirm
its configured collections follow this pattern:

```text
goodq_clip_<fresh_epoch>
goodq_dino_<fresh_epoch>
goodq_text_<fresh_epoch>
goodq_audio_<fresh_epoch>
```

Validate with:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.print_config
```

## 3. Delete Historical GoodQ Qdrant Collections

Only delete collections whose names start with `goodq_`:

```powershell
python - <<'PY'
import json, urllib.request, urllib.parse
base='http://127.0.0.1:6333'
collections=json.load(urllib.request.urlopen(base + '/collections', timeout=5))['result']['collections']
deleted=[]
for col in sorted(collections, key=lambda c: c['name']):
    name=col['name']
    if not name.startswith('goodq_'):
        continue
    req=urllib.request.Request(base + '/collections/' + urllib.parse.quote(name, safe=''), method='DELETE')
    with urllib.request.urlopen(req, timeout=15) as resp:
        deleted.append({'name': name, 'status': resp.status})
print(json.dumps({'deleted': deleted, 'count': len(deleted)}, indent=2))
PY
```

## 4. Initialize Fresh Empty Collections

```powershell
conda run --no-capture-output -n goodq_core python scripts/init_qdrant_collections.py
```

Then verify point counts:

```powershell
python - <<'PY'
import json, urllib.request, urllib.parse
base='http://127.0.0.1:6333'
collections=json.load(urllib.request.urlopen(base + '/collections', timeout=5))['result']['collections']
rows=[]
for col in sorted(collections, key=lambda c: c['name']):
    name=col['name']
    if not name.startswith('goodq_'):
        continue
    info=json.load(urllib.request.urlopen(base + '/collections/' + urllib.parse.quote(name, safe=''), timeout=5))['result']
    rows.append({'name': name, 'points_count': info.get('points_count'), 'status': info.get('status')})
print(json.dumps(rows, indent=2))
PY
```

Expected: only the fresh epoch collections are present, all with `points_count`
equal to `0`.

Also verify configured FAISS targets in the fresh epoch are either absent or
explicit-ID indexes. Legacy non-IDMap FAISS files must not be reused for a
strict memory pass.

## 5. Rerun One Scene First

Run one small scene or one small video before broad ingestion. Inspect:

- `/api/status`
- `/api/runs/latest/evidence`
- `/ui/operator_console_v1/`
- current-run audio proof, scene context, temporal index, and retrieval surfaces

Do not launch a full batch until the scene-level evidence is useful and clearly
scoped to the fresh home-memory epoch.
