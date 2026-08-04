<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_AGENT_OFFICE_INDEX -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# GoodQ4All Agent Office

This directory is the small first-read layer for agents working in GoodQ4All.
It exists so fresh sessions understand the durable project shape before they
interpret transient status or long basement-era handoff logs.

## First Read Order

1. `docs/agent/PROJECT_ORIENTATION.md` - timeless multi-root project map,
   evidence hierarchy, no-repeat preflight, and shift-report practice.
2. `docs/agent/CURRENT_STATE.md` - human-readable restart snapshot; verify its
   time-sensitive claims against live evidence.
3. `docs/agent/current_state.json` - machine-readable mirror of transient state.
4. `AGENTS.md` - durable operating protocol and engineering constraints.
5. `gemini.md` - desktop agent and workstation integration guide.
6. `PLAN.md` - coding agent execution plan (ExecPlan) guidelines.
7. The canonical contract named by the current task.

## Active Restart Handoff

For the current July historical-audio repair seam, read the
[`R08 Quality Queue Reconciliation`](../diagnostics/R08_QUALITY_QUEUE_RECONCILIATION_2026-07-29.md)
after the generated current-state snapshot. It records the closed repair lanes,
the current independent review queues, and the exact no-repeat boundaries. Use
the earlier [`R08 Historical Signature Backfill Closeout`](../diagnostics/R08_HISTORICAL_SIGNATURE_BACKFILL_CLOSEOUT_2026-07-29.md)
only as supporting batch evidence; neither diagnostic supersedes live runtime
probes.

## Active Workflows

- `workflows/PIPELINE_TROUBLESHOOTING_FLOW.md`: step-by-step pipeline threshold tuning, bug isolation, and regression verification against verified source ground truth.
- `workflows/CLEAN_MEMORY_START.md`: safe clean-slate Qdrant/epoch/FAISS preparation before personal-memory ingestion.
- `workflows/EVIDENCE_FIRST_RUNTIME_REPAIR.md`: targeted runtime repair loop for capability gaps where config, API, persistence, and UI evidence must be reconciled before broad reruns.
- `workflows/HERMES_PERSONAL_MEMORY_RETRIEVAL.md`: evidence-bound identity, relationship, and scene retrieval for the local Hermes agent.
- `workflows/LOCAL_DEV_RUNTIME_MODES.md`: paired Dev On/Dev Off service posture, encoder pre-warm, local model identity checks, and GPU-memory recovery rules.
- `workflows/PORTABLE_FOLLOWER_RELEASE_VALIDATION.md`: clean follower install, receipt preservation, and one-scene validation without canonical promotion.
- `workflows/REMOTE_WITNESS_OVER_SSH.md`: durable follower-side scene runner and reconnectable receipt protocol for approved SSH targets.

## What Lives Here

- `PROJECT_ORIENTATION.md`: durable project topology, authority boundaries,
  no-repeat gate, and incoming/outgoing shift-report format.
- `CURRENT_STATE.md`: current pause point, runtime posture, clean-start status,
  and known non-issues; it is intentionally transient.
- `current_state.json`: compact normalized state for agents and tools.
- `workflows/`: durable operator runbooks that should stay smaller than the canonical architecture docs.
- `skills/`: durable developer/operator capability files, prompt drafts, and codebase LLM audit workflows.
- `.agents/index/`: project corrections directory containing `corrections.json` to timeline issue, solution, failed attempts, and variables changed.


## What Does Not Live Here

- Historical witness proofs. Those stay in `docs/testing/`, `docs/diagnostics/`,
  `reports/`, or `docs/archive/`.
- Large scratchpad narratives. Those should be converted into a workflow, a
  contract update, or an archived historical note.
- New runtime architecture. Architecture still belongs under `docs/architecture/`
  or `docs/systems/`.

## Maintenance Rule

Update `PROJECT_ORIENTATION.md` only when durable topology or authority changes.
Update current-state files when a restart handoff changes. Keep both concise;
link to deeper proof instead of copying it.
