---
name: goodq4all-operator
description: Use for GoodQ4All repo runtime audits, clean memory starts, Qdrant cleanup, ingestion validation, local fallback/audio repair, operator-console visibility, and agent-facing documentation truth maintenance.
---

# GoodQ4All Operator

Use this skill when operating the GoodQ4All repo locally.

## First Reads

1. `AGENTS.md`
2. `docs/agent/PROJECT_ORIENTATION.md`
3. `docs/agent/CURRENT_STATE.md`
4. `docs/agent/current_state.json`
5. The canonical contract for the subsystem you are touching

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
3. delete old `goodq_` Qdrant collections, watchdog state registry (`watchdog_state.json`), and processing cache directory
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

## Portable Follower Validation

For an approved SSH follower, keep the release and witness boundaries separate:

1. Verify the offline asset receipt and transfer hashes before installation.
   For large multi-pack releases, transfer and size-check packs serially, then
   run one durable hash verifier that persists per-pack progress and an atomic
   receipt. A missing heartbeat or completed-artifact update is `unproven`, not
   a reason to start a duplicate verifier.
2. Preserve approved removal, installation, offline-suite, and restore-smoke
   evidence; a fresh installer exit alone is not a clean-baseline proof.
3. Launch one isolated non-promoting scene through `cli.remote_witness` on the
   follower, then read its durable receipt after SSH reconnects.
4. Treat `runner_finished` plus terminal audio ledger evidence as the scene
   gate. An SSH timeout, a quiet cold model fetch, or a pending audio step is
   not a pass.
5. Update `docs/releases/ROADMAP.md` and the applicable workflow with verified
   state; do not hand-edit generated current-state projections.
6. For a remote elevated installer, follow the shared **Durable remote installer
   validation** section in the local-network workflow. Read back the generated
   task runner before launching it: the quoted setup path and `/S` must be one
   line, or Session 0 can wait invisibly for an interactive installer.
7. During NSIS payload verification or extraction, inspect the active child
   process and its CPU/I/O. A quiet parent task is not a stall by itself.
