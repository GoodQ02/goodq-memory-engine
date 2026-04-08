<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-08 -->

# Phase 6: Multimodal Fusion & Temporal Indexing

**Status:** ✅ Wired and operational  
**Scope:** Phase 6a visual embeddings + Phase 6b cross-modal harmonization

Phase 6 consumes persisted scene artifacts and converts them into:
- scene-level CLIP/DINO vector truth
- Qdrant commits
- `temporal_index.json`
- top-level `phase6_status` / `phase6_complete` truth

It is backend-agnostic once the required scene and audio artifacts exist.

---

## Phase 6 Structure

### Phase 6a: Scene Visual Embeddings

**Module**
- `steps/video/scene_visual_embeddings.py`

**Responsibilities**
- load `scene_manifest.json`
- gather representative frame evidence
- finalize CLIP and DINO scene-vector state
- write `clip_id`, `dino_id`, `qdrant_ok`
- set `phase6_status` / `phase6_complete`

**Primary Outputs**
- scene-level vector ids
- top-level Phase 6 truth fields
- Qdrant writes into:
  - `goodq_clip_epoch_<epoch>`
  - `goodq_dino_epoch_<epoch>`

### Phase 6b: Cross-Modal Harmonization

**Module**
- `steps/video/cross_modal_harmonizer.py`

**Responsibilities**
- consume the persisted scene bundle
- align visual, transcript, diarization, entity, and timing surfaces
- persist additive harmonized scene truth back into `scene_manifest.json`
- build the canonical temporal rollup

**Primary Output**

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video_name>/temporal_index.json
```

---

## Canonical Inputs

Phase 6 consumes persisted scene artifacts, not ad hoc in-memory guesses.

### Required Inputs

- `video/scene_manifest.json`

### Common Input Surfaces Used

- `caption`
- `ocr_text`
- `objects`
- `faces`
- `tags`
- `entities`
- `audio.transcript`
- `audio.diarization`
- `audio.speaker_transcript`
- `audio.speaker_voice_signatures`
- backend truth fields (`audio_backend_*`)

When WSL audio is enabled, Phase 6 consumes WSL-produced transcript/diarization/signature outputs through the same manifest contract. When Windows-local audio is used, the same downstream contract still applies.

---

## Canonical Outputs

### Scene Manifest Updates

Phase 6a writes or finalizes:
- `clip_id`
- `dino_id`
- `qdrant_ok`
- `phase6_status`
- `phase6_complete`

### Temporal Index

Phase 6b writes:

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video_name>/temporal_index.json
```

The temporal index is the canonical multimodal rollup for:
- content summary
- per-scene timeline segments
- entity aggregation
- object and location summaries
- perception context including:
  - visible person-object counts
  - audio emotion
  - music event labels
  - time-hint rollups
  - speaker voice-signature coverage
- interaction context including:
  - `candidate_visible_people` (conservative physical-presence candidates)
  - `conversation_owner` (dominant interaction participant, not visual presence)

---

## Artifact Locations

### Scene Manifest

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video_name>/video/scene_manifest.json
```

### Temporal Index

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video_name>/temporal_index.json
```

### Harmonized Scene Truth

Phase 6b also writes additive scene-level harmonized fields back into the persisted scene bundle. Common fields now include:
- `scene_present_entities`
- `dialogue_mentioned_entities`
- `visible_people`
- `mentioned_people`
- `candidate_visible_people`
- `conversation_owner`
- `continuity_key`
- `dominant_speaker_id`
- `dominant_speaker_share`
- `dominance_confidence`
- `visible_person_object_count`
- `speaker_voice_signature_count`
- `audio_emotion`
- `music_events`
- `time_hints`

### Qdrant Collections

- `goodq_clip_epoch_<epoch>`
- `goodq_dino_epoch_<epoch>`

The epoch processing tree is the canonical artifact root. Compatibility fallbacks may exist in code, but they are not the active operator truth.

---

## Runtime Truth

### What Healthy Phase 6 Looks Like

On a successful witness:
- `phase6_status = complete`
- `phase6_complete = true`
- `qdrant_ok = true`
- CLIP and DINO scene vectors are committed
- `temporal_index.json` exists and reflects actual scene payload truth

### What Partial Failure Looks Like

Phase 6 may still proceed under partial upstream scene failures when the scene bundle remains canonical and truthful.

For example:
- isolated keyframe-step failure on one scene
- recovered DINO retry
- optional audio enrichment failure

These should not be described as “Phase 6 not wired” or “future” behavior.

---

## DINO And Vision-Step Containment

Current runtime quality truth:
- DINO is operational
- native DINO crashes may still occur
- staged containment is in place

Current retry ladder for DINO:
1. normal GPU attempt
2. GPU retry with AMP disabled
3. CPU fallback if policy requires it

The purpose of this containment is to preserve run integrity and truthful scene state, not to hide the failure.

---

## Harmonization Truth

`cross_modal_harmonizer.py` now derives rollup truth from actual scene payload content rather than stale scene labels.

That includes:
- `content_summary`
- `signal` vs `empty` vs `processing_error`
- `top_entities`
- `top_objects`
- place/location lift from visual semantics
- speaker continuity and dominance truth
- additive interaction ownership (`conversation_owner`) without promoting visual presence
- richer perception context from already-produced audio metadata

This means Phase 6 is now part of memory truth, not just a convenience layer.

---

## Verification Checklist

Verify Phase 6 with current artifacts, not with historical prose.

Healthy verification should show:

1. `scene_manifest.json` exists under the epoch processing tree.
2. `temporal_index.json` exists under the epoch processing tree.
3. `phase6_complete = true` on successful episodes.
4. `qdrant_ok = true` for successful scene-vector commits.
5. `temporal_index.json` matches the fresh semantic outputs rather than collapsing to placeholders.
6. harmonized scene fields in `scene_manifest.json` match the per-segment truth in `temporal_index.json`.

### Practical Inspection

For fresh benchmark verification, inspect:
- `scene_manifest.json`
- `temporal_index.json`
- `scene_ingest_results.json`

Useful truth fields to grep:
- `visible_person`
- `audio_emotion`
- `music`
- `time_hints`
- `speaker_voice`
- `conversation_owner`

---

## Common Failure Modes

### `no_scene_manifest`

Cause:
- scene manifest missing or scene processing failed too early

Meaning:
- Phase 6 was skipped correctly because required scene truth was unavailable

### Qdrant Unavailable

Cause:
- Qdrant not running or unreachable

Meaning:
- Phase 6 scene-vector persistence cannot complete canonically

### Partial Upstream Scene Failures

Cause:
- one or more visual or optional audio steps failed for a scene

Meaning:
- Phase 6 should still consume the truthful bundle if the non-action contract allows it

---

## Related Documentation

- [SCENE_MANIFEST_SPECIFICATION.md](SCENE_MANIFEST_SPECIFICATION.md)
- [SYSTEM_ARCHITECTURE.md](architecture/SYSTEM_ARCHITECTURE.md)
- [ARCHITECTURE_REFERENCE.md](architecture/ARCHITECTURE_REFERENCE.md)
- [WSL_AUDIO_RUNTIME.md](reference/WSL_AUDIO_RUNTIME.md)
- [IDENTITY_STITCHING_CONTRACT.md](architecture/IDENTITY_STITCHING_CONTRACT.md)

---

## Summary

Phase 6 is no longer a “planned” or “available but not wired” component. It is an operational fusion layer that:
- finalizes scene-level visual vector truth
- commits canonical CLIP/DINO scene vectors to Qdrant
- writes a durable multimodal temporal index
- carries stitching-era semantic and audio surfaces into retrieval and memory
- exposes richer situational-awareness context without relaxing visible-person truth
