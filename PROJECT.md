<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-05-F1 — select the next retrieval telemetry authority seam.

## Outcome

Produce a fresh read-only reconciliation of the two remaining retrieval
telemetry concerns, then select exactly one coherent implementation seam:

1. origin-owned request-context propagation; or
2. raw-query and FAISS-detail privacy redaction.

Do not begin production implementation until the owners, callers, rollback
boundary, mutation/privacy oracle, and no-repeat boundary are explicit.

## Governing evidence

- `docs/diagnostics/R05_F1_RETRIEVAL_TELEMETRY_PERSISTENCE_CHECKPOINT_2026-07-13.md`
- `docs/diagnostics/R05_F1_RETRIEVAL_TELEMETRY_PERSISTENCE_SELECTION_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Governing invariant

Retrieval audit attribution and content must be truthful without ambient
cross-request leakage, raw query disclosure, or workstation-path disclosure.
The completed persistence policy remains the sole event-write authority.

## Scope

- Trace every origin and caller of retrieval context through API, CLI, shared
  search engine, Qdrant, ephemeral-memory, and FAISS paths.
- Trace raw query text and FAISS index detail through application logs, event
  detail payloads, fallback JSONL, warnings, and user-facing projections.
- Identify existing tests and the smallest missing interleaving or canary
  oracle for each candidate.
- Select one candidate only when its owners share one authority, rollback
  boundary, and focused verification gate.
- Record the selection and no-repeat boundary before production edits.

## Boundaries

- Read-only selection only; no production or test implementation yet.
- Do not reopen retrieval policy resolution, destination authority,
  existing-database enforcement, schema readiness, or locked/busy fallback.
- Do not change event schema, retention, rollups, health, responses, route
  effects, or the 69-operation census.
- Do not change unrelated configuration, dependencies, active environments,
  configured data, live endpoints, services, identity, ingestion, WSL, public
  checkout, or the mixed main checkout.
- Use source traces and temporary/fake witnesses only if a claim cannot be
  established statically.

## Completion gate

Two independent traces must reconcile context origins and privacy sinks,
separate the distinct authority boundaries, identify a mutation-sensitive or
canary RED for each candidate, and agree on the smallest next seam. The
selection evidence, `PROJECT.md`, and sole roadmap must be checkpointed before
implementation begins.
