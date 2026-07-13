<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-05-F1 — select FAISS absolute-path privacy authority.

## Outcome

Trace where absolute FAISS index paths cross into retrieval event details,
ordinary warnings, and the legacy observability-rollup fallback. Select one
producer-owned rollback boundary and mutation-sensitive RED contract before any
production change.

## Governing evidence

- `docs/diagnostics/R05_F1_RETRIEVAL_QUERY_LOG_PRIVACY_CHECKPOINT_2026-07-13.md`
- `docs/diagnostics/R05_F1_RETRIEVAL_TELEMETRY_PERSISTENCE_CHECKPOINT_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Governing invariant

Retrieval telemetry and failure visibility remain useful without persisting or
logging workstation-specific absolute paths. Redaction belongs at the producer
that knows the field; central event serialization remains lossless.

## Scope

- Trace the FAISS event-detail path producer to SQLite and JSONL sinks.
- Trace every path-bearing FAISS warning and the rollup compatibility fallback.
- Identify actual consumers that require a basename, logical store identity, or
  another portable field.
- Prove current exposure with temporary paths and captured/in-memory outputs.
- Select one coherent producer-owned boundary and RED oracle.

## Boundaries

- Do not change completed query-log, request-context, persistence, SQLite,
  model-cache, Qdrant no-create, status, or summary authorities.
- Do not redact `RetrievalEvent.to_row()` or `to_dict()` centrally.
- Do not clean historical logs/events or bundle analytics-question and
  derived-intent logging candidates.
- Do not change routes, responses, ranking, dependencies, environments,
  configured data, live endpoints, services, identity, ingestion, WSL, public
  checkout, or mixed main checkout.
- Use temporary paths, captured emitters/logs, and in-memory values only.

## Completion gate

The selection must enumerate every applicable producer, sink, compatibility
consumer, and failure branch; distinguish absolute-path exposure from required
portable diagnostics; define mutation-sensitive canaries; and receive an
independent read-only review before implementation begins.
