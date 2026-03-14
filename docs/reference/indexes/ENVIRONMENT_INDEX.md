# GoodQ4All Environment Index

**Purpose:** Map the core Conda environments and WSL2 environments to their roles in the GoodQ4All pipeline, and distinguish shipping-critical envs from auxiliary/experimental ones.

---

## Windows Conda Environments (GoodQ4All)

### Orchestration & Core

- `goodq_core` – Primary orchestration environment.
  - Used by: `LAUNCH_GOODQ.bat`, `cli/run_ingestion.py`, Command Center, health checks.
  - Scope: Coordinates pipelines, DB access, FAISS, and API server.

### Vision / Video

- `goodq_video_scene_detect` – GPU-accelerated scene detection.
  - Steps: `video_scene_detect` (scene boundary detection).
- `goodq_image_caption` – Image captioning.
  - Steps: BLIP-based captioning.
- `goodq_image_embed` (mapped from `envs/image_caption` / `envs/text_embed`) – CLIP and DINO embeddings.
  - Steps: `image_embed_clip`, `image_embed_dino`.
- `goodq_object_detect` – Object detection (YOLO).
- `goodq_face_embed` – Face detection and embeddings.
- `goodq_ocr` – OCR for frame text.

### Audio

- `goodq_audio_diarize` – Speaker diarization (PyAnnote).
- `goodq_audio_transcribe` – Whisper/Faster-Whisper transcription.
- `goodq_audio_emotion` – Audio emotion classification.
- `goodq_audio_embed` – CLAP audio embeddings.

### Text, Sentiment & Emotion

- `goodq_text_embed` – SBERT text embeddings.
- `goodq_text_tagger` (mapped from `envs/tagger`) – NER/tagging.
- `goodq_sentiment` – Sentiment analysis.
- `goodq_emotion_classify` – Text emotion classification.

### Knowledge Graph & LLM

- `goodq_knowledge_graph` – Knowledge graph construction and queries.
- `goodq_llm_chat` / `llm_chat` – LLM-based chat and analysis (see LLM docs).

> Note: Environment lockfiles and names are further described in `envs/locks/README.md`. Where there is a `goodq_<step>` pattern and a matching `envs/<step>/` directory, they form a pair.

---

## WSL2 Environments

### Audio Processing Stack (`~/goodq_audio/`)

- Location: `~/goodq_audio/` (WSL2 Ubuntu).
  - `venv/` – Python virtual environment for the WSL audio worker.
  - `setup_cuda_env.sh`, `process.sh`, `process_audio.py` – GPU-accelerated audio processing and environment bootstrap.
  - Docs: `docs/guides/llm/WSL2_AUDIO_SETUP.md`, `docs/guides/llm/WSL2_AUDIO_MIGRATION_GUIDE.md`, `docs/guides/wsl2/START_HERE_WSL2.md`, `docs/guides/wsl2/WSL2_AUDIO_SUMMARY.md`.

### vLLM / LLM Service Stack (WSL2 Ubuntu)

- Runtime home: `GOODQ_WSL_VLLM_HOME` (default: `~/vllm_server`).
  - `venv/` – Python virtual environment for the vLLM service.
  - `GOODQ_WSL_MODEL_PATH` – Preferred model-path variable for the active vLLM service.
  - `scripts/wsl/install_vllm_service.sh` – Supported installer for the `vllm-llama1b` systemd service.
  - Docs: `docs/guides/llm/VLLM_SYSTEMD_SETUP.md`, `docs/guides/llm/LLM_INFRASTRUCTURE.md`, `docs/guides/llm/LLM_CLIENT_GUIDE.md`.

---

## Shipping-Critical Envs (Per SHIP_PROFILE)

These environments are considered part of the **supported surface** and should not be renamed or removed without updating:

- `goodq_core`
- `goodq_video_scene_detect`
- `goodq_audio_diarize`
- `goodq_audio_transcribe`
- `goodq_audio_emotion`
- `goodq_image_caption`
- `goodq_image_embed`
- `goodq_object_detect`
- `goodq_face_embed`
- `goodq_ocr`
- `goodq_text_embed`
- `goodq_sentiment`
- `goodq_emotion_classify`
- `goodq_audio_embed`
- `goodq_knowledge_graph`
- WSL2: `~/goodq_audio/venv/`, `GOODQ_WSL_VLLM_HOME/venv`

Other `goodq_*` or utility envs that appear only in historical docs or lockfiles may be treated as auxiliary/experimental unless explicitly referenced in `docs/releases/SHIP_PROFILE.md` or other canonical docs.

---

## How to Use This Index

- When adding or modifying steps:
  - Ensure the associated environment name matches the `goodq_<step>` pattern documented here.
  - If you introduce a new env that is part of the shipping surface, add it both here and in `docs/releases/SHIP_PROFILE.md`.
- When troubleshooting:
  - Use this index alongside `docs/guides/gpu/GPU_LLM_WSL_INDEX.md` and `docs/reference/indexes/TROUBLESHOOTING_INDEX.md` to quickly map failures to the right environment and docs.
