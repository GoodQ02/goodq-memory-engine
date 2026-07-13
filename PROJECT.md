<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-05-F1 — govern retrieval-event persistence/config authority.

## Outcome

Replace split retrieval-event enablement, fallback, and destination state with
one immutable canonical policy propagated through Qdrant, ephemeral, and FAISS
emitters. Preserve intentional successful-hit observability and best-effort
retrieval while preventing missing-database creation, ignored JSONL disable,
database-parent relocation, and event loss after same-path database replacement.

## Governing evidence

- `docs/diagnostics/R05_F1_RETRIEVAL_TELEMETRY_PERSISTENCE_SELECTION_2026-07-13.md`
- `docs/diagnostics/R05_F1_RETRIEVAL_SQLITE_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Governing invariant

Retrieval observability may mutate only through one explicit policy. Disabled
telemetry or fallback cannot write. Enabled SQLite telemetry may add its audit
schema and rows only to an existing primary database. Locked fallback may
append only under the exact configured log destination. Telemetry failure must
remain best effort for hits but visible without query text or absolute paths.

## Scope

- Add strict/frozen canonical `observability.retrieval_events` configuration
  and matching defaults; reject and ignore only the competing policy key
  without globally tightening legacy `memory.*` behavior.
- Resolve one frozen event policy with exact environment-over-config precedence
  and canonical log destination.
- Propagate that policy through the cached search engine, generic Qdrant
  builder, shared text-store builder, and all Qdrant/ephemeral/FAISS emitters.
- Give the observability-health provenance sampler an explicit disabled policy
  so its read-only query never depends on a post-construction environment
  toggle.
- Require an existing primary database, preserve intentional schema/event
  writes inside it, and make schema readiness robust to same-path replacement.
- Restrict JSONL to locked/busy fallback at the exact existing configured log
  directory and surface sanitized persistence loss without changing hits.
- Establish mutation-sensitive RED before production implementation.

## Boundaries

- Do not add request-scoped retrieval context in this seam.
- Do not change raw-query logs or FAISS path details in this seam.
- Do not change event row schema, retention, rollups, health, responses, route
  effects, or the 69-operation census.
- Do not reopen completed Qdrant, ingest-status, summary-status, model-cache,
  summary SQLite, or retrieval SQLite behavior.
- Do not change unrelated configuration, dependencies, active environments,
  configured data, live endpoints, services, identity, ingestion, WSL, public
  checkout, or the mixed main checkout.
- Use temporary databases/directories, fake clients, and monkeypatches only.

## Completion gate

The current implementation must first fail seeded oracles for policy loss,
fallback relocation, missing-database creation, and same-path replacement event
loss. The repair must pass focused configuration, emitter, Qdrant, ephemeral,
FAISS, retrieval, and route-effect regressions; compile changed Python; pass
documentation/configuration/static gates; preserve the 69-operation census; and
receive independent implementation and evidence review before checkpointing.
