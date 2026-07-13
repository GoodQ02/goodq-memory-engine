<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-12 -->

# Active bounded mission

Roadmap item: R-05 — govern Summary Console collection create and soft-delete.

## Outcome

Make the operator collection overlay exact-scope authorized, durably audited,
atomic under failure and concurrency, and truthful after crash boundaries. Keep
the repair synchronous and overlay-scoped, with only the existing control
ledger outside that overlay; do not expand it into model, identity, runtime,
ingestion, or core-memory work.

## Governing evidence

- `docs/diagnostics/R05_SUMMARY_COLLECTION_AUTHORITY_SELECTION_2026-07-12.md`
- `docs/diagnostics/R05_MUTATION_EXECUTION_AUTHORITY_AUDIT_2026-07-12.md`
- `docs/diagnostics/R05_VIDEO_SUMMARY_AUTHORITY_CHECKPOINT_2026-07-12.md`
- `docs/architecture/SUMMARY_CONSOLE_CONTRACT.md`
- `docs/releases/ROADMAP.md`

## Scope

- `POST /api/summary/collections`
- `DELETE /api/summary/collections/{collection_id}`
- the `saved_collections.json` strict load/lock/replace owner
- explicit MiniAgent authorization-only operations and existing external-outcome
  audit integration
- persistent action-job truth for soft-delete
- Summary Console create/delete confirmation flow
- focused route, store, authority, audit, static-UI, and route-effect tests

## Required order

1. Write failing strict-store tests for malformed input, concurrency, collision,
   flush/replace failure, and preservation of authoritative bytes.
2. Implement only the collection-store lock and durable replace boundary.
3. Write failing MiniAgent scope/audit tests, then add the two authorization-only
   actions using the existing token and audit stores.
4. Write failing route tests, then add write-free prepare and exact confirm
   flows. Reuse the generic action ledger for destructive soft-delete truth.
5. Write failing static UI tests, then align create/delete confirmation and
   token handling.
6. Run the focused integrated set, independent reviews, and documentation gates
   before checkpointing.

## Boundaries

- No live endpoint, model, service, job, configured data root, or operator data.
- No temporal summarization or model-activation work.
- No video-summary ledger, recovery, worker, route, or polling changes.
- No identity or passive-status work.
- No SQLite core, Qdrant, scene, timeline, manifest, ingestion, or source-media
  mutation.
- Do not broaden around adjacent HTML rendering concerns; record them for their
  later owner.
- Preserve the frozen mixed checkout, public checkout, active services, and
  data stores.

## Completion gate

Focused evidence proves exact confirmation, no pre-confirm write, strict and
atomic collection persistence, deterministic soft-delete crash truth, durable
redacted audit, sanitized outward errors, UI confirmation truth, unchanged core
memory, and preserved route-effect/client boundaries. Deterministic crash truth
requires an immutable action/job correlation marker in the affected collection
history or equivalent persisted overlay evidence. The seam closes only with an
isolated checkpoint and roadmap evidence.
