<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# Active bounded mission

Roadmap item: R-05 — define API and Command Center execution authority.

## Outcome

Adopt one loopback-only local-operator API model. Every mounted route must have
one truthful effect class, request staging must converge on one ledgered path,
curated writes must be atomic, scope-constrained, and audited, and process or
destructive actions must use the checkpointed single-use exact-scope confirmation
authority plus a persistent job record. Remote mutation remains denied by
default.

## Scope

- Freshly inventory the mounted API and operator surfaces by actual effect:
  passive read, request staging, curated mutation, or process execution.
- Reconcile that inventory with the existing 78-operation decision evidence and
  prove which routes have changed before implementation.
- Trace duplicate staging paths, upload authorities, token mechanisms, boolean
  confirmations, UI callers, and route-local execution gates.
- Reconstruct the approved repair in a new isolated worktree with focused
  contract, route, UI-copy, and authority tests.
- Preserve the separately owned passive-status, identity-recovery, and LAN
  boundary seams.

## Boundaries

- Work in a new isolated worktree; do not continue implementation in the
  completed control-authority checkpoint.
- Keep the frozen mixed checkout and public checkout unchanged.
- Do not run ingestion, mutate live memory or identity data, expose a service to
  the LAN, or perform destructive/process actions against live state.
- Do not implement passive runtime status, identity recovery, network-boundary,
  or clean-memory replacement work inside this seam.
- Preserve the checkpointed MiniAgent confirmation/audit authority and the
  preflight-only governor boundary; do not create a third approval mechanism.

## Resume authority

Use `docs/releases/ROADMAP.md` as the sole long-running register. Use this file
only for the bounded mission above; completed work belongs in evidence and Git
history, not in another backlog.
