# Agent State And Memory Clean Start Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the sprawling basement-era first-read surface with a compact agent state index, then reset local test memory for a clean home-movie rerun.

**Architecture:** Keep `AGENTS.md` concise and durable, move current restart truth into `docs/agent/`, preserve historical witness material as audit evidence, and make destructive memory cleanup observable through a manifest. Runtime cleanup should disconnect the active system from historical test epochs by using a fresh local epoch and empty Qdrant collections.

**Tech Stack:** Markdown/JSON documentation, repo-scoped Codex skills under `.agents/skills`, PowerShell, Qdrant HTTP API, existing `conda run -n goodq_core` runtime commands.

---

## File Structure

- Create: `docs/agent/README.md`
  - Human/agent index for the new "digital office" layer.
- Create: `docs/agent/CURRENT_STATE.md`
  - Primary first-read handoff for fresh agents.
- Create: `docs/agent/current_state.json`
  - Machine-readable mirror of the current agent state.
- Create: `docs/agent/workflows/CLEAN_MEMORY_START.md`
  - Runbook for cleaning test memory and starting a home-memory epoch.
- Create: `.agents/skills/goodq4all-operator/SKILL.md`
  - Repo-scoped Codex skill for GoodQ4All operator/audit workflows.
- Modify: `AGENTS.md`
  - Make the new agent state docs the first read, then point to canonical contracts.
- Modify: `docs/README.md`
  - Point humans and agents to the new agent-state layer before basement history.
- Modify: `docs/bootstrap/doc_authority_map.md`
  - Register the new agent-state layer and demote basement handoff from first-read authority.
- Modify: `docs/reference/indexes/AGENT_COMMS_INDEX.md`
  - Update the agent communications index so archived notes point to the new state layer.
- Modify: `docs/HANDOFF_BASEMENT_PHASE.md`
  - Add a top notice that this is sealed basement history, not the active scratchpad.
- Runtime artifact: `reports/local_housekeeping/2026-05-20-memory-clean-start/`
  - Pre/post Qdrant manifests and cleanup summary.

---

### Task 1: Freeze The Audit Evidence

**Files:**
- Create runtime report files under `reports/local_housekeeping/2026-05-20-memory-clean-start/`

- [ ] **Step 1: Capture Qdrant collection manifest**

Run:

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
PY
```

Expected: manifest includes all old GoodQ test collections before deletion.

- [ ] **Step 2: Capture epoch filesystem summary**

Run:

```powershell
$epochs = Join-Path (Join-Path $env:GOODQ_DATA_ROOT 'GoodQ_Data') 'epochs'
Get-ChildItem -LiteralPath $epochs -Directory | ForEach-Object {
  $sum = (Get-ChildItem -LiteralPath $_.FullName -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
  [pscustomobject]@{ epoch = $_.Name; size_mb = [math]::Round(($sum/1MB),2); last_write = $_.LastWriteTime.ToString('o') }
} | ConvertTo-Json | Set-Content reports/local_housekeeping/2026-05-20-memory-clean-start/epoch_filesystem_summary.json
```

Expected: summary records legacy/test epoch sizes so later deletion is traceable.

---

### Task 2: Create Agent State Layer

**Files:**
- Create: `docs/agent/README.md`
- Create: `docs/agent/CURRENT_STATE.md`
- Create: `docs/agent/current_state.json`
- Create: `docs/agent/workflows/CLEAN_MEMORY_START.md`

- [ ] **Step 1: Add concise human first-read**

Write `docs/agent/CURRENT_STATE.md` with:

```markdown
<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_AGENT_STATE -->
<!-- DOC_LAST_VERIFIED: 2026-05-20 -->

# GoodQ4All Current Agent State

This is the first-read handoff for fresh GoodQ4All agents.

## Read This As

- Current state, not historical witness proof.
- A routing layer to canonical contracts, not a replacement for them.
- A guardrail against investigating already-sealed basement-era problems first.
```

Then include the verified runtime, clean-start, and documentation status from the audit.

- [ ] **Step 2: Add machine-readable mirror**

Write `docs/agent/current_state.json` with normalized keys:

```json
{
  "schema_version": 1,
  "last_verified": "2026-05-20",
  "project": "GoodQ4All",
  "agent_first_read": "docs/agent/CURRENT_STATE.md",
  "runtime": {
    "api": "http://127.0.0.1:30000",
    "qdrant": "http://127.0.0.1:6333",
    "primary_os": "Windows 11",
    "profile": "BASELINE"
  },
  "clean_start": {
    "prior_pipeline_memory_is_disposable": true,
    "fresh_epoch": "epoch_2026_05_20_home_memory_clean",
    "qdrant_cleanup_manifest": "reports/local_housekeeping/2026-05-20-memory-clean-start/qdrant_pre_cleanup_manifest.json"
  }
}
```

- [ ] **Step 3: Add cleanup workflow**

Write `docs/agent/workflows/CLEAN_MEMORY_START.md` with exact audit, manifest, delete, configure, validate, and rerun steps.

---

### Task 3: Add Repo-Scoped Operator Skill

**Files:**
- Create: `.agents/skills/goodq4all-operator/SKILL.md`

- [ ] **Step 1: Add focused skill**

Create a concise skill that triggers on GoodQ4All runtime audits, Qdrant cleanup, ingestion validation, docs truth maintenance, and operator-console visibility work.

Expected: the skill points Codex to `AGENTS.md`, `docs/agent/CURRENT_STATE.md`, and read-only audits before edits.

---

### Task 4: Update Authority Pointers

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/README.md`
- Modify: `docs/bootstrap/doc_authority_map.md`
- Modify: `docs/reference/indexes/AGENT_COMMS_INDEX.md`
- Modify: `docs/HANDOFF_BASEMENT_PHASE.md`

- [ ] **Step 1: Make `docs/agent/CURRENT_STATE.md` the first read**

Update the documentation reading order in `AGENTS.md` so the first entries are:

```markdown
- docs/agent/CURRENT_STATE.md
- docs/agent/current_state.json
- docs/agent/README.md
```

Expected: basement handoff remains available but no longer acts as the scratchpad front door.

- [ ] **Step 2: Update docs landing and authority map**

Expected: the docs landing page names the agent state layer, and the authority map registers it as an operational agent-state authority surface.

---

### Task 5: Configure Fresh Local Epoch

**Files:**
- Local only: `configs/config.local.yaml` (ignored by git)

- [ ] **Step 1: Create fresh epoch override**

Set local runtime paths and Qdrant collections to `epoch_2026_05_20_home_memory_clean`:

```yaml
paths:
  db_dir: <GOODQ_DATA_ROOT>/GoodQ_Data/epochs/epoch_2026_05_20_home_memory_clean
  db_path: <GOODQ_DATA_ROOT>/GoodQ_Data/epochs/epoch_2026_05_20_home_memory_clean/memory.db
  knowledge_graph_db: <GOODQ_DATA_ROOT>/GoodQ_Data/epochs/epoch_2026_05_20_home_memory_clean/knowledge_graph.db
  processing: <GOODQ_DATA_ROOT>/GoodQ_Data/epochs/epoch_2026_05_20_home_memory_clean/processing
qdrant:
  collections:
    clip: goodq_clip_epoch_2026_05_20_home_memory_clean
    dino: goodq_dino_epoch_2026_05_20_home_memory_clean
    text: goodq_text_epoch_2026_05_20_home_memory_clean
    audio: goodq_audio_epoch_2026_05_20_home_memory_clean
```

Run:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.print_config
```

Expected: printed paths and collection names match the fresh epoch.

---

### Task 6: Delete Old Qdrant Test Collections

**Files:**
- Runtime only: Qdrant collections
- Create: `reports/local_housekeeping/2026-05-20-memory-clean-start/qdrant_post_cleanup_manifest.json`

- [ ] **Step 1: Delete only GoodQ collections from Qdrant**

Run a script that deletes collections whose names start with `goodq_`.

Expected: Qdrant remains reachable and only non-GoodQ collections, if any, remain.

- [ ] **Step 2: Initialize fresh empty collections**

Run:

```powershell
conda run --no-capture-output -n goodq_core python scripts/init_qdrant_collections.py
```

Expected: four fresh collections exist with `points_count = 0`.

---

### Task 7: Validate And Commit

**Files:**
- Validate all created/modified docs.

- [ ] **Step 1: Validate docs drift**

Run:

```powershell
python scripts/docs/doc_drift_lint.py
```

Expected: pass or only known historical/archive warnings.

- [ ] **Step 2: Validate runtime config**

Run:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.print_config
```

Expected: fresh epoch paths and fresh Qdrant collections.

- [ ] **Step 3: Commit tracked docs**

Run:

```powershell
git status --short
git add AGENTS.md docs/agent docs/README.md docs/bootstrap/doc_authority_map.md docs/reference/indexes/AGENT_COMMS_INDEX.md docs/HANDOFF_BASEMENT_PHASE.md docs/superpowers/plans/2026-05-20-agent-state-and-memory-clean-start.md .agents/skills/goodq4all-operator/SKILL.md
git commit -m "docs: add agent state clean-start office"
```

Expected: tracked docs and repo skill are committed; ignored local config and runtime manifests remain local unless intentionally promoted.

---

## Self-Review

- Spec coverage: Covers agent handoff restructuring, OpenAI docs guidance, repo skill creation, Qdrant cleanup, fresh home-memory epoch, and accessory doc pointer updates.
- Placeholder scan: No `TBD`, generic TODOs, or undefined commands remain.
- Safety check: Destructive Qdrant deletion occurs only after manifest capture and user confirmation that prior pipeline memory is disposable.
