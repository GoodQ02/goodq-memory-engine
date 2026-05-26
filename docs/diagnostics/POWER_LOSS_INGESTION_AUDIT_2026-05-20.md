<!-- DOC_BADGE: DIAGNOSTIC -->
<!-- DOC_STATUS: ACTIVE_INCIDENT_AUDIT -->
<!-- DOC_LAST_VERIFIED: 2026-05-20 -->

# Power Loss During Ingestion Audit - 2026-05-20

## Scope

This note records the observed GoodQ4All state after an unexpected workstation
shutdown while the first full home-memory ingestion was running.

The audit sections capture the original post-reboot state. The remediation
section records the narrow fixes applied afterward. Treat this as an incident
snapshot and restart guide.

## Incident Summary

- Windows logged an unclean reboot through Kernel-Power/EventLog evidence.
- Qdrant restarted after boot and all fresh home-memory collections were green.
- The GoodQ API was not running after boot until manually restarted for
  inspection.
- The completed one-scene probe remained indexed under `reports/fresh_ingest_runs`.
- The interrupted full-video run created only its run root and resolved config;
  it did not write final `output/scene_ingest_results.json`.

## Durable Storage Observations

Interrupted epoch: `epoch_2026_05_20_home_memory_clean`

SQLite:

- `memory.db` integrity check: `ok`
- `knowledge_graph.db` integrity check: `ok`
- `memory.db` journal mode: `wal`
- `knowledge_graph.db` journal mode: `wal`
- `memory.db` contained 8 scene rows after restart.
- `knowledge_graph.db` contained 8 event rows after restart.

Qdrant:

- `goodq_audio_epoch_2026_05_20_home_memory_clean`: 7 points
- `goodq_text_epoch_2026_05_20_home_memory_clean`: 15 points
- `goodq_clip_epoch_2026_05_20_home_memory_clean`: 1 point
- `goodq_dino_epoch_2026_05_20_home_memory_clean`: 1 point

Interpretation:

- Per-scene SQLite and Qdrant commits survived.
- The full run did not reach Phase 6 visual embeddings/harmonization.
- The full run did not write the final API-indexed run artifact.
- Before remediation, current dashboard evidence still indexed the completed
  one-scene probe, while strict current-run audio proof no longer matched
  because Qdrant audio payloads belonged to the interrupted full-run `run_id`.

## Interrupted Run Evidence

Interrupted full run root:

`reports/fresh_ingest_runs/family_1987_1988_full_20260520_144133`

Observed run id from step ledger:

`4bb5828b-66b3-477b-81f9-a01ac1168831`

Step ledger:

- Rows: 136
- Scene indexes touched: 0 through 7
- Status counts: 113 `ok`, 23 `skipped`
- Last observed step: `audio_metadata`
- Last observed scene index: 7
- No `pipeline.ingestion` completion row was observed for this run.

Completed one-scene probe:

`reports/fresh_ingest_runs/family_1987_1988_scene_probe_20260520_142722`

Observed probe run id:

`88f6b6e0-bd94-4668-8d4e-2610e9d89db8`

The probe completed through `cross_modal_harmonization` and wrote the
API-indexed wrapper artifacts.

## External Storage-Layer Expectations

SQLite official documentation states that transactions are designed to appear
atomic even if interrupted by an OS crash or power failure. SQLite also documents
automatic rollback of partially written transactions on next access.

Qdrant official storage documentation states that changes added to its WAL are
not lost after power loss and that Qdrant can restore storage from the WAL after
abnormal shutdown.

GoodQ4All therefore should expect storage engines to preserve committed units,
but the GoodQ ingestion pipeline spans multiple persistence surfaces:

- SQLite memory
- SQLite knowledge graph
- Qdrant vectors
- FAISS files
- filesystem artifacts
- step ledgers
- API-indexed run wrappers

Those surfaces are not one global transaction. A power loss can leave a truthful
but partial cross-store state.

## Restart Rules

Do not treat the interrupted full run as a completed canonical run.

Before broad ingestion resumes, choose one of these paths:

1. Preferred clean path: start a new fresh epoch and rerun the first video from
   scratch.
2. Surgical cleanup path: delete or quarantine partial full-run vectors,
   SQLite/KG rows, and processing artifacts for the interrupted run, then rerun
   in the current epoch.
3. Forensic path: preserve the partial state and build an interrupted-run report
   for UI/testing, but do not promote it as successful memory.

For the next ingestion run, use an output path compatible with the API run index:

`reports/fresh_ingest_runs/<run_id>/output/scene_ingest_results.json`

## Remediation Applied

- `/api/status` now reports the real SQLite `scenes` row count instead of a
  DB-present placeholder.
- `lib/run_index.py` now indexes run roots with `_resolved_config.json` but
  missing final output as `interrupted_ingestion`.
- `lib/run_summary.py` now summarizes resolved-config-only interrupted runs
  without throwing `FileNotFoundError`.
- Interrupted-run summaries preserve the run-specific Qdrant collection names
  from `_resolved_config.json`, so proof checks remain tied to the correct
  epoch even after local config is switched to a new clean epoch.
- Local config was advanced to `epoch_2026_05_20_home_memory_clean_02` for the
  next clean home-memory rerun. New Qdrant collections for that epoch were
  created and verified empty.

## Follow-Up Candidates

- Add a periodic scene-level recovery artifact, such as
  `scene_ingest_results.partial.json`, written after each completed scene.
- Add a restart checklist that compares SQLite scenes, Qdrant points, step
  ledger run ids, and API-indexed run wrappers before resuming ingestion.
