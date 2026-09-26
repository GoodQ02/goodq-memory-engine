---
name: goodq4all-operator
description: Use for GoodQ4All repo runtime audits, clean memory starts, Qdrant cleanup, ingestion validation, local fallback/audio repair, operator-console visibility, and agent-facing documentation truth maintenance.
---

# GoodQ4All Operator

Use this skill when operating the GoodQ4All repo locally.

## Read For The Task

Follow the applicable `AGENTS.md`. For unfamiliar or authority-sensitive work,
read `docs/agent/PROJECT_ORIENTATION.md`; reuse it when already read this session.

- For runtime-state questions, read the relevant current-state section and verify
  it against the resolved configuration and live evidence. Generated state files
  are snapshots, not permission or proof that cleanup remains necessary.
- For clean-memory work, read `docs/agent/workflows/CLEAN_MEMORY_START.md`.
- For a repair, read the relevant subsystem contract and the repair workflow below.
- For documentation-only work, inspect the affected text and its authoritative
  source. Do not start services, query personal stores, or preload runtime runbooks.

## Operating Rules

- Inspect the affected surface before changing it; keep unrelated work intact.
- Require explicit authorization covering destructive cleanup or ingestion.
  A collection prefix, old epoch label, or historical state note never makes data
  disposable. Resolve exact targets and preserve recovery evidence first.
- Prefer a fresh isolated epoch and its own collections for an approved probe.
  Verify emptiness and isolation; do not clear existing collections by default.
- Preserve source behavior unless the task includes code repair.
- Use current configured endpoints and the existing project environment. Probe
  only the services relevant to the task; a successful health response alone
  does not establish useful scene output.

## Useful Checks

From the repository root, when relevant:

```powershell
git status --short --branch
conda run --no-capture-output -n goodq_core python -m cli.print_config
```

Keep resolved configuration local and redact credentials before sharing it.
For documentation changes, use `scripts/docs/doc_drift_lint.py`; distinguish
pre-existing findings from findings introduced by the changed files.

## Clean Memory Starts

Use the current procedure in `docs/agent/workflows/CLEAN_MEMORY_START.md` only
when this task involves a fresh ingestion probe or explicitly approved cleanup.
That runbook owns target selection, recovery, isolation, and scene-level evidence.
Its historical reference is optional context, never an executable cleanup plan.

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
