---
name: goodq4all-operator
description: Use for GoodQ4All repo runtime audits, clean memory starts, Qdrant cleanup, ingestion validation, local fallback/audio repair, operator-console visibility, and agent-facing documentation truth maintenance.
---

# GoodQ4All Operator

Use this skill when operating the GoodQ4All repo locally.

## First Reads

1. `AGENTS.md`
2. `docs/agent/CURRENT_STATE.md`
3. `docs/agent/current_state.json`
4. The canonical contract for the subsystem you are touching

## Operating Rules

- Start read-only: inspect config, runtime status, Qdrant, recent logs, and docs before changing anything.
- Keep cleanup observable: write or inspect a manifest before destructive runtime cleanup.
- Treat old Season, Seinfeld, witness, smoke, and prior home-movie test memory as disposable only when the current state file says so.
- Use fresh epochs for new personal-memory tests; do not reuse old "clean" epoch labels without verifying emptiness.
- Preserve source code behavior unless the task is specifically a code repair.

## Common Commands

```powershell
git status --short --branch
conda run --no-capture-output -n goodq_core python -m cli.print_config
python scripts/docs/doc_drift_lint.py
```

Qdrant health:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:6333/collections' -TimeoutSec 5
```

API health:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:30000/api/status' -TimeoutSec 5
```

## Clean Memory Starts

Follow `docs/agent/workflows/CLEAN_MEMORY_START.md`. The safe pattern is:

1. manifest old Qdrant collections
2. point local config at a fresh epoch
3. delete old `goodq_` Qdrant collections
4. initialize fresh empty collections
5. generate post-cleanup manifest using `scripts/generate_post_manifest.py`
6. run one scene first
7. inspect evidence before broad ingestion

## Evidence-First Runtime Repair

Follow `docs/agent/workflows/EVIDENCE_FIRST_RUNTIME_REPAIR.md` when a capability
looks absent, stale, or partially proven. The short pattern is:

1. name one seam
2. prove config/runtime/persistence/UI truth separately
3. patch the boundary, not the symptom
4. validate with a focused test
5. rerun a fresh scene-first probe
6. update current-state docs so the next agent does not chase the stale theory
