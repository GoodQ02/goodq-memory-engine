# Scene Manifest Specification

**Status:** ✅ **STABLE AND OPERATIONAL**
**Last Verified:** April 24, 2026
**Evidence:** fresh Season 5 projection smoke artifacts produced epoch-scoped manifests with active WSL audio, persisted diarization/emotion truth, speaker continuity, and additive harmonized scene fields

---

## Overview

`scene_manifest.json` is the canonical per-video artifact emitted by ingestion. It is the handoff surface between scene processing, Phase 6, retrieval, and the identity formation layer.

It is authoritative for:
- scene boundaries and scene ids
- keyframe-derived visual outputs
- scene-level audio outputs
- backend truth (`audio_backend_*`, `phase6_*`)
- speaker-owned transcript alignment
- per-speaker voice signatures used by stitching
- additive harmonized scene truth written by Phase 6b

### Location

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video_name>/video/scene_manifest.json
```

**Example**

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/epoch_2025_12_22/processing/01x01 - Good News, Bad News/video/scene_manifest.json
```

### Creation

- **Owner:** `cli/run_ingestion.py`
- **Write point:** scene processing completes before Phase 6 consumes the manifest
- **Consumers:** `scene_visual_embeddings.py`, `cross_modal_harmonizer.py`, API/loaders, identity ledger rebuilds

---

## Top-Level Structure

```json
{
  "video_id": "7215a98e...",
  "video_path": "${GOODQ_DATA_ROOT}/GoodQ_Data/import_inbox/...",
  "phase6_status": "complete",
  "phase6_complete": true,
  "scenes": [...]
}
```

### Required Top-Level Fields

- `video_id`
- `video_path`
- `phase6_status`
- `phase6_complete`
- `scenes`

`phase6_status` and `phase6_complete` are the canonical Phase 6 truth surface for the video bundle.

---

## Scene Object

Each scene entry contains the scene boundary, keyframe outputs, audio outputs, vector-store truth, and additive harmonized scene context.

```json
{
  "scene_id": "7fde117a...",
  "index": 0,
  "start": 0.0,
  "end": 4.171,
  "duration": 4.171,
  "confidence": 1.0,
  "clip_id": "clip_scene_...",
  "dino_id": "dino_scene_...",
  "qdrant_ok": true,
  "speaker_ids": ["SPEAKER_00"],
  "speaker_count": 1,
  "keyframe": {...},
  "audio": {...}
}
```

### Common Scene-Level Truth Fields

- `clip_id`, `dino_id`
- `qdrant_ok`
- `speaker_ids`
- `speaker_count`
- `scene_context_llm` (feature-gated additive interpretation)
- `scene_context_epistemic` (additive self-audit payload describing evidence dominance, fallback mode, and limits)
- `scene_context_arbitration` (additive read-model payload preserving disagreements, hypotheses, and unresolved axes)
- `continuity_key`
- `dominant_speaker_id`
- `dominant_speaker_share`
- `dominance_confidence`
- `visible_person_object_count`
- `speaker_voice_signature_count`
- `speaker_voice_signature_meta`
- `diarization_status`
- `diarization_error`
- `diarization_note`
- `audio_emotion`
- `emotion_status`
- `emotion_error`
- `music_events`
- `time_hints`
- `candidate_visible_people`
- `speaker_aligned_mentions`
- `interaction_dominance`
- `conversation_owner`

`speaker_ids` may still contain structural diarization labels such as `SPEAKER_00`. Those labels are not semantic identity by themselves.

`speaker_aligned_mentions`, `interaction_dominance`, and `conversation_owner`
are additive interaction/read-model fields. They must not be treated as direct
identity promotion.

Transcript/entity disagreement reporting is derived later from the persisted
scene surface at temporal-index projection time. It is an operator visibility
layer rather than a scene-manifest write contract of its own.

### `scene_context_llm` Contract

When `scene_context_llm` is present, it is an additive interpretation payload with an explicit
three-tier tag model:

- `primary_tags`: meaning-driving scene topics or anchors
- `contextual_tags`: environmental or situational memory cues
- `structural_tags`: low-value scaffolding retained only for weak-scene continuity

The compatibility field `context_tags` remains available for downstream consumers, but it is
derived from the tiered lanes rather than replacing them.

Tier-array rules:

- `primary_tags`, `contextual_tags`, and `structural_tags` must be present as arrays
- low-signal scenes still use explicit empty arrays instead of `null`
- missing or `null` tier arrays should be treated as malformed legacy payloads, not as the
  normative manifest shape

---

## Keyframe Object

The `keyframe` object contains the representative frame path and the consolidated outputs of the visual step stack.

```json
"keyframe": {
  "path": "${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video>/video/scene_0000.jpg",
  "timestamp": 2.0855,
  "scene": {
    "start": 0.0,
    "end": 4.171,
    "duration": 4.171
  },
  "ocr_text": "Text detected in frame",
  "caption": "a person sitting at a desk",
  "caption_meta": {
    "status": "ok"
  },
  "objects": [],
  "detect_meta": {
    "status": "ok"
  },
  "faces": [],
  "faces_meta": {
    "status": "ok"
  },
  "dino_meta": {
    "status": "ok"
  },
  "clip_meta": {
    "status": "ok"
  },
  "tags": [],
  "usefulness": 0.42,
  "entities": [],
  "frame_text": "Combined scene description"
}
```

### Keyframe Truth Notes

- The representative frame lives in the epoch processing tree, not `logs/scene_ingest`.
- Partial failures are allowed. A scene may remain canonical even if one visual step fails.
- When a keyframe step fails, the scene should preserve the real failing step and raw error surface instead of reporting a generic frame-extraction failure.

Common visual error fields that may appear on scene outputs:
- `keyframe_error`
- `keyframe_error_step`
- `keyframe_error_env`
- `keyframe_error_raw`

---

## Audio Object

The `audio` object contains scene audio outputs, backend attribution, diarization, speaker transcript alignment, and voice-signature payloads.

```json
"audio": {
  "path": "${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video>/audio/scene_0000.wav",
  "start": 0.0,
  "end": 4.171,
  "duration": 4.171,
  "audio_backend_selected": "wsl",
  "audio_backend_effective": "wsl",
  "audio_backend_downgraded": false,
  "transcript": "look at it it's too high",
  "transcript_meta": {
    "status": "success",
    "engine": "wsl_unified",
    "device": "cuda"
  },
  "diarization": [],
  "diarization_meta": {
    "status": "ok"
  },
  "speaker_transcript": [],
  "speaker_voice_signatures": [],
  "speaker_voice_signature_meta": {
    "status": "ok",
    "emitted": 0,
    "attempted_speakers": 0,
    "min_voiced_seconds": 4.0,
    "min_segment_count": 2
  },
  "emotions": [],
  "emotion_meta": {
    "status": "ok"
  },
  "clap_meta": {
    "status": "ok"
  },
  "embeddings": [],
  "embedding_dim": 768,
  "wsl2_unified": true,
  "gpu_used": true
}
```

### Canonical Audio Backend Fields

These fields are authoritative:

- `audio_backend_selected`
- `audio_backend_effective`
- `audio_backend_downgraded`

Interpretation:
- `selected`: requested backend policy
- `effective`: backend that actually completed the scene
- `downgraded`: whether fallback occurred during the scene

### Speaker Transcript and Stitching Fields

These fields are now part of the manifest contract:

- `speaker_transcript`
- `speaker_voice_signatures`
- `speaker_voice_signature_meta`
- `emotion` / `emotion_scores`
- `music_events`
- `time_hints`

They are the input surface for the ladder defined in `docs/architecture/IDENTITY_STITCHING_CONTRACT.md`.

`speaker_voice_signatures` should only be emitted when the runtime has enough stable voiced speech:
- at least `4.0` seconds total voiced duration
- at least `2` distinct usable segments

### CLAP Audio Vector Success

`audio.clap_meta` is the scene-level CLAP status surface.

Current-run audio vector success is proven only when:

- `audio.clap_meta.status == ok`
- the Qdrant audio collection contains a payload for the same `scene_id`
- the Qdrant payload has the same runtime `run_id`
- required provenance fields are present on that payload

Matching `scene_id` alone is not proof. Legacy Qdrant audio points without
`run_id`, points from a different `run_id`, `clap_meta.status == error`, and
`clap_meta.status == skipped` are not current-run audio vector success.

Use `docs/architecture/AUDIO_VECTOR_PROVENANCE_CONTRACT.md` as the full
consumer contract for audits, UI/API read models, retrieval status, and
control recurrence reporting.

---

## Consumers

### Operational Consumers

1. **Scene Visual Embeddings** (`steps/video/scene_visual_embeddings.py`)
   - Reads `scene_manifest.json`
   - Writes CLIP/DINO vector status back into scene/video truth

2. **Cross-Modal Harmonizer** (`steps/video/cross_modal_harmonizer.py`)
   - Reads `scene_manifest.json`
   - Produces `temporal_index.json`
   - Writes additive harmonized scene truth back into `scene_manifest.json`
   - Uses scene payload truth, not stale labels, for `content_summary`

3. **Realtime KG Integration** (`lib/kg_realtime_integration.py`)
   - Consumes scene bundles during ingestion
   - Uses transcript, speaker alignment, voice signatures, captions, OCR, objects, and tags

4. **Identity Ledger Rebuilds** (`lib/identity_ledger.py`, `scripts/build_identity_ledger.py`)
   - Consume scene manifests and KG edges
   - Surface `identity_candidate`, `identity_supported`, and `identity_evidence`

5. **API / Loader Surfaces**
   - Read manifests from the epoch processing tree
   - Serve scene truth to local UI/API helpers when enabled

---

## Validation Rules

### Structure

Required:
- top-level JSON parse succeeds
- `scenes` is present and ordered
- each scene has `scene_id`, `index`, `start`, `end`, `duration`
- `keyframe.path` and `audio.path` resolve inside the epoch processing tree

### Truth Surfaces

Required:
- `audio_backend_*` fields reflect real backend behavior
- `phase6_status` / `phase6_complete` reflect actual Phase 6 outcome
- scene vector status resolves through `qdrant_ok`
- additive harmonized fields must remain truthful and non-destructive; they may enrich the scene bundle, but they must not overwrite raw upstream scene evidence

### Partial Failure Semantics

Allowed:
- a scene may remain canonical with partial visual or optional-audio failures
- optional enrichments may fail without invalidating the manifest

Not allowed:
- masking the failing step behind a generic extraction error
- silently suppressing backend downgrade truth

---

## Known Active Issues

### 1. Partial Scene Errors Still Occur

Some witness runs still surface isolated native crashes in visual steps such as `image_caption`, `object_detect`, or `image_embed_dino`. The manifest remains canonical when:
- the scene bundle is persisted
- the failing step is attributed truthfully
- the run continues under the non-action contract

### 2. Structural Speaker Labels Are Not Identity

`SPEAKER_00`-style labels are structural diarization outputs. They are inputs to the stitching layer, not semantic identities.

### 3. Voice Pattern Capture Is Distinct From Identity Promotion

The presence of `speaker_voice_signatures` does not imply that identity promotion should occur. Promotion remains evidence-based and conservative.

### 4. Interaction Ownership Is Additive, Not Guaranteed

`conversation_owner` and `interaction_dominance` are active harmonization
surfaces, but they may still be absent on many healthy scenes. Strong speaker
continuity does not imply that these higher-level ownership fields will be
dense on every episode.

---

## Related Documentation

- [INGEST_ORCHESTRATION_CONTRACT.md](architecture/INGEST_ORCHESTRATION_CONTRACT.md)
- [IDENTITY_STITCHING_CONTRACT.md](architecture/IDENTITY_STITCHING_CONTRACT.md)
- [PHASE6_MULTIMODAL_FUSION.md](PHASE6_MULTIMODAL_FUSION.md)
- [WSL_AUDIO_RUNTIME.md](reference/WSL_AUDIO_RUNTIME.md)
- [SYSTEM_ARCHITECTURE.md](architecture/SYSTEM_ARCHITECTURE.md)

---

## Summary

`scene_manifest.json` is the canonical per-video scene bundle. It is no longer just a segmentation artifact; it is the durable truth surface for:
- multimodal scene data
- backend attribution
- Phase 6 completion
- speaker-owned transcript alignment
- voice-signature capture used by identity stitching
- additive perception and interaction context written by harmonization
