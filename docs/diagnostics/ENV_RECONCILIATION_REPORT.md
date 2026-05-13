# Environment Template Reconciliation

Generated: 2026-02-18 (static reconciliation)

## Baseline

- `.env.template` did not exist before reconciliation.
- `.env.local.template` exists and was used as the de-facto prior template for drift comparison.

## Missing from template (must add)

- `ANTHROPIC_API_KEY`
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_VOICE_ID`
- `GOODQ_API_HOST`
- `GOODQ_API_PORT`
- `GOODQ_CC_QUERY`
- `GOODQ_CC_THUMBS`
- `GOODQ_COMMIT_EVENTS_JSONL`
- `GOODQ_CONDA_ENV`
- `GOODQ_DATA_ROOT`
- `GOODQ_DB_PATH`
- `GOODQ_DEBUG_KEEP_TEMP`
- `GOODQ_FAISS_AUDIO_PATH`
- `GOODQ_FAISS_DIR`
- `GOODQ_HEALTH_AUTH_HEADER`
- `GOODQ_HEALTH_AUTH_TOKEN`
- `GOODQ_HEALTH_EXPORT_URL`
- `GOODQ_HEALTH_SOURCE_ID`
- `GOODQ_HOST_PROFILE`
- `GOODQ_KG_DB_PATH`
- `GOODQ_MODELS_DIR`
- `GOODQ_NO_AUTO_GPU`
- `GOODQ_PROCESSING_ROOT`
- `GOODQ_QDRANT_COLLECTION_AUDIO`
- `GOODQ_QDRANT_COLLECTION_CLIP`
- `GOODQ_QDRANT_COLLECTION_DINO`
- `GOODQ_QDRANT_COLLECTION_TEXT`
- `GOODQ_QDRANT_URL`
- `GOODQ_READONLY_ENVELOPE_PATH`
- `GOODQ_REQUIRE_GPU`
- `GOODQ_REQUIRE_WSL_AUDIO`
- `GOODQ_RETRIEVAL_CONTEXT`
- `GOODQ_RETRIEVAL_EVENTS`
- `GOODQ_RETRIEVAL_EVENTS_JSONL`
- `GOODQ_SMOKE_OVERRIDE_ROOT`
- `GOODQ_STEP_TIMEOUT_MS`
- `GOODQ_SUMMARIES_PREVIEW`
- `GOODQ_SUMMARY_TTL_HOURS`
- `GOODQ_VAULT_ROOT`
- `GOODQ_VECTOR_DEBUG`
- `GOODQ_VERBOSE`
- `GOODQ_WSL_AUDIO_COMPUTE_TYPE`
- `GOODQ_WSL_AUDIO_DEVICE`
- `GOODQ_WSL_AUDIO_MIXED_PRECISION`
- `GOODQ_WSL_DISTRO`
- `GOODQ_WSL_MODEL_PATH`
- `GOODQ_WSL_PROJECT_ROOT`
- `GOODQ_WSL_USER`
- `GOODQ_WSL_VLLM_HOME`
- `GOODQ_WSL_WORKSPACE`
- `HA_TOKEN`
- `HF_AUTH_TOKEN`
- `HF_DATASETS_CACHE`
- `HF_DATASETS_OFFLINE`
- `HF_DOWNLOAD_GATED`
- `HF_HOME`
- `HF_HUB_ENABLE_HF_TRANSFER`
- `HF_HUB_TOKEN`
- `HF_TOKEN`
- `HUGGINGFACE_TOKEN`
- `OPENAI_API_KEY`
- `PYANNOTE_AUDIO_AUTH`
- `PYANNOTE_TOKEN`
- `TORCH_HOME`
- `TRANSFORMERS_CACHE`
- `TRANSFORMERS_OFFLINE`
- `elevenlabs_voice_id`

## Present but outdated (in .env.local.template)

- `HF_HOME` / `TORCH_HOME`: hardcoded `L:` paths in old template; canonical contract now allows host/data-root abstraction.
- `HF_HUB_ENABLE_HF_TRANSFER` / `HF_DOWNLOAD_GATED`: old template forced values; contract now keeps them optional knobs.

## Present but no longer used

- None

## Correct and aligned (from .env.local.template)

- `ELEVENLABS_API_KEY`
- `ELEVENLABS_VOICE_ID`
- `GOODQ_API_HOST`
- `GOODQ_API_PORT`
- `GOODQ_STEP_TIMEOUT_MS`
- `GOODQ_VERBOSE`
- `HA_TOKEN`
- `HF_HUB_TOKEN`
- `HF_TOKEN`
- `OPENAI_API_KEY`
- `PYANNOTE_TOKEN`

## Excluded legacy/non-contract literals

- `GOODQ_CONFIG_PATH`
- `GOODQ_DATA_DIR`
- `GOODQ_PIPELINE_HA_API`
- `GOODQ_POINT_ID_NAMESPACE`
- `GOODQ_PRODUCTION`

## REVIEW Resolution (2026-02-19)

- `GOODQ_WSL_WORKSPACE` defaults are now aligned to `/home/<resolved_user>/goodq_audio` across active setup/runtime surfaces:
  - `api/main.py`
  - `scripts/wsl2_audio_bridge.py`
  - `wsl2_audio/start_wsl2_service.bat`
  - `scripts/setup_wsl2_audio.py`
- Hugging Face token alias overlap is now explicitly normalized:
  - Canonical token: `HUGGINGFACE_TOKEN`
  - Legacy alias mirror: `HF_TOKEN <-> HUGGINGFACE_TOKEN` (when one is unset)
  - PyAnnote inheritance: `PYANNOTE_TOKEN` inherits canonical token when unset
  - Runtime fallback support remains for `PYANNOTE_AUDIO_AUTH`
  - Contract is documented in `.env.template`

