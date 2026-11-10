---
name: goodq4all-operator
description: Diagnose GoodQ runtime behavior and validate ingestion, approved data cleanup, or follower releases.
---

# GoodQ4All Operator

Follow applicable `AGENTS.md` and the current task's authorization. Read
`PROJECT.md` when resuming or selecting a milestone; use the relevant row of
`docs/architecture/REPOSITORY_MAP.md` to locate source and contracts. Read
`docs/agent/PROJECT_ORIENTATION.md` for unfamiliar ownership or authority, not
as a repeated preflight.

## Route the task

Paths below are relative to the repository root. Load only the matching workflow.

| Task | Owner |
| --- | --- |
| Absent, stale or incorrect runtime/API/UI evidence | `docs/agent/workflows/EVIDENCE_FIRST_RUNTIME_REPAIR.md` |
| Ingestion output quality, ground truth or threshold tuning | `docs/agent/workflows/PIPELINE_TROUBLESHOOTING_FLOW.md` |
| Approved isolated ingestion or exact-target data cleanup | `docs/agent/workflows/CLEAN_MEMORY_START.md` |
| Dev service posture, local models or GPU recovery | `docs/agent/workflows/LOCAL_DEV_RUNTIME_MODES.md` |
| Approved follower release/install validation | `docs/agent/workflows/PORTABLE_FOLLOWER_RELEASE_VALIDATION.md` |
| Reconnectable SSH scene witness | `docs/agent/workflows/REMOTE_WITNESS_OVER_SSH.md` |
| Hermes personal-memory queries | `docs/agent/workflows/HERMES_PERSONAL_MEMORY_RETRIEVAL.md` |

For ordinary documentation edits, inspect the affected text and its owner
directly; no runtime workflow, service start or personal-store query is needed.
Run `scripts/docs/doc_drift_lint.py` and
`scripts/docs/doc_authority_lint.py verify` for documentation changes.

## Bound the operation

Resolve the actual configured endpoint, epoch, paths and writer owner for the
surface under test. Use the existing project environment; `cli.print_config`
can resolve config when needed. Keep its output local and redact credentials.
Inspect relevant artifacts/status before model work or expensive probes.

An approved probe should use verified fresh isolated targets. Never clear a
collection because of its prefix or an old state note. The clean-memory runbook
owns exact-target authorization, writer handling, backup and isolation checks.
Health responses and old populated stores do not prove a new scene succeeded.

## Close one outcome

Define the observable result and its acceptance evidence, repair the affected
boundary, then verify that caller at the appropriate scope. Fresh ingestion is
required for current ingestion acceptance; a read-only consumer repair may use
existing artifacts. Broader runs and promotion require their own scope coverage.

Keep exact checks, revision/configuration and results in the task receipt.
Update `PROJECT.md` or the roadmap only when the checkpoint or gate changes.
Never hand-edit generated current-state projections. Report failures and
unverified limits; keep **UNDO ONLY - not a verification step** separate from
verification. Do not create a parallel mission, harness or completion ledger.
