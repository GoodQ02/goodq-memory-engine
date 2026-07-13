<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-05-F1 — implement explicit retrieval request-context authority.

## Outcome

Replace process-global `GOODQ_RETRIEVAL_CONTEXT` reads with one explicit,
origin-owned, keyword-only context propagated through API, MiniAgent, CLI,
engine, router, Qdrant, ephemeral-memory, and FAISS query interfaces. Preserve
retrieval and the completed event-persistence authority while making concurrent
attribution truthful.

## Governing evidence

- `docs/diagnostics/R05_F1_RETRIEVAL_CONTEXT_AUTHORITY_SELECTION_2026-07-13.md`
- `docs/diagnostics/R05_F1_RETRIEVAL_TELEMETRY_PERSISTENCE_CHECKPOINT_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Governing invariant

Every telemetry-writing retrieval query receives its context explicitly from
its origin. Cached clients and shared stores never infer per-request identity
from process state. Interleaved calls retain distinct normalized attribution.

## Scope

- Establish mutation-sensitive RED for required keyword-only context,
  origin/caller propagation, ambient-conflict rejection, nested fan-out, and
  concurrent isolation.
- Add explicit context to the selected engine, memory protocol/router/store,
  and Qdrant query interfaces.
- Supply fixed labels from API, MiniAgent, CLI, diagnostic,
  promotion-witness, and health origins.
- Remove the ambient context entry from `.env.template` and all production
  environment reads without touching the user's environment.
- Preserve normalization vocabulary, hits, ranking, filters, promotion,
  persistence policy, health no-write behavior, and route census.

## Boundaries

- Do not change persistence policy, schema readiness, destination authority,
  fallback, event schema, retention, rollups, or warning behavior.
- Do not change raw-query logs, FAISS event details, or FAISS path-bearing logs;
  those remain the next separate privacy seam.
- Do not change response contracts, route classifications, dependencies,
  active environments, configured data, live endpoints, services, identity,
  ingestion, WSL, public checkout, or the mixed main checkout.
- Use temporary/in-memory stores, fake clients, and monkeypatches only.

## Completion gate

The current code must first fail exact origin, required-interface,
conflicting-environment, nested-call, and interleaving oracles. The repair must
pass focused engine, route, MiniAgent, promotion-witness, memory-router/store,
Qdrant, health, telemetry persistence, and route-effect regressions; compile
changed Python; pass documentation/configuration/static gates; preserve the
69-operation census; and receive independent implementation and adversarial
review before checkpointing.
