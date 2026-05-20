<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_AGENT_OFFICE_INDEX -->
<!-- DOC_LAST_VERIFIED: 2026-05-20 -->

# GoodQ4All Agent Office

This directory is the small first-read layer for agents working in GoodQ4All.
It exists so fresh sessions do not have to infer current truth from long
basement-era handoff logs.

## First Read Order

1. `docs/agent/CURRENT_STATE.md` - human-readable current operating state.
2. `docs/agent/current_state.json` - machine-readable mirror of the same state.
3. `AGENTS.md` - durable operating protocol and engineering constraints.
4. The canonical contract named by the current task.

## What Lives Here

- `CURRENT_STATE.md`: current pause point, runtime posture, clean-start status,
  and known non-issues.
- `current_state.json`: compact normalized state for agents and tools.
- `workflows/`: durable operator runbooks that should stay smaller than the
  canonical architecture docs.

## What Does Not Live Here

- Historical witness proofs. Those stay in `docs/testing/`, `docs/diagnostics/`,
  `reports/`, or `docs/archive/`.
- Large scratchpad narratives. Those should be converted into a workflow, a
  contract update, or an archived historical note.
- New runtime architecture. Architecture still belongs under `docs/architecture/`
  or `docs/systems/`.

## Maintenance Rule

Update this directory when a fresh agent would otherwise start from stale state
or investigate a sealed problem first. Keep it concise; link to deeper proof
instead of copying it.
