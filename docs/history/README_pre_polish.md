# GoodQ - Desktop AI Companion

**Version 1.2.0** | **Status: Production-Ready** | **Last Updated: October 6, 2025**

> Privacy-first, multimodal AI companion inspired by Q from James Bond. Process video, audio, images, and text entirely on your local hardware with enterprise-grade observability.

[![Production Ready](https://img.shields.io/badge/status-production--ready-brightgreen)]()
[![Python 3.10](https://img.shields.io/badge/python-3.10-blue)]()
[![CUDA 12.1](https://img.shields.io/badge/CUDA-12.1-green)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)]()

---

## ✨ Highlights

🎉 **October 6, 2025 - Project Polish Complete!**
- ✅ All 22 environments operational with perfect isolation
- ✅ Audio emotion classification unblocked (CUDA-accelerated)
- ✅ Smart deduplication working (76% faster on reruns: 158s → 38s)
- ✅ System & cache readiness: Perfect scores
- ✅ End-to-end ingestion: Passes all tests
- ✅ Zero production blockers remaining

---

## 📋 Table of Contents

- [What is GoodQ?](#what-is-goodq)
- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Documentation](#documentation)
- [Performance](#performance)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## 🎯 What is GoodQ?
- Readiness passes remain automated: run `python scripts\system_readiness_check.py` and `python scripts\cache_readiness_check.py` before ingest. They self-heal HF/Torch env vars, validate CUDA/PyAnnote, and fail fast if required assets drift from `L:/models`.
- Model and dataset caches now cover the full foundation set: `scripts\download_datasets.py` prefetches sentiment/NLP corpora, math & science benchmarks, geospatial/astronomy references, and baseline ASR datasets into `L:/models/hf/datasets`, and recognises category-specific vendor directories for advanced corpora (COCO, Common Voice, MMLU, etc.).
- The CLI orchestrator ships with "smart memory": before processing a scene it checks SQLite for existing keyframe/audio hashes and reuses stored manifests to skip detection when the video hash matches; every downstream step is logged as `status="skipped"` with `extra.reason="dedupe"` when artifacts already exist, and metadata is reused.
- Every run carries a digital fingerprint. `run_ingestion.py` stamps a UUID, pipeline name, start timestamp, optional git SHA, and a scene manifest hash into `logs/_resolved_config.json`, and those fields propagate to every `step_runs.jsonl` entry.
- Step telemetry is centralized under `L:/GoodQ_Data/logs`, now enriched with run metadata so audits can trace skipped vs materialized work across replays.
- Lite ingestion continues end-to-end; the only outstanding blocker is adding `hf_transfer` (or vendoring the SER weights) inside `goodq_audio_emotion` so the audio emotion step no longer short-circuits.
- Legacy `GoodQ_Pipeline` stays reference-only while storage now lives under `L:/GoodQ_Data` alongside `goodq4all`.

## Readiness & Caches
- `python scripts/system_readiness_check.py` – verifies env vars, tool paths, CUDA availability, PyAnnote auth, and Hugging Face access. It auto-corrects `HF_HOME/TORCH_HOME/HF_HUB_ENABLE_HF_TRANSFER` for the run and records any fallbacks in the report.
- Gated datasets follow a three-tier flow: reuse vendored caches under `L:/models/hf/datasets` first, fall back to authenticated downloads (honouring `HF_TOKEN` + `hf_transfer`), and gracefully skip with a warning when no token is available.
- `python scripts/cache_readiness_check.py` – confirms required Hugging Face snapshots, YOLO weights, NRC lexicons, and datasets exist under `L:/models`; the dataset section now calls out vendored/cached/gated corpora so you can stage large resources before production runs.
- `conda run -n goodq_text_embed python scripts/download_datasets.py` – warms the lightweight datasets we rely on for smoke tests. Missing repos are logged as warnings so the script never blocks the pipeline.
- Use `HF_DOWNLOAD_GATED=1` with `scripts\download_datasets.py` when you need gated corpora. Common Voice 17, COCO 2017, `lukaemon/mmlu_flan`, SciKnowOrg materials science, tweet_sentiment_multilingual, and speech_commands still require manual approval or updated loaders; they will continue to surface warnings until you vendor them locally or refresh `dataset_specs.py`.

## Open Issues
- **Audio emotion classification**: install `pip install hf_transfer` inside `goodq_audio_emotion` (or vendor the wheel) so Transformers can stream `superb/hubert-large-superb-er` or `ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition` without timing out.
- **Runtime monitoring**: continue tailing `L:/GoodQ_Data/logs/step_runs.jsonl` during long runs – if ingestion pauses, the log will reveal which step is waiting on downloads.
- **Validation plan**: once audio emotion loads cleanly, rerun `pwsh scripts/ingest_videos_lite.ps1 -InputDir import_inbox -MaxFrames 10 -MaxSegments 3` to confirm end-to-end persistence, then graduate to the full orchestrator smoke.

## Why GoodQ Exists
- Desktop-native, privacy-first AI companion inspired by Q from the Bond universe.
- Combines multimodal ingestion (video, audio, documents) with durable memory, diagnostics, and rapid search.
- Runs local-first: CUDA acceleration, local embeddings, optional offline TTS, and configurable LLM endpoints (LM Studio, Ollama, OpenAI-compatible APIs).
- Mission control mindset: health checks, automated backups, and pipeline-level observability are built into every run.

## Major Capabilities
- **Multimodal ingestion**: scene detection, frame captioning, OCR, object/face embeddings, PyAnnote diarization, whisper.cpp transcription, CLAP audio embeddings, SBERT text embeddings.
- **Memory management**: schema introspection, FAISS/DB reconciliation, automatic backups, and ZenML artifact tracking.
- **Mission telemetry**: Command Center CLI, pipeline summaries, and environmental sync that keep caches, tokens, and configs aligned.
- **Home & system awareness**: optional Home Assistant polling and hardware diagnostics for richer context during missions.

## Architecture Overview
- ZenML pipelines coordinate per-step Conda environments for isolation and reproducibility.
- Step runner (`goodq4all.cli.step_runner`) loads items/config JSON, executes a step, and writes results back to disk so PowerShell orchestrators remain simple.
- Persistence layer uses SQLite (`memory.db`) plus FAISS indices for text/image/audio, with ID maps to reconcile embeddings and raw assets.
- Short-term run summaries and long-term compressed history live side-by-side in `memory.db::summaries`, mirroring the Context Engineering guidance used in the original GoodQ stack.

## Key Pipelines
- **ingest_multimodal** (scaffold): discovers inputs, processes audio/image/text, and enriches items with embeddings and analytics.
- **ingest_multimodal_conda**: production pipeline using ZenML decorators and Conda environment delegation for each heavy step.
- **goodq_chat**: chat/mission pipeline (LLM prompt, optional TTS playback).

## Step Highlights
- **Audio**: metadata (mutagen/librosa) → diarization (PyAnnote) → chunking → whisper.cpp transcription (10 s windows) → speaker merge, time hints, music events, emotion (Transformers SER), CLAP embedding, transcript sentiment/tagging.
- **Image**: ffmpeg-scene frames → OCR (tesseract) → caption (BLIP) → detection (YOLO) → face embeddings (face_recognition or facenet-pytorch fallback) → CLIP & DINO embeddings stored in FAISS.
- **Text**: SBERT embeddings, sentiment, emotions, tagger (DSLIM NER with transformers logging suppressed and cached pipelines) and usefulness scoring.
- **Context**: Home Assistant API snapshot, system metrics (psutil + NVIDIA SMI), Command Center summaries.

## Configuration Files
- `configs/config_open.yaml` – primary runtime settings (LLM endpoints, tool paths, video thresholds, tagger model).
- `configs/paths.yaml` – canonical paths for logs, outputs, DB, FAISS, ID maps.
- `configs/entities.yaml` – Home Assistant entities (optional).
- `.env.local` – auto-synced secrets and cache variables (never commit).

## Environment Layout
- `envs/<step>/requirements.txt` – per-step dependency pins; GPU-enabled envs include `image_caption`, `object_detect`, `audio_transcribe`, `audio_diarize`, `audio_emotion`, `face_embed`.
- `scripts/enable_cuda.ps1` – installs CUDA wheels for every GPU env; use `-Verify` to confirm.
- Run `scripts/prepare_step_envs.ps1 -EnvPrefix goodq -LinkProject` to create/update envs and drop `.pth` files pointing to `L:/` so `goodq4all` imports resolve.

## Quickstart
1. **Optional reset**: `pwsh scripts/reset_goodq_envs.ps1 -EnvPrefix goodq -Force -ClearTemp`
2. **Install & cache warm-up**: `pwsh scripts/install_goodq.ps1 -SetCacheEnv -ModelsCache 'L:/models'`
3. **Preflight**: `pwsh scripts/mission_health_check.ps1 -EnvPrefix goodq -FixMissingCaches`
4. **Dry run**: `pwsh scripts/mission_launch.ps1 -Mode dryrun -EnvPrefix goodq`
5. **Full pipeline + dashboard**: `pwsh scripts/mission_launch.ps1 -Mode pipeline -OpenDashboard`
6. **Lite ingestion sanity check**: `pwsh scripts/ingest_videos_lite.ps1 -InputDir import_inbox -MaxFrames 10 -MaxSegments 3`

## Scripts Worth Knowing
- `scripts/install_goodq.ps1` – one-shot installer (envs, CUDA, optional dry run).
- `scripts/mission_health_check.ps1` – diagnostics (DB/FAISS, env sanity, cache check).
- `scripts/mission_launch.ps1` – orchestrates health, CUDA, pipeline launch, Command Center.
- `scripts/sync_env_local.ps1` – copies approved system env vars into `.env.local` before each run.
- `scripts/enable_cuda.ps1` – ensures GPU wheels across envs; `-Verify` prints per-env status.
- `scripts/reconcile_indices.ps1` – compares FAISS `ntotal` vs DB/ID-map counts, flags drift.
- `scripts/run_full_dry_run.ps1` – generates export bundle with DB, FAISS, logs.
- `scripts/command_center.ps1` – interactive dashboard (GPU, DB/FAISS stats, step log tail).
- `scripts/launch_goodq.bat` – Windows launcher for full-stack mission runs.

## Artifacts & Logs
- Ingestion logs live under `L:/GoodQ_Data/logs` until the ZenML artifact store migration completes.
- Lite/full runs emit per-step JSON outputs (`logs/step_runs.jsonl`) and bundle exports (`logs/run_exports/YYMMDD_HHMMSS`).
- Audio/text/image embeddings are written to SQLite (`memory.db`) and FAISS indices defined in `configs/paths.yaml`.
- CLAP ID maps keep FAISS IDs aligned with content fingerprints for auditability.

## Environment Variables
- Required tokens: `PYANNOTE_TOKEN` or `PYANNOTE_AUDIO_AUTH`, `HF_TOKEN`, `OPENAI_API_KEY` (or LM Studio/Ollama equivalents), optional `ELEVENLABS_API_KEY`, `HA_TOKEN`.
- Cache homes: set `HF_HOME` and `TORCH_HOME` to `L:/models`; `TRANSFORMERS_CACHE` is deprecated.
- `scripts/set_env_vars.ps1 -OnlyIfMissing` provides a safe setter for commonly used keys.

## Historical Context
- The original GoodQ_o2-B repository (now archived) introduced the mission-oriented UX, dual TTS, system monitoring, and Home Assistant hooks.
- Its documentation, changelogs, and requirements have been consolidated into `L:/legacy` so the active ZenML project stays lean while preserving institutional knowledge.
- You can still explore experimental modules (LLM orchestration, trend analytics, mission logging) inside the legacy archive; port relevant ideas into `goodq4all` as needed.

## Recent Highlights & Next Steps
- Conda envs rebuilt under `C:/Users/jdben/miniconda3`; installer scripts now target this base and relink the repo automatically.
- `system_readiness_check.py` and `cache_readiness_check.py` both report **GREEN**; vendor modules live under `goodq4all/vendor` to satisfy non-conda imports.
- Lite ingestion (`scripts/ingest_videos_lite.ps1 -VerboseSteps`) runs end-to-end without hangs: diarization, transcription, audio emotion, CLAP, and text pipelines all complete.
- Step telemetry captures `run_id`, pipeline metadata, canonical IDs, and raises an `improbable_duration` flag when GPU-heavy steps finish suspiciously fast.
- Pip/models/dataset caches are centralized (`L:/pip_cache`, `L:/models`), avoiding writes to the system drive and speeding up reruns.
- `python scripts/system_readiness_check.py` — verifies env vars, tool paths, CUDA availability, PyAnnote auth; falls back to normalized paths and records any auto-corrections.
- `python scripts/cache_readiness_check.py --json` — confirms Hugging Face/Torch snapshots, YOLO weights, NRC lexicons, and dataset caches under `L:/models`; optional caches are reported but non-blocking.
- `conda run -n goodq_text_embed python scripts/download_datasets.py` — warms the smoke-test datasets; failures are logged as warnings only.
- `scripts/set_env_vars.ps1` now de-dupes `.env.local` entries so repeated installs no longer append duplicates.
- **Scene idempotence:** `run_ingestion.py` still recomputes image/audio pipelines on every run. Next pass should compute a `scene_manifest_hash`, consult `scene_has_materialized(...)`, and log `skipped` entries instead of reprocessing.
- **Run metadata propagation:** `cfg['run']` is partially in place (logger consumes it) but `run_ingestion.py` still needs to stamp `run_id`, `started_at`, `git_sha`, etc., before writing the config snapshot.
- **Performance polish (optional):** adopt NVDEC (`ffmpeg -hwaccel cuda`), stage scratch on NVMe, enable TF32 (`torch.backends.cuda.matmul.allow_tf32 = True`), and fuse/batch post-ops for additional speed.
