<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-03-26 -->

# Segmentation Artifact Contract

This document freezes the Wave 1 shadow-mode artifact contract for the phased segmentation engine.

## Scope

This contract applies to the segmentation engine sidecar rooted at:

- `<processing_dir>/_segmentation_shadow/<video_stem>/`

It does not change the canonical live ingest path. Until explicit promotion, current scene-first ingest remains authoritative.

## Naming

To avoid the historical naming collision:

- `SEG_P0` ... `SEG_P6` refer only to segmentation engine phases.
- `Project Phase N` refers to milestone and program-level phase documents elsewhere in the repo.

The segmentation engine phases are:

1. `SEG_P0` normalization
2. `SEG_P1` VAD segmentation
3. `SEG_P2` pyannote refinement
4. `SEG_P3` smart chunk building
5. `SEG_P4` heavy audio enrichment
6. `SEG_P5` chunk-aware video scene alignment
7. `SEG_P6` final segmentation manifest integration

## Contract Version

- `contract_name`: `goodq_segmentation_shadow_contract`
- `contract_version`: `1`

## Authority Model

Authoritative artifacts:

- live ingest `video/scene_manifest.json`
- live ingest `temporal_index.json`
- live ingest persistent scene/audio memory

Derived shadow artifacts:

- shadow `audio/segmentation.json`
- shadow `metadata/segmentation_enhanced.json`
- shadow `video/scene_manifest.json`
- shadow `metadata/segmentation.json`
- shadow `shadow_summary.json`
- shadow `shadow_metrics.json`

Shadow artifacts are comparison-only until a later explicit cutover.

## Paths

Required shadow artifact paths:

1. `audio/segmentation.json`
2. `video/scene_manifest.json`
3. `shadow_summary.json`

Conditionally required shadow artifact paths:

1. `metadata/segmentation_enhanced.json`
2. `metadata/segmentation.json`
3. `shadow_metrics.json`

Conditional rules:

- `metadata/segmentation_enhanced.json` is expected when `SEG_P4` is not skipped.
- `metadata/segmentation.json` is expected when `SEG_P6` is not skipped.
- `shadow_metrics.json` is expected when `segmentation.metrics_output=true`.

## Artifact Schemas

### `audio/segmentation.json`

Purpose:
- canonical output of `SEG_P3`
- upstream chunk contract for later shadow phases

Required fields:

- `segments`: list
- `chunks`: list

Optional fields:

- `manifest_path`
- chunk dictionaries with `id`, `start`, `end`, `duration`, `chunk_path`, `vad_speech`

Rules:

- `segments` and `chunks` must describe the same chunk set.
- `chunks` is the preferred producer label.
- `segments` is the compatibility alias for downstream consumers that still expect segment terminology.

### `metadata/segmentation_enhanced.json`

Purpose:
- canonical output of `SEG_P4`
- enriched chunk transcript/speaker/audio metadata

Required fields when present:

- `segments`: list
- `chunks`: list
- `phase4_complete`: bool

Optional fields:

- `processed_segment_count`
- segment-level `transcript`
- segment-level `transcript_segments`
- segment-level `diarization`
- segment-level `speakers`

Rules:

- `segments` and `chunks` must remain equivalent aliases.
- this file is derived from `audio/segmentation.json`

### `video/scene_manifest.json`

Purpose:
- canonical output of `SEG_P5`
- shadow scene alignment contract

Required fields:

- `video_id`
- `video_path`
- `phase5_complete`
- `total_scenes`
- `scenes`: list
- `aligned_segments`: list

Required scene fields:

- `scene_id`
- `index`
- `start`
- `end`

Rules:

- `scene_id` and `index` are required even in shadow mode.
- `aligned_segments` is the comparison surface for shadow alignment scoring.

### `metadata/segmentation.json`

Purpose:
- canonical output of `SEG_P6`
- integration-ready segmentation manifest

Required fields when present:

- `version`
- `schema`
- `source`
- `summary`
- `segments`
- `frame_index`
- `processing`

Rules:

- this file is the shadow-side integration artifact, not yet the live `temporal_index.json`
- its presence is the highest shadow readiness signal before downstream temporal-index promotion

### `shadow_summary.json`

Purpose:
- execution summary for the shadow run

Required fields:

- `activation`
- `status`
- `reason`
- `skip_phases`
- `output_dir`

Recommended fields:

- `audio_manifest_path`
- `phase4_manifest_path`
- `scene_manifest_path`
- `segmentation_manifest_path`
- `validation`
- `timings`

### `shadow_metrics.json`

Purpose:
- comparison summary between live ingest outputs and shadow artifacts

Required fields:

- `scene_count_delta`
- `transcript_coverage_delta`
- `speaker_coverage_delta`
- `alignment_score`
- `temporal_index_completeness_current`
- `temporal_index_completeness_shadow`
- `temporal_index_completeness_delta`

Rules:

- `alignment_score` is a heuristic comparison metric derived from `aligned_segments`
- `temporal_index_completeness_shadow` is a readiness score until the shadow path writes a true temporal index

## Adapter Rules

The compatibility adapter must remain a pure shape adapter.

Allowed:

- `chunks` -> `segments` aliasing
- flattening SEG_P4 transcript and diarization fields into SEG_P6 inputs
- normalizing scene indexing metadata

Not allowed:

- mutating authoritative live ingest artifacts
- changing semantic content during adaptation
- using adapter code to introduce side effects or persistence decisions

## Promotion Guardrails

Before any shadow artifact becomes authoritative:

1. shadow metrics must exist
2. transcript coverage deltas must be reviewed on witness runs
3. speaker coverage deltas must be reviewed on witness runs
4. scene-count and alignment deltas must be reviewed against current Phase 6 behavior
5. cutover must happen behind explicit config, not by changing defaults
