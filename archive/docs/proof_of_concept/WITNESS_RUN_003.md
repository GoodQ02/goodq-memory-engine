<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_ARCHIVED_ON: 2026-03-03 -->

# WITNESS_RUN_003 — Post-Audit Witness C (Modality Status + Truth Check)

## Purpose
Capture the first forced rerun after:
- run-level `modality_status` aggregation was added, and
- pytest discoverability normalization was completed.

This witness validates that new observability fields are emitted under real ingestion load and compares resulting truth against existing scene/phase artifacts.

## Run Context
- Input video: `samples/ingestion/09. 2002 - 2003.mp4`
- Profile: `GPU_ENHANCED`
- Forced re-ingestion: enabled (`--force`)
- Scope limiter: `--max-videos 1`
- Observer flags: `GOODQ_OBSERVE=1`, `GOODQ_OBSERVE_JSON=1`
- Witness run id: `d1de224f-6320-4669-bda4-0ca0b5498dbf`
- Code baseline (`git_sha` from resolved run config): `a0432c10cef9d38cac848d3037fc09f533f1c099`
- Command exit code: `0`

## Primary Outcome
- Run completed successfully.
- `phase6_complete=true`
- Run-level parity deterministic:
  - `qdrant_ok=true`
  - `faiss_ok=not_attempted`
- Run-level audio backend now explicitly populated:
  - `audio_backend_selected=wsl`
- New run-level modality summary is present and structured:
  - `vision_clip=available`
  - `vision_dino=available`
  - `text_embed=unavailable`
  - `audio_embed=unavailable`

## Evidence Sources
- Run artifact: `logs/scene_ingest_results.json` (latest entry for witness `video_id`)
- Step telemetry ledger: `logs/step_runs.jsonl`
- Memory commit ledger: `logs/memory_commit_events.jsonl`
- Resolved run config: `logs/scene_ingest/_resolved_config.json`
- Qdrant collections:
  - `goodq_clip_epoch_2025_12_22`
  - `goodq_dino_epoch_2025_12_22`
  - `goodq_text_epoch_2025_12_22`
  - `goodq_audio_epoch_2025_12_22`
- KG DB (from config path): `<cfg.paths.knowledge_graph_db>`

## Witness A/B/C Comparison

| Field | Witness 001 | Witness 002 | Witness 003 |
| --- | ---: | ---: | ---: |
| `scenes_total` | `19` | `19` | `19` |
| `transcript_scenes` | `18` | `19` | `17` |
| `clip vectors (video_id)` | `19` | `19` | `19` |
| `dino vectors (video_id)` | `19` | `19` | `19` |
| `phase6_complete` | `true` | `true` | `true` |
| `qdrant_ok` | `true` | `true` | `true` |
| `faiss_ok` | `not_attempted` | `not_attempted` | `not_attempted` |
| `audio_backend_selected` (run-level) | `windows` | `null` | `wsl` |
| `modality_status` | `null` | `null` | `{"vision_clip":"available","vision_dino":"available","text_embed":"unavailable","audio_embed":"unavailable"}` |

## Scene-Level Integrity Snapshot (Witness 003)
- `scenes_total=19`
- `transcript_scenes=17`
- Scene backend attribution:
  - `wsl=18`
  - `windows=0`
  - `none=1`
- Scenes with `audio_error`: `1`
- Scene-level vector parity:
  - `vector_points_attempted > 0`: `0`
  - `qdrant_ok=not_attempted` for all 19 scenes
  - `faiss_ok=not_attempted` for all 19 scenes

### Notable Scene Exceptions
1. `scene_index=0`
- `audio_backend_selected=none`
- `audio_backend_reason=audio_processing_error`
- `audio_error` persisted in scene payload.

2. `scene_index=12`
- `audio_backend_selected=wsl`
- `audio_backend_reason=wsl_transcript_success`
- `transcript=null`, `segments=[]`
- `transcript_meta.status=success` with `duration=0.0`

## Step Telemetry Summary (Witness 003)
- Step events for run id: `302`
- Status distribution:
  - `ok=302`
  - non-`ok` rows in `step_runs.jsonl`: none for this run id
- Step window (first to last step event in telemetry file): `1316.3s`

### Step Count Highlights
- `video_scene_detect`: `1`
- `scene_visual_embeddings`: `1`
- `cross_modal_harmonization`: `1`
- `image_embed_clip`: `19`
- `image_embed_dino`: `19`
- `audio_metadata`: `19`
- `audio_speaker_merge`: `19`
- `audio_music_events`: `19`
- `audio_time_hints`: `19`
- `text_embed`: `18` (all `audio_transcript` modality)
- `audio_embed_clap`: `18`
- `sentiment`: `18`
- `emotion_classify`: `18`

Interpretation: one scene shortfall in audio-derived steps matches the `scene_index=0` audio processing exception.

## Vector Store Evidence (filtered by witness `video_id`)
| Collection | Points |
| --- | ---: |
| `goodq_clip_epoch_2025_12_22` | `19` |
| `goodq_dino_epoch_2025_12_22` | `19` |
| `goodq_text_epoch_2025_12_22` | `0` |
| `goodq_audio_epoch_2025_12_22` | `0` |

This aligns with run-level `modality_status` (`text_embed/audio_embed` unavailable) and with scene-level `vector_points_attempted=0`.

## Memory Commit Evidence
`memory_commit_events.jsonl` does not include `run_id`, so witness attribution used:
- `video_id=e74f5572...26000ca`
- witness run time window.

Within witness run window:
- total events: `38`
- modalities:
  - `clip=19`
  - `dino=19`
- all `attempted=true`
- all `committed=true`

No witness-window text/audio commit rows were observed.

## Knowledge Graph Evidence
Using `<cfg.paths.knowledge_graph_db>`:
- `media_nodes` rows for canonical sample path of this video: `19`
- distinct `scene_id` for that path: `19`
- Additional `19` rows also exist for a prior diagnostic copy path sharing the same `video_hash`

Interpretation:
- KG scene coverage for this canonical sample-path video is present.
- Historical diagnostic reruns contribute additional rows for alternative media paths.

## Harmonizer Truth Cross-Check
Temporal index under `<cfg.paths.processing>/<video_stem>/temporal_index.json` reports:
- `phase6_complete=true`
- `phase6_harmonized=true`
- `harmonization_status=degraded`
- `phase6_warning=missing_audio_artifacts`
- `has_audio=false`
- `has_transcripts=false`

This conflicts with scene payload truth in run artifact (`17` transcript-bearing scenes, `18` WSL-attributed audio scenes).

This witness therefore confirms:
- pipeline completion remains true,
- but harmonizer-level audio/transcript truth remains conservative/degraded for this run.

## Retry and Control Plane
- `native_retry_count=0`
- `healer_retry_count=0`
- `control_agent_status=disabled_no_llm_client`
- `control_agent_reason=ControlAgent requires injected llm_client`

## Claim Boundaries
This witness **does claim**:
- end-to-end run success under `GPU_ENHANCED`,
- deterministic run-level parity (`qdrant_ok`/`faiss_ok`),
- deterministic non-null run-level `audio_backend_selected`,
- deterministic non-null structured `modality_status`.

This witness **does not claim**:
- full text/audio embedding coverage,
- harmonizer audio/transcript parity alignment,
- zero scene-level transcription anomalies.

