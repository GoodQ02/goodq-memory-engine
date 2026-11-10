<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-27 -->

# Vision Processing Pipeline

**Status:** Existing production pipeline; perception quality is not fully accepted.
**Current scope review:** October 24, 2026; the detailed runtime history remains dated.
**Scope:** Scene detection, keyframe extraction, visual embedding generation, and Phase 6a/6b integration

Image/video OCR uses the pinned PaddleOCR PP-OCRv6 medium detector and recognizer
through ONNX Runtime. The replacement qualification and remaining recognition
limits are recorded in the `perception assessment` (omitted from public source).
Object detection runs `opencv_yolox` on ONNX Runtime CUDA in `envs/object_detect/.venv` (with CPU retry), and scene captioning runs `tencent/WeVisOne-VL-2B` in `envs/caption_vlm/.venv` once per scene across sampled frames. [PROJECT.md](../../../PROJECT.md)
owns the deployment checkpoint and the fresh context/UI witness.

---

## Overview

The vision pipeline performs video segmentation, extracts optimal keyframes, processes representative visual cues, and commits embeddings for search parity.

The flow consists of:
1. **Scene Detection (`gpu_scene_detect.py`)**: Vectorized GPU-accelerated frame difference calculations in PyTorch.
2. **Keyframe Extraction (`scene_frame_extractor.py`)**: OpenCV-native seeking and multi-criteria keyframe selection (Entropy, Laplacian, Motion).
3. **Visual Extraction Steps**:
```text
scene keyframe
  -> OCR
  -> image caption (WeVisOne-VL-2B)
  -> object detection (YOLOX / NanoDet CPU fallback)
  -> face embedding / face metadata
  -> DINOv2-Large embedding (1024-d)
  -> CLIP-ViT-Large embedding (768-d)
  -> tagger / semantic lift
  -> scene bundle + KG + Phase 6
```

These steps are operational. They are not latent or “future” capabilities.

---

## Pre-Extraction and Segmentation

Before individual scene analysis begins, the video source undergoes high-performance preprocessing:

### 1. Vectorized GPU Scene Detection (`gpu_scene_detect.py`)
- **Acceleration**: Frame differences are calculated directly on the GPU using PyTorch tensors.
- **Batching**: Reduces CPU-GPU synchronization bottlenecks by processing frame buffers in batches and performing a single GPU-to-CPU sync per batch.
- **Robustness**: Automatically handles initialization edges and flags cuts when mean absolute difference exceeds the dynamic threshold.

### 2. OpenCV-Native Keyframe Seeking (`scene_frame_extractor.py`)
- **OpenCV Direct Path**: Uses native `cv2.VideoCapture` seeking and frame decoding in Python to bypass FFmpeg subprocess spawning overhead.
- **Fallback**: Spawns an FFmpeg child process only if OpenCV cannot open or seek within the media container.
- **Advanced Keyframe Selection**: Evaluates candidate frames in each scene across three visual dimensions to pick the single most representative frame:
  - *Shannon Entropy*: Selects frames with the highest informational texture and color complexity.
  - *Laplacian Variance*: Rejects motion-blurred or out-of-focus frames in favor of high sharpness.
  - *Motion Peaks*: Captures frames corresponding to high action or change.

---

## Canonical Runtime Surfaces

### Keyframe Artifact

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video_name>/video/scene_XXXX.jpg
```

### Canonical Bundle

Each scene’s visual outputs persist into:

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video_name>/video/scene_manifest.json
```

Those persisted outputs are then consumed by:
- `lib/kg_realtime_integration.py`
- `steps/video/scene_visual_embeddings.py`
- `steps/video/cross_modal_harmonizer.py`

---

## Active Vision Steps

### 1. `image_ocr`

**Purpose**
- extract visible text while retaining its original source evidence

**Runtime and outputs**
- `goodq_ocr` resolves a dedicated project-local OCR interpreter. The pinned
  dependencies are in `envs/ocr/requirements.txt` and `envs/locks/ocr.lock.txt`;
  model identities and file hashes are in `configs/model_registry.yaml`.
- `image_ocr.device` explicitly selects `cpu` or `cuda:0`. A selected CUDA
  provider must initialize and execute kernels; a whole-session CPU fallback
  fails visibly. Native ONNX placement of individual CPU nodes is reported.
  GPU workers share the host reservation owner and release claims on exit or
  cancellation. The 16 GB host witness does not qualify untested 8/6 GB devices.
- `ocr_text` and `ocr_meta.accepted_regions` retain native text, source-pixel boxes,
  polygons and recognizer sequence scores. Scores are model evidence, not
  calibrated probabilities. Mismatched arrays and malformed geometry fail visibly.
  New Paddle ledger rows label their required numeric aggregate as the arithmetic
  mean of retained recognizer sequence scores, with its observation count. Raw
  region scores remain unchanged. Historical presence scores keep their meaning.
- Both video callers and standalone-image ingestion use one native Paddle pass.
  Tesseract, image variants, crop agreement, enhancement retries and automatic OCR
  engine fallback are retired. Historical records retain their original engine
  labels and score meanings; they are not reinterpreted as Paddle results.
- `ocr_meta` records both pinned model revisions, actual provider execution,
  settings fingerprint, source hash and frame timestamp. Scene aggregation retains
  per-sample evidence. A missing selected model/provider is an error; `no_text`
  means no admitted native reading, not proof that no visible text exists.
- Dates are a separate calendar-valid interpretation of raw observed text.
  `date_evidence` links interpreted or uncertain dates to their exact text, box,
  polygon and frame offset. Invalid dates are not promoted; ambiguous numeric
  order or century remains uncertain. No character insertion or engine-specific
  repair changes the native reading.
- Runtime inference uses verified local assets and disables remote model checks.
  The local environment resolves the experimental dependency conflict without
  altering audio, location or core environments. Packaging qualification is
  recorded separately from local runtime qualification.

### 2. `image_caption`

**Purpose**
- generate a natural-language description of the keyframe

**Typical Output Fields**
- `caption`
- `caption_meta`

**Behavior**
- runs the sealed `tencent/WeVisOne-VL-2B` (`3dad9ce8bcb6fbe0aea945bf8860bd2cfc3663bf`) model inside `envs/caption_vlm/.venv` (`goodq_caption_vlm`), loading the model once per scene across all sampled frames (`samples: [...]`)
- deterministic greedy decoding (`max_new_tokens=256`, `do_sample=False`) with `caption_meta.inference_kind = "model_generated_description"`
- hedged place clauses in VLM descriptions (`possibly a home office or living room`) are suppressed by `is_hedged_mention` before place entity extraction or setting-hint derivation

### 3. `object_detect`

**Purpose**
- detect visible objects and contribute location/context cues

**Typical Output Fields**
- `objects`
- `detect_meta`

**Behavior**
- object inventory is retained as structural scene evidence
- object labels may also support conservative place inference in the semantic layer

### 4. `face_embed`

**Purpose**
- emit structural face detections and embeddings for identity-related evidence

**Typical Output Fields**
- `faces`
- `faces_meta`

**Behavior**
- face nodes are structural inputs to the identity ladder
- a detected face is not automatically a person identity

### 5. `image_embed_dino`

**Purpose**
- emit semantic image embeddings for similarity and Phase 6

**Typical Output Fields**
- `dino_embedding`
- `dino_meta`

**Current Runtime Truth**
- DINO is operational using **`facebook/dinov2-large`** (producing **1024-dimensional** vectors)
- processes frame paths in a single flattened batch wrapped in `torch.inference_mode()` and half-precision FP16 Autocast for optimal performance
- direct DINO writes to the configured DINO FAISS index and `dino_id_map`
- direct DINO requires explicit-ID FAISS support; legacy non-IDMap indexes fail visibly instead of falling back to position-based writes
- generic embedding metadata uses modality `dino`, not a collapsed `image` label
- native crashes may still occur
- ingestion now contains staged containment:
  - first attempt: normal GPU
  - retry: GPU with AMP disabled
  - final fallback: CPU if required by policy

### 6. `image_embed_clip`

**Purpose**
- emit multimodal image embeddings for retrieval and harmonization

**Typical Output Fields**
- `clip_embedding`
- `clip_meta`

**Behavior**
- CLIP is operational using **`openai/clip-vit-large-patch14`** (producing **768-dimensional** vectors)
- processes frame paths in a single flattened batch under `torch.inference_mode()` and mixed-precision Autocast
- direct CLIP writes to the configured CLIP FAISS index and `clip_id_map`
- direct CLIP requires explicit-ID FAISS support; legacy non-IDMap indexes fail visibly instead of falling back to position-based writes
- generic embedding metadata uses modality `clip`, not a collapsed `image` label
- CLIP and DINO are committed during Phase 6a when successful

### 7. `tagger`

**Purpose**
- lift text and visual context into semantic entities/tags

**Typical Output Fields**
- `tags`
- semantic entities surfaced through the scene bundle and KG

**Current Runtime Truth**
- thin semantic scaffolding noise is suppressed
- the taste layer now rejects filler/fragments and known joke aliases
- conservative place inference from captions/objects is active
- explicit bathroom captions are recognized; a sink alone does not identify a room
- object-based room inference requires every defining detection to meet the rule's
  existing confidence level; missing, invalid and weaker scores remain object
  evidence without becoming stronger room claims. Matched detector scores remain
  in the inferred entity's provenance. These are candidates, not verified places.

---

## What the Vision Layer Produces

The visual stack contributes to these important scene-bundle fields:

- `ocr_text`
- `caption`
- `objects`
- `faces`
- `tags`
- `entities`
- `frame_text`
- `clip_id`
- `dino_id`
- `qdrant_ok`
- `faiss_ok`

When steps fail partially, the scene should still retain:
- the true failing step
- raw error text when available
- enough truth for downstream systems to classify the scene accurately

---

## Integration With Phase 6

### Phase 6a

`steps/video/scene_visual_embeddings.py` reads the persisted manifest and finalizes CLIP/DINO scene-vector status, including:
- scene-level `clip_id`
- scene-level `dino_id`
- `qdrant_ok`
- `faiss_ok`
- top-level `phase6_status`
- top-level `phase6_complete`

Phase 6a is launched through the visual embedding environment
`goodq_image_caption`, which owns CLIP/DINO/Torch/FAISS dependencies. It writes
Qdrant as the canonical vector surface and writes FAISS parity when configured.
If FAISS parity cannot be written, the scene remains Qdrant-valid but the
manifest must expose the FAISS reason instead of silently reporting success.
Phase 6a also requires explicit-ID FAISS support for its parity writes.

### Phase 6b

`steps/video/cross_modal_harmonizer.py` uses visual and audio scene truth to build:

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video_name>/temporal_index.json
```

This rollup now uses actual scene payload truth rather than stale labels.

---

## Failure Model

The vision pipeline is designed to be resilient, not brittle.

### Non-Blocking Failures

These are allowed:
- isolated OCR failure
- isolated caption failure
- isolated object-detect failure
- contained DINO crash with retry/fallback
- optional enrichments missing for one scene

### Required Truth

Not allowed:
- masking a keyframe-step crash as generic frame extraction failure
- silently dropping the real failing step
- letting one vision-step failure invalidate an otherwise healthy scene bundle

---

## Current Known Runtime Edges

- native `image_caption` and `object_detect` crashes still occur occasionally in long witnesses
- DINO is resilient now, but still not fully cured of native edge cases
- optional steps may fail while the scene and video remain canonical

These are runtime-quality issues, not contract ambiguities.

---

## Verification Checklist

On a healthy witness:

1. `scene_XXXX.jpg` keyframes exist in the epoch processing tree.
2. Scene bundles persist visual outputs in `scene_manifest.json`.
3. `phase6_complete = true` and `qdrant_ok = true` for healthy episodes.
4. `faiss_ok = true` only when configured CLIP/DINO FAISS parity writes used
   explicit stable IDs.
5. `temporal_index.json` reflects the visual evidence rather than collapsing to generic summaries.
6. Placeholder semantic junk does not dominate `top_entities`.

---

## Related Documentation

- [SCENE_MANIFEST_SPECIFICATION.md](../SCENE_MANIFEST_SPECIFICATION.md)
- [PHASE6_MULTIMODAL_FUSION.md](../PHASE6_MULTIMODAL_FUSION.md)
- [SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md)
- [IDENTITY_STITCHING_CONTRACT.md](../IDENTITY_STITCHING_CONTRACT.md)

---

## Summary

The vision pipeline is no longer just a pre-Phase-6 keyframe helper. It is a production scene-evidence layer that:
- enriches scene bundles
- feeds realtime KG updates
- supports semantic rollups
- supplies embeddings to Phase 6 and Qdrant
- stays resilient under partial failure rather than collapsing the ingest
