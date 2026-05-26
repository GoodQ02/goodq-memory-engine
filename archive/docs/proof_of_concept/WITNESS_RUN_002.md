<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_ARCHIVED_ON: 2026-03-03 -->

# WITNESS_RUN_002 — Full Rerun Diagnostic Comparison

## Purpose
Capture a forced, single-file rerun of the canonical witness video and compare pre/post system state to validate output movement and truth integrity after recent audit hardening.

## Run Context
- Input video: `samples/ingestion/09. 2002 - 2003.mp4`
- Rerun input mode: isolated single-file directory (`logs/diagnostics/witness_compare_20260302_173544/input`)
- Profile: `GPU_ENHANCED`
- Forced re-ingestion: enabled (`--force`)
- Observer telemetry: enabled (JSON events + heartbeat, tqdm disabled)
- Rerun `run_id`: `90e366c9-41be-4c37-84b6-52abbf4addb9`

## Reference Artifacts
- Comparison summary: `logs/diagnostics/witness_compare_20260302_173544/comparison_report.md`
- Structured comparison data: `logs/diagnostics/witness_compare_20260302_173544/snapshots/comparison.json`
- Pre snapshot: `logs/diagnostics/witness_compare_20260302_173544/snapshots/pre_snapshot.json`
- Post snapshot: `logs/diagnostics/witness_compare_20260302_173544/snapshots/post_snapshot.json`
- Rerun results JSON: `logs/diagnostics/witness_compare_20260302_173544/scene_ingest_results_rerun.json`

## Primary Outcome
- Rerun completed successfully (`exit_code=0`).
- `phase6_complete=true`
- Run-level parity remained deterministic:
  - `qdrant_ok=true`
  - `faiss_ok=not_attempted`

## Witness-001 vs Witness-002 (Key Deltas)

| Metric | Witness 001 (documented) | Witness 002 (rerun) |
| --- | --- | --- |
| `video` | `09. 2002 - 2003.mp4` | `09. 2002 - 2003.mp4` |
| `scenes_total` | `19` | `19` |
| `transcript_scenes` | `18` | `19` |
| `audio_backend_selected` | `windows (18/19 scenes; 1 missing)` | `windows (19/19 scenes)` at scene level |
| `phase6_complete` | `true` | `true` |
| `qdrant_points_clip` | `19` | `19` |
| `qdrant_points_dino` | `19` | `19` |
| `kg_media_nodes` | `19` | `19` |
| `total_duration_sec` | `1418.856` | `1510.676` |

## Pre/Post Vector Delta for Target Video ID

| Collection | Pre(video_id) | Post(video_id) | Delta |
| --- | ---: | ---: | ---: |
| `goodq_clip_epoch_2025_12_22` | `0` | `19` | `+19` |
| `goodq_dino_epoch_2025_12_22` | `0` | `19` | `+19` |
| `goodq_text_epoch_2025_12_22` | `0` | `0` | `0` |
| `goodq_audio_epoch_2025_12_22` | `0` | `0` | `0` |

## Memory and KG Movement
- `memory_commit_events_total` for target video_id: `0 -> 38`
- `memory_commit_events_by_modality` (post): `clip=19`, `dino=19`
- KG `media_nodes` with target `video_id`: `0 -> 19`

## Important Observations
1. Transcript coverage improved from `18/19` to `19/19`.
2. Scene-level audio backend is now consistently `windows` across all 19 scenes.
3. Run-level `audio_backend_selected` is still unset while scene-level backend values are populated. This remains a reporting aggregation seam, not a scene-processing failure.
4. This rerun produced visual vector movement (`clip`/`dino`) and corresponding commit events, but no target-video growth in `text`/`audio` collections in this run window.

## Claim Boundaries
- This witness validates a concrete output shift in transcript scene coverage and stable visual vector/KG movement under forced rerun conditions.
- This witness does not claim universal text/audio vector density across all runs or profiles.

