<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-05-F1 — make retrieval model loading local-only.

## Outcome

Resolve text and CLIP query encoders only from exact registry-pinned local
snapshots without downloads, cache writes, environment mutation, directory
creation, or provisioner logging.

## Governing evidence

- `docs/diagnostics/R05_F1_HIDDEN_READ_MUTATION_SELECTION_2026-07-13.md`
- `docs/diagnostics/R05_F1_QDRANT_QUERY_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/diagnostics/R05_F1_INGEST_STATUS_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/diagnostics/R05_F1_REMAINING_HIDDEN_READ_SELECTION_2026-07-13.md`
- `docs/diagnostics/R05_F1_SUMMARY_STATUS_AUTHORITY_CHECKPOINT_2026-07-13.md`
- `docs/diagnostics/R05_F1_MODEL_CACHE_SELECTION_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Scope

- Add a side-effect-free exact-snapshot inspector module that accepts an
  explicit models root and registry key without importing or using the
  download/provisioning path.
- Use it only in the text and CLIP retrieval loaders.
- Pass absolute local snapshot paths and `local_files_only=True` to every
  affected library loader.
- Preserve exact registry revisions and graceful missing-cache degradation.
- Add absent-cache and seeded-cache immutability tests before production code.

## Boundaries

- Production scope is limited to the pure cache inspector, two retrieval model
  loaders, and their focused tests.
- Do not invoke live endpoints, Qdrant, model downloads, ingestion, identity,
  configured data roots, operator data, WSL, or active services.
- Use temporary roots, fakes, and monkeypatches only for bounded evidence.
- Do not modify registry content, download provisioning, audio/ingestion
  loaders, telemetry, SQLite, route effects, dependencies, or runtime packages.
- Do not reopen Qdrant query, ingest-status, or summary-status authority without
  contradictory focused evidence.

## Completion gate

The current remote-ID loaders must fail the focused RED first. Absent cache must
leave the temporary tree absent and call no library loader. Seeded exact
snapshots must pass absolute paths with local-only flags while preserving every
path, byte, size, and timestamp. Provisioner/download/log poisons, existing
loader behavior, a fresh-import `sys.path` invariant, route census, compilation,
diff checks, and independent review must pass before the implementation
checkpoint.
