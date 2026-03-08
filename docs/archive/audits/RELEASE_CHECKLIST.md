<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_CANONICAL_POINTER: docs/releases/SHIP_PROFILE.md -->
<!-- DOC_ARCHIVED_ON: 2026-02-12 -->

> [!WARNING]
> ARCHIVE / NON-CANONICAL / DO NOT COPY PATHS
> This document is preserved as historical evidence and may contain obsolete fixed-drive paths, host-specific assumptions, stale commands, or superseded runtime guidance.
> Do not use it for current runtime, setup, migration, or copy-paste path decisions.
> Use active documentation, `config_loader`, and canonical path abstractions such as `<project_root>`, `<GOODQ_DATA_ROOT>`, and `<GOODQ_WSL_WORKSPACE>` instead.

# GoodQ4All Release / Mission Launch Checklist

**Purpose:** One-page checklist to validate a build before you call it “production ready”. Think of this as your Q‑style pre‑flight: verify core services, GPU paths, WSL integrations, and a full ingestion loop.

---

## 0. Preconditions

- Windows 10/11 with WSL2 enabled.
- NVIDIA RTX‑class GPU with drivers installed and working.
- Conda environments created (see `docs/ENVIRONMENT_INDEX.md`).
- WSL audio (`~/goodq_audio/`) and vLLM (`~/vllm_server/`) stacks installed (see `docs/WSL2_AUDIO_SETUP.md`, `docs/vllm-integration-complete.md`).

If any of these are missing, address those first.

---

## 1. Core System Readiness (Windows)

From PowerShell or CMD:

```powershell
cd L:\goodq4all

conda run -n goodq_zenml python scripts/system_readiness_check.py
conda run -n goodq_zenml python scripts/cache_readiness_check.py
```

Confirm:
- Overall status is ✅ or only WARNs for optional datasets.
- No hard FAILs for `tools_root`, `ffmpeg`, `whisper_cli`, `yolo_model`, or `models_root`.

If there are FAILs, consult:
- `docs/TROUBLESHOOTING_INDEX.md`
- `docs/GPU_LLM_WSL_INDEX.md` (for GPU/LLM/tooling issues).

---

## 2. GPU Pipeline Sanity Checks (Windows)

### Audio Stack

```powershell
cd L:\goodq4all

conda run -n goodq_audio_diarize   python scripts/test_audio_diarize_breakdown.py
conda run -n goodq_audio_transcribe python scripts/test_audio_pipeline_gpu.py
conda run -n goodq_audio_emotion   python scripts/test_vad_gpu_usage.py
```

Expect:
- CUDA available where configured.
- Emotion/diarization/transcription tests report `status: ok` and non‑zero counts where applicable.

### Vision / Scene Detection

```powershell
cd L:\goodq4all

conda run -n goodq_video_scene_detect python scripts/test_gpu_scene_detection.py
conda run -n goodq_image_caption      python scripts/test_vision_gpu.py
conda run -n goodq_face_embed         python scripts/test_vision_gpu.py
```

Expect: no CUDA errors, models load successfully, and test scenes/frames are processed.

If any test fails, see:
- `docs/GPU_LLM_WSL_INDEX.md`
- `docs/TROUBLESHOOTING_INDEX.md`

---

## 3. WSL2 Audio & vLLM Validation

### Audio Processing (WSL2)

In WSL2:

```bash
cd ~/goodq_audio
source venv/bin/activate

./process.sh /mnt/l/goodq4all/data/test_audio.mp3
tail -f ~/goodq_audio/logs/audio_service.log
```

Confirm:
- No GPU/CUDA errors.
- Diarization and transcription segments appear in the log.
- VAD is trimming silence as described in `docs/VAD_AND_GPU_OPTIMIZATION_COMPLETE.md`.

### vLLM / LLM Client

In WSL2:

```bash
cd ~/vllm_server
source venv/bin/activate
./scripts/start_llama1b.sh

curl http://localhost:38005/v1/models
```

On Windows:

```powershell
cd L:\goodq4all
conda run -n goodq_zenml python scripts/test_llm_client.py
```

Confirm:
- `/v1/models` returns the Llama‑1B model list.
- `test_llm_client.py` reports a healthy chain (vLLM primary, Ollama fallback when present).

---

## 4. End‑to‑End Ingestion Smoke Test

### Launch Stack

From Windows:

```powershell
cd L:\goodq4all

LAUNCH_GOODQ.bat
START_WATCHDOG.bat
```

Drop a small test video (or one of your home videos) into:

```text
L:\goodq4all\import_inbox\
```

Monitor:
- Command Center and Pipeline Engines tabs in the UI.
- `logs/watchdog.log` and `L:\_DATA\GoodQ_Data\logs\step_runs.jsonl`.

When processing completes, verify:
- Scene Explorer shows scenes and thumbnails.
- Analytics view shows emotion/entity/timeline data (no placeholder content).
- Knowledge Graph visualization shows entities and relationships.
- Chat can answer basic questions about the processed video.

---

## 5. Post‑Run Status & Documentation

After a successful run:

1. Update `docs/CURRENT_SYSTEM_STATUS.md` if anything material changed (e.g., number of scenes/videos, new issues discovered/resolved).
2. Add a brief entry to `docs/project-history/CHANGELOG.md` summarizing the validation run (date, scope, pass/fail, notable observations).
3. Optionally create a dated validation note (for example `docs/PRODUCTION_VALIDATION_<YYYYMMDD>.md`) if this run is significant.

This creates an auditable trail of “mission launches” and keeps your future self – or future agents – aligned on what was verified and when.

---

## 6. If Something Fails

Use this triage path:

- **Configuration / tools issues:** `docs/TROUBLESHOOTING_INDEX.md`, `docs/INSTALL.md`, `docs/API_DEBUG_INSTRUCTIONS.md`.
- **GPU / performance issues:** `docs/GPU_LLM_WSL_INDEX.md`, `docs/GPU_SETUP.md`, `docs/GPU_OPTIMIZATION_GUIDE.md`.
- **WSL2 / audio issues:** `docs/WSL2_AUDIO_SETUP.md`, `docs/WSL2_AUDIO_MIGRATION_GUIDE.md`, `docs/WSL2_AUDIO_SUMMARY.md`.
- **LLM issues:** `docs/LLM_INFRASTRUCTURE.md`, `docs/LLM_CLIENT_GUIDE.md`, `docs/vllm-integration-complete.md`.

Treat this checklist as your standard operating procedure before declaring a build “ready for the field”.

