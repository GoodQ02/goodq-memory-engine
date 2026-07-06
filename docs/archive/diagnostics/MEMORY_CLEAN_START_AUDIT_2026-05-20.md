<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CLEAN_START_AUDIT_SUMMARY -->
<!-- DOC_LAST_VERIFIED: 2026-05-20 -->

# Memory Clean Start Audit - 2026-05-20

## Purpose

Prepare GoodQ4All for a clean personal/home-movie rerun by removing
proving-ground memory from active local runtime surfaces.

## Operator Decision

Prior pipeline memory was classified as disposable and reproducible, including:

- Seinfeld/sample/test witness memory
- semantic-cleanup and smoke-test memory
- previous home-movie probe runs
- Qdrant embeddings from all prior test epochs

Tracked report summaries remain as historical proof. Generated runtime artifacts
were cleaned from local ignored directories so active API and UI surfaces do not
start by showing old runs.

## Pre-Cleanup Findings

- Qdrant collections: `68`
- Qdrant represented epochs: `17`
- Qdrant points: `17,767`
- Filesystem epoch payloads: about `5,280 MB`
- Ignored generated report payloads: about `6,098 MB`
- `/api/runs/latest/evidence` resolved to an old standalone probe before report
  cleanup.

## Actions Completed

- Deleted all `68` old `goodq_` Qdrant collections.
- Initialized fresh home-memory collections:
  - `goodq_clip_epoch_2026_05_20_home_memory_clean`
  - `goodq_dino_epoch_2026_05_20_home_memory_clean`
  - `goodq_text_epoch_2026_05_20_home_memory_clean`
  - `goodq_audio_epoch_2026_05_20_home_memory_clean`
- Deleted ignored generated report artifacts that were feeding latest-run API
  projections.
- Removed `16` old filesystem epoch directories.
- Retained one small `epoch_2025_12_22` log stub because the Qdrant Windows
  service holds historical log handles open.
- Restarted the API on port `30000` after local config was pointed at the fresh
  epoch.

## Post-Cleanup Validation

- Qdrant: `4` fresh GoodQ collections, all green, all `0` points.
- API status: active, pipeline idle, database not yet created, `0` scenes.
- Latest evidence route: `available=false`, `reason=no_indexed_runs`.
- Doc drift lint: no active drive-root violations and no snapshot-authority
  violations.
- Operator console route: served successfully from local API.

## Fresh Epoch

```text
epoch_2026_05_20_home_memory_clean
```

The next run should start with one small home-movie scene or clip before broad
batch ingestion.
