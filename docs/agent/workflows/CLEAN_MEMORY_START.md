<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_RUNBOOK -->
<!-- DOC_LAST_VERIFIED: 2026-05-24 -->

# Clean Memory Start Workflow

Use this runbook before running personal or home-movie media through GoodQ4All
after a proving-ground/test-memory phase.

> [!NOTE]
> **Issue Diagnostics & Reporting Directive (Mandatory Coverage)**
> Report every issue you find, including ones you are uncertain about or consider low-severity. Do not filter for importance or confidence at this stage - a separate verification step will do that. Your goal here is coverage: it is better to surface a finding that later gets filtered out than to silently drop a real bug. For each finding, include your confidence level and an estimated severity so a downstream filter can rank them.

## Safety Boundary

This workflow may delete Qdrant collections whose names begin with `goodq_`.
Do not delete filesystem epochs until they have been measured and the operator
has confirmed bulk artifact cleanup is desired.

## Probe Run Rule

Treat every scene probe that is meant to validate retrieval, sentiment,
emotion, KG, or vector proof as a clean-run experiment:

- use a fresh epoch name for the probe
- manifest existing `goodq_` Qdrant collections before deletion
- delete and recreate the active `goodq_` Qdrant collections before the probe
- verify the fresh collections are empty before ingestion
- verify the configured FAISS targets are absent or explicit-ID indexes before
  ingestion
- do not reuse an epoch that already contains probe vectors, even if the prior
  probe was small

This prevents stale Qdrant points or prior FAISS residue from looking like new
scene truth.

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

The follow-up 2026-05-21 validation probes then used:

```text
epoch_2026_05_21_family_full_clean_02
```

That epoch now contains the 1-scene and 10-scene FAMILY validation probes. It is
useful evidence, but it is not a pristine seed for the next probe or broad
home-memory run. Reset Qdrant and use a fresh epoch, or deliberately reset the
active epoch and verify all FAISS targets before ingestion.

The 2026-05-21 emotion-ranking validation used a short local clip and:

```text
epoch_2026_05_21_family_full_clean_04
```

That epoch is the current evidence surface for the repaired sentiment and
emotion-ranking path. It should also be treated as occupied probe evidence, not
a seed for the next clean pass.

The 2026-05-22 runtime fallback/audio/entity validation then used:

```text
epoch_2026_05_22_runtime_fallback_probe_02
```

That epoch is the current evidence surface for the Windows Ollama fallback,
configured WSL `faster-whisper` probe, current-run audio proof, sentiment,
entity hygiene, Qdrant, and explicit-ID FAISS validation. It is occupied probe
evidence, not a broad home-memory seed.

The completed full family home-movie validation run then used:

```text
epoch_2026_05_22_family_full_01
```

That epoch contains the full 141-scene FAMILY run, complete SQLite/KG projections, audio vector proofs, and is served by the Retro Memory Explorer UI. It is the current baseline validation surface and must not seed the next clean pass.

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

## 2.5 Wipe Active Epoch & Legacy Database Files

Run this Python script to delete the SQLite databases, FAISS indices, and legacy project graph databases for the active configured epoch:

```powershell
python - <<'PY'
import os, sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path.cwd()))
try:
    from steps.common.config_loader import load_configs
except ModuleNotFoundError:
    try:
        from goodq4all.steps.common.config_loader import load_configs
    except ModuleNotFoundError:
        print("[ERROR] Cannot load config_loader. Run from project root.")
        sys.exit(1)

config = load_configs({})
paths = config.get('paths', {})

db_path = paths.get('db_path')
kg_path = paths.get('knowledge_graph_db')
faiss_dir = paths.get('faiss_dir')
legacy_kg = Path("data/knowledge_graph.db")

print("=== Wiping active epoch relational memory ===")
for p_str in [db_path, f"{db_path}-shm", f"{db_path}-wal", kg_path]:
    if p_str:
        p = Path(p_str)
        if p.exists():
            try:
                p.unlink()
                print(f"[SUCCESS] Deleted: {p}")
            except Exception as e:
                print(f"[ERROR] Failed to delete {p}: {e}")

print("\n=== Wiping legacy database files ===")
if legacy_kg.exists():
    try:
        legacy_kg.unlink()
        print(f"[SUCCESS] Deleted: {legacy_kg}")
    except Exception as e:
        print(f"[ERROR] Failed to delete {legacy_kg}: {e}")

print("\n=== Wiping FAISS index and sqlite map files ===")
if faiss_dir:
    faiss_p = Path(faiss_dir)
    if faiss_p.exists():
        for root, dirs, files in os.walk(faiss_p, topdown=False):
            for file in files:
                file_path = Path(root) / file
                try:
                    file_path.unlink()
                    print(f"[SUCCESS] Deleted FAISS file: {file_path}")
                except Exception as e:
                    print(f"[ERROR] Failed to delete FAISS file {file_path}: {e}")
            for d in dirs:
                d_path = Path(root) / d
                os.makedirs(d_path, exist_ok=True)
PY
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

## 4.5 Generate Post-Cleanup Manifest

Verify the baseline cleanup and record host, database, FAISS indices, and empty Qdrant collection states to prove the baseline state is clean:

```powershell
python - <<'PY'
import os, sys, socket, datetime, subprocess, json, urllib.request, urllib.parse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path.cwd()))
try:
    from steps.common.config_loader import load_configs
except ModuleNotFoundError:
    from goodq4all.steps.common.config_loader import load_configs

config = load_configs({})
paths = config.get('paths', {})

db_path = Path(paths.get('db_path')) if paths.get('db_path') else None
kg_path = Path(paths.get('knowledge_graph_db')) if paths.get('knowledge_graph_db') else None
faiss_dir = Path(paths.get('faiss_dir')) if paths.get('faiss_dir') else None

# 1. Gather files status
memory_db_status = "absent"
if db_path and db_path.exists():
    memory_db_status = "present (empty)" if db_path.stat().st_size == 0 else f"present ({db_path.stat().st_size} bytes)"

kg_db_status = "absent"
if kg_path and kg_path.exists():
    kg_db_status = "present (empty)" if kg_path.stat().st_size == 0 else f"present ({kg_path.stat().st_size} bytes)"

# 2. Gather FAISS status
faiss_index_count = 0
faiss_id_map_count = 0
if faiss_dir and faiss_dir.exists():
    for root, _, files in os.walk(faiss_dir):
        for f in files:
            if f.endswith('.index'):
                faiss_index_count += 1
            elif f.endswith('.sqlite') or f.endswith('.db'):
                faiss_id_map_count += 1

# 3. Gather Git & Host info
try:
    git_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=str(Path.cwd())).decode().strip()
except Exception:
    git_commit = "unknown"

hostname = socket.gethostname()
timestamp = datetime.datetime.utcnow().isoformat() + 'Z'

# 4. Gather Qdrant info
base = 'http://127.0.0.1:6333'
collections_report = []
try:
    collections_data = json.load(urllib.request.urlopen(base + '/collections', timeout=5))
    collections = collections_data['result']['collections']
    for col in sorted(collections, key=lambda c: c['name']):
        name = col['name']
        if not name.startswith('goodq_'):
            continue
        info = json.load(urllib.request.urlopen(base + '/collections/' + urllib.parse.quote(name, safe=''), timeout=5))['result']
        vector_config = info.get('config', {}).get('params', {}).get('vectors', {})
        dim = vector_config.get('size') if isinstance(vector_config, dict) else None
        
        collections_report.append({
            'name': name,
            'vector_dimension': dim,
            'points_count': info.get('points_count'),
            'status': info.get('status')
        })
except Exception as e:
    print(f"Error querying Qdrant: {e}")

payload = {
    'kind': 'qdrant_post_cleanup_manifest',
    'timestamp': timestamp,
    'machine_hostname': hostname,
    'git_commit': git_commit,
    'active_epoch': config.get('paths', {}).get('db_dir'),
    'database_states': {
        'memory_db': memory_db_status,
        'knowledge_graph_db': kg_db_status
    },
    'faiss_states': {
        'faiss_index_count': faiss_index_count,
        'faiss_id_map_count': faiss_id_map_count
    },
    'qdrant_collections': collections_report
}

out_dir = Path('reports/local_housekeeping/2026-06-12-memory-clean-start')
out_dir.mkdir(parents=True, exist_ok=True)
out_file = out_dir / 'qdrant_post_cleanup_manifest.json'
out_file.write_text(json.dumps(payload, indent=2), encoding='utf-8')
print(json.dumps(payload, indent=2))
PY
```

Expected: Database files are listed as "absent" or "present (empty)", FAISS index/id-map counts are `0`, and all active Qdrant collections have a `points_count` of `0` and dimension matching current models (CLIP=768, DINO=1024, Text=384, Audio=512).

## 5. Rerun One Scene First

Run one small scene or one small video before broad ingestion. Inspect:

- `/api/status`
- `/api/runs/latest/evidence`
- `/ui/operator_console_v1/`
- current-run audio proof, scene context, temporal index, and retrieval surfaces

Do not launch a full batch until the scene-level evidence is useful and clearly
scoped to the fresh home-memory epoch.
