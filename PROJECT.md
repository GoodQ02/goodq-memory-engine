<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-05-F1 — select the remaining retrieval SQLite or telemetry seam.

## Outcome

Reconcile the two remaining retrieval effects and select one exact owner,
mutation oracle, rollback boundary, and verification gate before another
production edit. Do not treat intentional durable observability as accidental
hidden mutation or infer the next repair from an older order.

## Governing evidence

- `docs/diagnostics/R05_F1_SUMMARY_STATUS_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/diagnostics/R05_F1_MODEL_CACHE_SELECTION_2026-07-13.md`
- `docs/diagnostics/R05_F1_MODEL_CACHE_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/diagnostics/R05_F1_SUMMARY_SQLITE_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Governing invariant

Authority follows the effect actually required by the product. A query-side
SQLite read must not possess creation/write capability, while intentional
retrieval telemetry must remain durable, explicit, and governed until evidence
justifies a different policy. No retrieval route becomes passive while either
effect remains open.

## Scope

- Trace retrieval SQLite opens and retrieval-event persistence from each of the
  four retrieval routes to their exact owners.
- Use temporary roots, fake clients/models, and seeded SQLite evidence only.
- Distinguish mandatory product observability from incidental request-side
  mutation, fallback output, and write-capable database access.
- Record one selection checkpoint naming the chosen seam, intended RED, frozen
  surfaces, and completion evidence before production implementation.

## Boundaries

- Do not repeat completed Qdrant, ingest-status, summary-status, model-cache, or
  summary SQLite authority work.
- Do not change production code, route effects, responses, telemetry policy,
  dependencies, or runtime packages during selection.
- Do not invoke configured databases, live endpoints, Qdrant, models, ingestion,
  identity, WSL, public checkout, or the mixed main checkout.
- Keep retrieval SQLite and telemetry separate unless the trace proves one
  shared authority and rollback boundary.

## Completion gate

A read-only evidence checkpoint must identify every remaining retrieval SQLite
and telemetry callsite, state which behavior is intentional, select one exact
next seam, define its mutation-sensitive RED and focused regression gate, and
receive independent review. If the evidence contradicts ROADMAP ordering or
route classification, update the register before implementation.
