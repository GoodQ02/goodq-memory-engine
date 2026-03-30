<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-03-26 -->

# GoodQ4All Environment Index

**Purpose:** Map the current supported Windows and WSL environments to their roles in the live pipeline.

---

## Bootstrap-Provisioned Windows Environments

The supported bootstrap surface provisions `goodq_core` plus the current step-env pack from pinned lock recipes.

### Orchestration & Core

- `goodq_core`
  - canonical orchestration environment
  - used by launcher, CLI, bootstrap validation, API, and watchdog

### Vision / Video

- `goodq_video_scene_detect`
  - legacy-but-supported scene detection environment
- `goodq_image_caption`
  - image captioning plus OCR / EXIF / CLIP / DINO support for the current image lane
- `goodq_object_detect`
  - YOLO object detection
- `goodq_face_embed`
  - face detection and embedding
- `goodq_text_embed`
  - text embedding support

### Audio

- `goodq_audio_metadata`
  - audio metadata and time-hint helpers
- `goodq_audio_transcribe`
  - Windows-side audio helper lane used for speaker merge, music events, and time hints
- `goodq_audio_emotion`
  - audio emotion analysis
- `goodq_audio_embed`
  - CLAP audio embeddings

---

## Current WSL Environments

### WSL Unified Audio Worker

- home: `GOODQ_WSL_WORKSPACE` (typically `~/goodq_audio`)
- runtime: `venv/`
- key files:
  - `setup_cuda_env.sh`
  - `process_audio.py`
  - `process.sh`

This is the current accelerated audio worker for:

- transcription
- optional diarization
- optional embeddings
- optional emotion

### WSL vLLM Service Stack

- home: `GOODQ_WSL_VLLM_HOME` (default `~/vllm_server`)
- runtime: `venv/`
- used for the optional WSL/systemd-backed local LLM service path

---

## Supported Shipping Surface

These are the environments/operators that should be treated as part of the active supported surface:

- `goodq_core`
- `goodq_video_scene_detect`
- `goodq_image_caption`
- `goodq_object_detect`
- `goodq_face_embed`
- `goodq_text_embed`
- `goodq_audio_metadata`
- `goodq_audio_transcribe`
- `goodq_audio_emotion`
- `goodq_audio_embed`
- WSL unified audio worker: `GOODQ_WSL_WORKSPACE/venv`
- WSL vLLM worker: `GOODQ_WSL_VLLM_HOME/venv`

---

## Legacy / Non-Canonical Surfaces

The following names may still exist in code, lockfiles, or historical docs, but they are not the current primary bootstrap/runtime surface:

- `goodq_audio_diarize`
- `goodq_image_embed`
- `goodq_ocr`
- `goodq_text_tagger`
- `goodq_sentiment`
- `goodq_emotion_classify`
- `goodq_knowledge_graph`
- `goodq_llm_chat`

They should not be treated as the first stop for current runtime troubleshooting unless a canonical doc explicitly points there.

---

## How To Use This Index

- Use this index to map a failing step to its current runtime environment.
- Use the WSL runtime doc when audio acceleration is involved.
- Use the segmentation artifact contract when shadow-mode segmentation is involved.

Related docs:

- [`docs/reference/WSL_AUDIO_RUNTIME.md`](../WSL_AUDIO_RUNTIME.md)
- [`docs/technical/SEGMENTATION_ARTIFACT_CONTRACT.md`](../../technical/SEGMENTATION_ARTIFACT_CONTRACT.md)
- [`docs/guides/gpu/GPU_LLM_WSL_INDEX.md`](../../guides/gpu/GPU_LLM_WSL_INDEX.md)
