<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-07 — audit the unsafe clean-memory workflow and select its
portable replacement boundary.

## Outcome

Determine from fresh read-only evidence which active instructions and utilities
can delete memory, how their scopes are resolved, and whether an existing safe
primitive can be reused. Produce one exact replacement selection before any
cleanup implementation begins.

## Governing evidence

- `docs/agent/workflows/CLEAN_MEMORY_START.md`
- `.agents/skills/goodq4all-operator/SKILL.md`
- `docs/agent/skills/goodq4all-operator/SKILL.md`
- `docs/releases/ROADMAP.md`

## Governing invariant

A replacement is safe only when it starts from an immutable manifest, resolves
an exact authorized temporary or configured scope, defaults to dry-run, rejects
boundary escapes, stops on failure, and emits post-action evidence. Existing
working ingestion and promoted memory remain untouched.

## Scope

- Inventory every destructive command and target rule in the active clean-memory
  runbook and both repository operator-skill copies.
- Search for existing manifest, dry-run, exact-scope, boundary-check, and
  post-clean verification utilities before proposing new code.
- Trace configuration and authority inputs statically; use temporary-root
  fixtures only when a witness is needed.
- Produce one selection document naming the replacement entry point, manifest,
  scope, failure, rollback, and test contracts plus the exact replacement of all
  three active instruction surfaces.

## Boundaries

- Read-only selection only; do not delete, move, truncate, reset, recreate, or
  re-ingest anything in this mission.
- Do not execute manual cleanup blocks or probe configured data, Qdrant,
  databases, epochs, FAISS, watchdog state, or processing directories.
- Do not assume the dated runbook paths or mixed shell examples are current.
- Do not change production, tests, configuration, dependencies, services,
  identity, WSL, public checkout, or mixed main checkout.

## Completion gate

The selection must inventory every active destructive block across the workflow
and both operator-skill copies, prove the no-repeat search for reusable
primitives, identify one exact implementation and test boundary, name how every
active instruction copy will stop competing with the replacement, and receive
independent review. No cleanup implementation starts until the roadmap and this
bounded mission agree on that seam.
