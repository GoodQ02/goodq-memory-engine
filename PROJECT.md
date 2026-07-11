<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# Active bounded mission

Roadmap item: R-11 — remove Control Agent authority contradictions.

## Outcome

Establish one truthful MiniAgent/control authority: approvals bind to an exact
operation and scope, confirmation material is persisted atomically, every
decision/execution produces durable generic audit evidence, and the governor
MCP remains preflight-only and non-executing.

## Scope

- Audit the current MiniAgent contracts, native confirmation paths, token
  persistence, generic tool audit records, and governor MCP boundary.
- Write focused failing tests for each confirmed authority contradiction before
  changing production code.
- Remove confirmation bypasses and bind approvals to the exact operation and
  scope they authorize.
- Make confirmation persistence atomic and append durable generic decision and
  execution audit evidence.
- Keep disabled-by-default behavior explicit and verified.

## Boundaries

- Work in a new isolated worktree; do not continue implementation in this
  completed architecture-contract checkpoint.
- Do not turn the governor MCP into an executor.
- Do not absorb the later route-convergence or clean-memory replacement seams.
- Do not change network bindings, run ingestion, mutate live memory, or touch
  the frozen mixed checkout or public checkout.
- Preserve exact-scope UCF promotion and lifecycle behavior already
  checkpointed.

## Resume authority

Use `docs/releases/ROADMAP.md` as the sole long-running register. Use this file
only for the bounded mission above; completed work belongs in evidence and Git
history, not in another backlog.
