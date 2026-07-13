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
- `docs/guides/CLEAN_MEMORY_START.md`
- `docs/agent/workflows/EVIDENCE_FIRST_RUNTIME_REPAIR.md`
- `docs/agent/README.md`
- `README.md`
- `SUPPORT.md`
- `docs/archive/guides/install/UNINSTALL.md` (transitive historical hazard only)
- `AGENTS.md`
- `docs/bootstrap/doc_authority_map.md`
- `docs/reference/indexes/AGENT_COMMS_INDEX.md`
- `docs/reference/indexes/AGENT_FILE_INDEX.md`
- `docs/codebase_index/README.md`
- `.agents/skills/goodq4all-operator/SKILL.md`
- `docs/agent/skills/goodq4all-operator/SKILL.md`
- `docs/releases/ROADMAP.md`

## Governing invariant

A replacement is safe only when it starts from an immutable manifest, resolves
an exact authorized temporary or configured scope, defaults to dry-run, rejects
boundary escapes immediately before every target, journals intent and result
around each mutation, stops on failure, and emits post-action evidence. Real
configured apply remains unavailable until the separate corpus-retention
authority registers durable disposable and restorable evidence. Existing
working ingestion and promoted memory remain untouched.

## Scope

- Inventory every destructive command and target rule in the active clean-memory
  runbook and both repository operator-skill copies, plus every active redirect
  or semantic rule that could restore broad cleanup authority and every inbound
  active/index or transitive active-to-archive reference that could preserve a
  superseded executor or manual destructive procedure.
- Search for existing manifest, dry-run, exact-scope, boundary-check, and
  post-clean verification utilities before proposing new code.
- Trace configuration and authority inputs statically; use temporary-root
  fixtures only when a witness is needed.
- Produce one selection document naming the replacement entry point, manifest,
  scope, failure, rollback, and test contracts plus the exact alignment of the
  workflow, both skill copies, active guide, and evidence-first workflow.

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
primitives, identify one exact implementation and test boundary, close the
proven owner/state atomicity gap and every approval crash window, require one
exclusive lease to fence live apply from recovery, name how every active
workflow, skill, guide, and semantic redirect stops competing with the
replacement, and receive independent review. No cleanup implementation starts
until the roadmap and this bounded mission agree on that seam.
