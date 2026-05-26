<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_ARCHIVED_ON: 2026-03-19 -->

# GOODCUBE_STAGE10_3_CONDA_ENV_AUDIT

Date: 2026-02-21
Scope: Read-only static audit of conda environment architecture and dependency isolation.
Method: Repo scan only (no installs, no refactors). `conda` binary is not present in this shell, so live env package inspection was not possible.

## Referenced Env Names

### Environment names referenced in `cli/`, `steps/`, `scripts/`, `configs/`

| Env name | Where referenced | Current role |
|---|---|---|
| `goodq_core` | `configs/config.yaml:46`, `configs/config.yaml:135`, `cli/run_ingestion.py:801`, `scripts/_lib/interpreter_bindings.ps1:15` | Primary/default runtime env token |
| `goodq_video_scene_detect` | `cli/run_ingestion.py:949`, `cli/watchdog.py` (indirect via step plans), `configs/config.yaml:144` | Active scene-detect env |
| `goodq_audio_transcribe` | `cli/watchdog.py:643`, `cli/chroma_store.py:65`, `cli/run_ingestion.py:883` | Active audio step env token |
| `goodq_audio_embed` | `cli/watchdog.py:644`, `cli/run_ingestion.py:930`, `configs/config.yaml:139` | Active audio embedding env |
| `goodq_audio_emotion` | `cli/watchdog.py:645`, `configs/config.yaml:140` | Active watchdog audio env |
| `goodq_audio_metadata` | `cli/watchdog.py:646`, `cli/chroma_store.py:173`, `cli/run_ingestion.py:871`, `configs/config.yaml:141` | Active metadata/time-hint env |
| `goodq_text_embed` | `cli/watchdog.py:649`, `cli/chroma_store.py:50`, `scripts/start_api.ps1:40` | Active text embedding + API env |
| `goodq_sentiment` | `cli/watchdog.py:650`, `cli/chroma_store.py:162` | Active NLP env |
| `goodq_emotion_classify` | `cli/watchdog.py:651`, `cli/chroma_store.py:155` | Active NLP/tagging env |
| `goodq_image_caption` | `cli/watchdog.py:734`, `cli/chroma_store.py:56` | Active image/caption env |
| `goodq_object_detect` | `cli/watchdog.py:736` | Active vision env |
| `goodq_face_embed` | `cli/watchdog.py:737` | Active vision env |
| `goodq_audio_diarize` | installer/check scripts only (`scripts/install_pipeline_windows.ps1:75`, `scripts/system_readiness_check.py:264`) | Provisioned, not on current watchdog/run_ingestion plans |
| `goodq_object_track` | installer matrix (`scripts/install_pipeline_windows.ps1:74`, `scripts/install_pipeline_wsl.py:134`) | Provisioned name; runtime naming drift with `goodq_object_track_yolo` |
| `goodq_object_track_yolo` | GPU setup script (`scripts/install_gpu_support.ps1:26`) | Alternate naming token (drift) |
| `goodq_ocr`, `goodq_pdf_text`, `goodq_llm_chat`, `goodq_tts`, `goodq_system_metrics`, `goodq_home_assistant_status` | installer matrices (`scripts/install_pipeline_windows.ps1:84-89`, `scripts/install_pipeline_wsl.py:150-155`) | Provisioned/support envs |
| `goodq_agents` | `scripts/setup/setup_agents.ps1` | Tooling env (not ingestion runtime) |
| `goodq_zenml` | legacy/setup references (`scripts/prepare_step_envs.ps1:130`) | Legacy orchestration remnant |

### Key runtime split

- `cli/run_ingestion.py` routes many heavy steps through `goodq_core` (`cli/run_ingestion.py:801-807`, `cli/run_ingestion.py:927-929`) while still using per-step envs for selected audio/scene work (`cli/run_ingestion.py:871`, `cli/run_ingestion.py:930`, `cli/run_ingestion.py:949`).
- `cli/watchdog.py` uses explicit per-step env isolation for audio/image/document plans (`cli/watchdog.py:643-652`, `cli/watchdog.py:734-744`, `cli/watchdog.py:850-853`).

## YAML Definitions Found

- Conda env YAML files: none found under repo (`environment.yml`/`environment.yaml` absent).
- Step env definitions are file-based via `envs/*/requirements.txt` (20 env requirement files).
- Lock surface exists via `envs/locks/*.lock.txt` (20+ lock files, see `envs/locks/README.md`).
- Additional WSL lock file exists: `wsl2_audio/requirements-locked.txt`.
- `goodq_core` has no canonical `envs/goodq_core.yaml` or equivalent manifest in active repo.

### Per-env requirements files discovered

- `envs/audio_diarize/requirements.txt`
- `envs/audio_embed/requirements.txt`
- `envs/audio_emotion/requirements.txt`
- `envs/audio_metadata/requirements.txt`
- `envs/audio_transcribe/requirements.txt`
- `envs/emotion_classify/requirements.txt`
- `envs/face_embed/requirements.txt`
- `envs/home_assistant_status/requirements.txt`
- `envs/image_caption/requirements.txt`
- `envs/llm_chat/requirements.txt`
- `envs/object_detect/requirements.txt`
- `envs/object_track_yolo/requirements.txt`
- `envs/ocr/requirements.txt`
- `envs/pdf_text/requirements.txt` (empty)
- `envs/sentiment/requirements.txt`
- `envs/system_metrics/requirements.txt`
- `envs/tagger/requirements.txt`
- `envs/text_embed/requirements.txt`
- `envs/tts/requirements.txt`
- `envs/video_scene_detect/requirements.txt`

## Step-to-Env Mapping

### Active orchestration mapping (code-backed)

| Path class | Steps | Env mapping observed |
|---|---|---|
| Video scene detect | `video_scene_detect` | `goodq_video_scene_detect` in `cli/run_ingestion.py:949` |
| Image pipeline (`run_ingestion`) | `image_ocr`, `image_caption`, `object_detect`, `face_embed`, `image_embed_dino`, `image_embed_clip`, `tagger`, `text_embed` | `goodq_core` (`cli/run_ingestion.py:801-807`, `cli/run_ingestion.py:823`) |
| Audio pipeline (`run_ingestion`) | `audio_metadata`, `audio_speaker_merge`, `audio_music_events`, `audio_time_hints`, `audio_embed_clap`, `sentiment`, `emotion_classify`, `tagger`, `text_embed` | Mixed: `goodq_audio_metadata`, `goodq_audio_transcribe`, `goodq_audio_embed`, `goodq_core` (`cli/run_ingestion.py:871`, `cli/run_ingestion.py:883-885`, `cli/run_ingestion.py:930`, `cli/run_ingestion.py:925`, `cli/run_ingestion.py:927-929`) |
| Audio pipeline (`watchdog`) | `audio_transcribe`, `audio_embed_clap`, `audio_emotion`, `audio_metadata`, `audio_time_hints`, `audio_music_events`, `text_embed`, `sentiment`, `emotion_classify`, `tagger` | Per-step split (`cli/watchdog.py:643-652`) |
| Image pipeline (`watchdog`) | OCR/caption/object/face/embed/text/sentiment/tagging | Per-step split (`cli/watchdog.py:734-744`) |
| Document pipeline (`watchdog`) | `pdf_text`, `text_embed`, `sentiment`, `emotion_classify`, `tagger` | `goodq_text_embed` + NLP envs (`cli/watchdog.py:834`, `cli/watchdog.py:850-853`) |
| Chroma ingest helper | text/image/audio enrichment steps | Per-step split (`cli/chroma_store.py:50-65`, `cli/chroma_store.py:155-179`) |
| API launcher | retrieval API | Executes in `goodq_text_embed` (`scripts/start_api.ps1:40-61`) |

### Why separation exists (inferred)

- Required conflicts: divergent Torch/TorchVision/Numpy pins across envs.
- Historical architecture: per-step conda isolation remains embedded in watchdog/chroma and installer matrices.
- Performance isolation: scripts explicitly tune GPU stack per env (`scripts/setup_gpu_environments.bat`).
- WSL transition: audio transcribe/diarize pathways now have WSL-accelerated variants, reducing need for heavy Windows audio envs in some flows.

## Overlap Matrix

Static comparison across `envs/*/requirements.txt`:

- Total env requirement files: `20`
- Unique package names (union): `41`
- Version-conflict package names: `4`

### Most-shared packages

| Package | # envs |
|---|---|
| `numpy` | 13 |
| `torch` | 12 |
| `transformers` | 7 |
| `pillow` | 7 |
| `tokenizers` | 5 |
| `sentencepiece` | 5 |
| `soundfile` | 5 |
| `torchvision` | 5 |

### Highest overlap pairs

| Env pair | Shared packages | Jaccard |
|---|---:|---:|
| `audio_embed` vs `audio_emotion` | 6 | 0.75 |
| `emotion_classify` vs `sentiment` | 5 | 0.83 |
| `object_detect` vs `object_track_yolo` | 5 | 0.71 |
| `image_caption` vs `text_embed` | 6 | 0.40 |

### Unique package signals by env

- `audio_diarize`: `pyannote.audio`, `whisperx`, `torchaudio`, `cryptography`, `dill`
- `audio_transcribe`: `faster-whisper`, `numba`
- `face_embed`: `face-recognition`, `facenet-pytorch`
- `object_detect`: `ultralytics`
- `object_track_yolo`: `deep-sort-realtime`
- `text_embed`: `sentence-transformers`, `datasets`, `python-dotenv`
- `image_caption`: `accelerate`, `timm`, `reverse_geocoder`, `timezonefinder`
- `system_metrics`: `psutil`, `pandas`, `chardet`

## Minimal Unified Dependency Set

Assuming GOODCUBE strategy is GPU workstation + WSL audio offload, the practical target is:

- One Windows runtime env (`goodq_core`) for vision/text/vector/control paths.
- One WSL audio venv (`/home/<user>/goodq_audio/env`) for faster-whisper/diarization-heavy work.

### Minimal Windows unified set (replace most step envs)

Common base:

- `torch==2.3.1`, `torchvision==0.18.1`
- `transformers==4.43.3`, `tokenizers==0.19.1`, `sentencepiece==0.2.0`
- `numpy` (single normalized pin required), `pillow` (single normalized pin required)
- `faiss-cpu==1.9.0`, `sentence-transformers==2.7.0`
- `opencv-python-headless==4.10.0.84`, `scenedetect==0.6.2`
- `librosa==0.10.2.post1`, `soundfile==0.12.1`, `mutagen==1.47.0`
- `ultralytics==8.2.103`, `face-recognition==1.3.0`, `facenet-pytorch>=2.6.0`
- `pytesseract==0.3.10`
- `requests==2.32.3`, `pandas==2.2.2`, `psutil==5.9.8`, `chardet==5.2.0`
- `accelerate==0.33.0`, `timm==0.9.5`, `datasets==2.19.1`, `regex==2024.7.24`

### Minimal WSL audio set (already aligned by Stage 7/8 direction)

- `faster-whisper`
- CUDA-enabled `torch`
- runtime audio deps for helper path (`soundfile`, `numpy`, `ctranslate2` via faster-whisper stack)

## Conflict Analysis

### Hard version conflicts

- `torch`: `2.3.1` vs `2.5.1`
- `torchvision`: `0.18.1` vs `0.20.1`

Primary source: `audio_diarize` env diverges from most other envs.

### Soft but material conflicts

- `numpy`: `1.26.4` vs `2.2.6` vs ranged pins (`>=1.24,<2`, `>=2.0,<2.3`)
- `pillow`: `10.2.0` vs `10.4.0` vs `12.0.0`

### Architecture/control conflicts

- Env routing is not centralized; hardcoded env names appear in multiple runtime entrypoints (`cli/run_ingestion.py`, `cli/watchdog.py`, `cli/chroma_store.py`).
- Naming drift: `goodq_object_track` vs `goodq_object_track_yolo` and even `object_track_yolo` token in scripts (`scripts/setup_gpu_environments.bat:161`).
- `goodq_core` lacks canonical declarative manifest in repo, so reproducibility is weaker than step envs.

### Hidden dependency assumptions

- `video_scene_detect` GPU path imports `torch` (`steps/video_scene_detect/step.py:107`) but env requirements file does not declare Torch (`envs/video_scene_detect/requirements.txt`).
- OCR/PDF/audio pipelines rely on external binaries (`tesseract`, `pdftotext`, `ffmpeg`) outside pip requirements.

## GOODCUBE Recommendation

### 1) Is multi-env architecture still necessary?

- Strictly today: yes for full declared surface, due unresolved pin conflicts and hardcoded per-step routing.
- Operationally on GOODCUBE profile with WSL audio offload: multi-env can be reduced substantially.

### 2) Can GOODCUBE collapse to single runtime?

- Not safely as an immediate no-code switch.
- Safe near-term target is dual-runtime: `goodq_core` (Windows) + WSL audio venv.

### 3) Which envs are safest to alias toward `goodq_core` first?

Lowest-risk functional candidates (after dependency parity validation):

- `goodq_sentiment`, `goodq_emotion_classify`, `goodq_tagger`
- `goodq_audio_metadata`
- `goodq_text_embed`
- `goodq_image_caption`, `goodq_object_detect`, `goodq_face_embed`
- `goodq_pdf_text`, `goodq_ocr`, `goodq_system_metrics`, `goodq_home_assistant_status`, `goodq_llm_chat`, `goodq_tts`

Highest-risk to collapse immediately:

- `goodq_audio_diarize` (Torch stack divergence + pyannote/whisperx stack)
- `goodq_video_scene_detect` until Torch/Numpy expectations are explicitly normalized

### 4) Minimal additions `goodq_core` would need to replace others

If `goodq_core` is to absorb non-WSL steps, it must include at least:

- all unique packages listed in this audit’s overlap section (notably `ultralytics`, `face-recognition`, `facenet-pytorch`, `sentence-transformers`, `pytesseract`, `mutagen`, `accelerate`, `timm`, `datasets`, `deep-sort-realtime` if tracking is required)
- normalized single pins for `numpy` and `pillow`
- verified external binaries on host path: `ffmpeg`, `tesseract`, `pdftotext`

### 5) Risk analysis of collapsing env model

- Binary compatibility regressions from forcing one Torch/Numpy/Pillow stack.
- Reduced fault isolation during GPU OOM/fragmentation events.
- Hardcoded env tokens can still call non-existent env names unless routing is unified.
- Harder rollback unless lock discipline is strengthened for the unified env.

## Risk Flags

- `goodq_core` is runtime-critical but undeclared in repo manifests.
- Runtime mapping inconsistency: `run_ingestion` mostly unified; `watchdog` and `chroma_store` remain per-step isolated.
- Env naming drift (`goodq_object_track` vs `goodq_object_track_yolo` vs `object_track_yolo`).
- Hidden non-pip dependencies (`ffmpeg`, `tesseract`, `pdftotext`) not represented in env requirement files.
- Legacy/unused provisioning surfaces (including `goodq_zenml`) still present and may confuse operators.

## Next Action Proposal

1. Freeze current `goodq_core` package inventory and compare against this audit’s minimal unified set (gap-only list).
2. Decide target model explicitly: `single Windows env + WSL audio` vs `full multi-env`; document as runtime contract.
3. Normalize env naming (`goodq_object_track`/`goodq_object_track_yolo`) and routing source-of-truth.
4. Pilot aliasing of low-risk envs to `goodq_core` in one orchestrator path first, then validate before wider rollout.
5. Keep `goodq_audio_diarize` isolated or fully offload it to WSL until Torch stack convergence is proven.
