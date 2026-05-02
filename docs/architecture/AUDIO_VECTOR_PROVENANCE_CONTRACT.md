<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-01 -->

# Audio Vector Provenance Contract

This contract defines how GoodQ4All decides whether a scene has a current-run
CLAP audio vector.

It is a read-only interpretation contract for audits, API/UI read models,
retrieval status, and control recurrence reports. It does not change ingestion,
retry behavior, Qdrant payloads, or legacy vectors.

## Doctrine

Current-run audio vector success is proven only when both conditions hold:

1. The scene audio payload reports `clap_meta.status == ok`.
2. The Qdrant audio collection contains a point for the same scene with the
   same runtime `run_id` and required provenance fields.

Scene-id presence alone is not proof.

## Required Qdrant Provenance Fields

Active-line CLAP audio Qdrant payloads must carry these fields when available:

- `run_id`
- `embedding_id`
- `component`
- `step`
- `model`
- `created_at`
- `commit_ts_utc`

Expected supporting fields include:

- `scene_id`
- `video_id`
- `scene_index`
- `modality`
- `source_path`
- `audio_backend_effective`

Consumers must treat `component=audio_embed_clap` and
`step=audio_embed_clap` as the CLAP audio-vector source marker.

## Success Definition

A scene is `current_run_audio_vector_proven` only when:

- `audio.clap_meta.status == ok`
- a Qdrant audio payload exists with matching `run_id`
- the payload has the same `scene_id`
- the payload has the same `video_id` when available
- required provenance fields are present

This is the only success definition future audits, UI, retrieval status, and
recurrence reports should use for current-run audio vector coverage.

## Non-Success States

The following are not current-run audio vector success:

- a Qdrant audio point with only matching `scene_id`
- a Qdrant audio point with missing `run_id`
- a Qdrant audio point with a different `run_id`
- a legacy audio point with missing provenance fields
- `audio_embed_clap` native crash or subprocess failure
- `clap_meta.status == error`
- `clap_meta.status == skipped`
- `clap_meta.reason == audio_silent`
- `clap_meta.reason == no_text`
- a step log `step_end` without matching manifest/Qdrant proof

These may be valid operator signals, but they must not be counted as
current-run CLAP vector coverage.

## Read-Model Language

Preferred labels:

- `current_run_audio_vector_proven`
- `provenance_unverified_audio_vector_exists`
- `legacy_audio_vector_present`
- `audio_vector_absent`
- `audio_vector_skipped`
- `audio_vector_error`

Avoid using unqualified `audio_vector_exists` as a current-run success claim.
If a read model keeps that field for compatibility, it must pair it with a
provenance field that says whether the vector is current-run proven.

Compatibility fields that predate this doctrine must be read narrowly:

- `faiss.audio_vectors` means FAISS audio index count only. It is not
  current-run Qdrant proof.
- `scene_modality_coverage.has_audio_clap` means an audio CLAP commit was found
  in `memory_commit_events`. It is not current-run Qdrant proof unless paired
  with the stricter run-provenance checks above.
- `scene_modality_coverage.audio_vector_provenance_state` should carry the
  doctrine state for UI consumers. `provenance_unverified_audio_vector_exists`
  means storage evidence exists but current-run Qdrant proof has not been
  established.

## Recurrence And Audit Rules

Control recurrence reports and witness audits should compare:

- count of scenes where `clap_meta.status == ok`
- count of Qdrant audio payloads with matching `run_id`
- count of non-ok CLAP scenes
- count of non-ok CLAP scenes that nevertheless have stale or legacy Qdrant
  scene-id matches

If a scene has `clap_meta.status != ok`, a stale or legacy Qdrant point must be
reported as provenance-unverified, not as current-run success.

Optional CLAP failures remain optional failures. If authoritative scene truth,
Phase 6, and Qdrant health remain intact, they should not become blocking
solely because a stale or legacy audio vector exists.

## Witness Evidence

The one-episode baseline witness proved the happy path:

- run root: `reports/fresh_ingest_runs/20260501_114445_audio_qdrant_provenance_02x01_witness`
- runtime run id: `1fc3bddd-9eac-4051-80c7-8ff2eb76b1bd`
- 40 scenes
- 40 `clap_meta.status == ok`
- 40 current-run Qdrant audio points with required provenance

The two-episode boundary witness proved the stricter rule:

- run root: `reports/fresh_ingest_runs/20260501_153532_audio_qdrant_provenance_s2_two_episode_witness`
- runtime run id: `e0b1237e-8413-4f92-8a11-5f3d96396537`
- 78 scenes
- 75 `clap_meta.status == ok`
- 75 current-run Qdrant audio points with required provenance
- 2 `audio_embed_clap` optional native failures
- 1 `clap_meta.status == skipped` with `reason == audio_silent`
- 0 current-run Qdrant audio points for the non-ok CLAP scenes
- stale or legacy scene-id matches were not counted as current-run success

Both witnesses completed with authoritative scene truth intact, Phase 6
complete, and Qdrant health true.

## Consumer Checklist

Before reporting current-run audio vector success, a consumer must verify:

1. The scene belongs to the runtime run being audited.
2. `clap_meta.status == ok`.
3. Qdrant audio payload `run_id` matches the audited run.
4. Qdrant audio payload `scene_id` matches the scene.
5. Qdrant audio payload `video_id` matches when available.
6. Required provenance fields are present.

If any check fails, report a narrower state instead of success.

## Boundary

This contract does not:

- mutate existing Qdrant points
- backfill legacy vectors
- change CLAP inference
- change retry behavior
- change Phase 6
- activate ControlAgent
- enable healing
- create a second recurrence engine

It only defines how existing and future truth surfaces should be interpreted.
