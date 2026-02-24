# GOODCUBE_STAGE10A_ARCHITECTURE_DEPENDENCY_AUDIT

Date: 2026-02-21
Mode: Static/read-only audit (no package installs, no code refactors)
Scope: `steps/**`, `cli/**`, `api/**`, `scripts/**`, plus runtime-coupled `common/**`, memory router/stores, and Qdrant integration.

## Import Surface Summary

### Full third-party module inventory (49 modules)
`PIL`, `chardet`, `chromadb`, `click`, `cross_video_entity_resolver`, `cv2`, `datasets`, `deep_sort_realtime`, `dotenv`, `face_recognition`, `facenet_pytorch`, `faiss`, `fastapi`, `faster_whisper`, `flash_attn`, `huggingface_hub`, `knowledge_graph`, `langchain_community`, `langchain_text_splitters`, `librosa`, `matplotlib`, `mutagen`, `numpy`, `pandas`, `psutil`, `pyannote`, `pydantic`, `pytesseract`, `requests`, `reverse_geocoder`, `scenedetect`, `sentence_transformers`, `sklearn`, `soundfile`, `starlette`, `tabulate`, `timeline_builder`, `timezonefinder`, `torch`, `torchaudio`, `torchvision`, `transformers`, `typer`, `ultralytics`, `unified_knowledge_graph`, `uvicorn`, `webrtcvad`, `yaml`, `zenml`.

Evidence sources:
- static imports in `steps/**`, `cli/**`, `api/**`, `scripts/**` (AST scan)
- examples in `steps/audio_transcribe/step.py:34`, `steps/common/qdrant_client.py:6`, `api/main.py:16`, `cli/retrieve.py:53`

### Runtime grouping (code-backed)

- Required for baseline/core control plane:
`yaml`, `dotenv`, `requests`, `click`, `typer`, `tabulate`, `fastapi`, `uvicorn`, `pydantic`, `starlette`, `psutil`, `pandas`, `chardet`, `numpy`
  - refs: `steps/common/config_loader.py:8`, `steps/common/config_loader.py:87`, `api/main.py:10`, `cli/run_ingestion.py:23`, `cli/graph_query.py:6`, `cli/graph_query.py:9`, `api/main.py:16`, `api/server.py:19`, `api/routes/search.py:9`, `cli/watchdog.py:971`, `steps/system_metrics/step.py:10`

- GPU_ENHANCED-focused:
`torch`, `torchvision`, `transformers`, `cv2`, `ultralytics`, `face_recognition`, `facenet_pytorch`, `deep_sort_realtime`, `flash_attn`
  - refs: `steps/common/gpu_config.py:77`, `steps/image_embed_clip/step.py:67`, `steps/video_scene_detect/gpu_scene_detect.py:9`, `steps/object_detect/step.py:38`, `steps/face_embed/step.py:29`, `steps/object_track_yolo/step.py:15`, `steps/common/audio_gpu_optimizer.py:181`

- WSL audio-focused:
`faster_whisper`, `librosa`, `soundfile`, `pyannote`, `torchaudio`, `webrtcvad`, `mutagen`
  - refs: `steps/audio_transcribe/step.py:34`, `steps/audio_transcribe/step.py:92`, `steps/audio_diarize/step.py:86`, `steps/audio_diarize/step.py:40`, `steps/common/vad_preprocessor.py:9`, `steps/audio/segmentation/phase1_vad_segmentation.py:11`, `steps/audio_metadata/step.py:21`

- Phase 6 scene embeddings/retrieval-focused:
`PIL`, `scenedetect`, `sentence_transformers`, `reverse_geocoder`, `timezonefinder`, `datasets`
  - refs: `steps/video/scene_embedder.py:11`, `steps/video_scene_detect/step.py:120`, `steps/text_embed/step.py:44`, `steps/image_exif/step.py:52`, `steps/image_exif/step.py:64`, `scripts/download_datasets.py:15`

- Vector operations-focused:
`faiss`, `chromadb`, `langchain_community`, `langchain_text_splitters`
  - refs: `steps/common/memory_stores.py:173`, `cli/chroma_store.py:73`, `api/main.py:684`, `cli/chroma_store.py:84`

- Mixed / unresolved surface:
`cross_video_entity_resolver`, `knowledge_graph`, `timeline_builder`, `unified_knowledge_graph`, `zenml`
  - refs: `scripts/build_unified_kg.py:24`, `scripts/build_unified_kg.py:25`, `scripts/build_unified_kg.py:26`, `scripts/build_kg_standalone.py:20`, `steps/graph_builder/graph_builder.py:10`

### Conditionally loaded imports
Heavy dependencies are mostly lazy or guarded (`try/except`) in step functions.
- refs: `steps/audio_transcribe/step.py:34`, `steps/common/memory_stores.py:173`, `steps/object_detect/step.py:38`, `steps/video/scene_embedder.py:37`, `cli/chroma_store.py:72`

## Execution Path Dependency Matrix

| Path | Entry / Flow | Required modules | External binaries / services | Env & profile gates |
|---|---|---|---|---|
| Single-file ingestion | `pipelines/direct_ingestion.py:20` -> `cli/run_ingestion.py:964` -> `_run_step` (`cli/run_ingestion.py:534`) -> `cli/step_runner.py` | `typer`, `yaml`, `requests`, step modules, `torch` family depending on step | `conda` (`steps/common/tool_paths.py:39`), `ffmpeg` (`cli/run_ingestion.py:709`, `cli/run_ingestion.py:733`), optional `wsl` audio bridge (`cli/run_ingestion.py:875`) | `GOODQ_HOST_PROFILE`, `GOODQ_REQUIRE_GPU`, `GOODQ_REQUIRE_WSL_AUDIO`, `GOODQ_STEP_TIMEOUT_MS`, `GOODQ_VERBOSE`, `phase6.enabled` (`cli/run_ingestion.py:1406`) |
| Audio-only ingestion | `cli/watchdog.py:597` (`ingest_audio`) -> `run_conda_step` (`steps/common/conda_runner.py:17`) | `faster_whisper/librosa/soundfile/pyannote/torchaudio`, `text_embed`, `sentiment`, `tagger` | `conda`, optional `wsl` (audio steps), `ffmpeg` in downstream audio paths | `GOODQ_STEP_TIMEOUT_MS` (`cli/watchdog.py:625`), WSL gates in `steps/audio_transcribe/step.py:509`-`620` |
| Image-only ingestion | `cli/watchdog.py:689` (`ingest_image`) -> conda step plan (`cli/watchdog.py:733`) | `PIL`, `torch`, `transformers`, `cv2`, `ultralytics`, `face_recognition`, `facenet_pytorch` | `conda` | profile-driven GPU behavior (`steps/common/profile_config.py:41`-`65`, `steps/common/gpu_config.py:192`-`203`) |
| Text-only ingestion | `cli/watchdog.py:781` (`ingest_document`) -> `pdf_text` then `text_embed` | `sentence_transformers`, `faiss`, `requests` (indirect), `pydantic` for API side | `conda`, `pdftotext` (`steps/pdf_text/step.py:8`-`20`) | `GOODQ_STEP_TIMEOUT_MS` (`cli/watchdog.py:813`) |
| Scene bundle registration | `register_scene_bundle` (`steps/common/memory.py:270`) -> `build_memory_router` (`steps/common/memory_manager.py:10`) | SQLite + memory router/stores, `faiss`, Qdrant HTTP client (`requests`) | Qdrant service (`http://127.0.0.1:6333` by config), FAISS index files | `memory.routing.*` (`steps/common/memory_manager.py:14`-`15`), `GOODQ_VECTOR_DEBUG` (`steps/common/memory.py:477`, `steps/common/qdrant_client.py:41`) |
| Vector write path | Phase 6 scene embeddings (`steps/video/scene_visual_embeddings.py:16`) and router inserts (`steps/common/memory_router.py:47`) | `torch`, `transformers`, `PIL`, `numpy`, `faiss`, qdrant client | Qdrant upsert (`steps/video/scene_visual_embeddings.py:127`, `185`), FAISS local index | `phase6.enabled` + `phase6.retrieval.enable` (`cli/run_ingestion.py:1406`, `steps/video/scene_visual_embeddings.py:121`) |
| Retrieval path | API search (`api/routes/search.py:57`) -> `retrieval/multimodal_search.py`; CLI fallback `cli/retrieve.py:164` | `sentence_transformers`, `transformers` (CLIP), `torch`, `numpy`, qdrant client, `faiss` fallback | Qdrant service, FAISS index, SQLite for metadata joins (`cli/retrieve.py:61`) | `phase6.retrieval.fusion_weights` (`retrieval/multimodal_search.py:43`), `GOODQ_RETRIEVAL_CONTEXT` (`steps/common/qdrant_client.py:210`) |

## Declared vs Actual Dependencies

### Declaration files found
- `setup.py`
- `api/requirements.txt`
- `envs/*/requirements.txt` (19 env-specific requirement files)
- `wsl2_audio/requirements-locked.txt`
- lock set exists under `envs/locks/*.lock.txt`

No `pyproject.toml` and no `environment.yml`/`environment.yaml` were found.

### Declaration posture
- `setup.py:11`-`13` has empty `install_requires`.
- Dependencies are split by env files, not centrally declared for shared runtime.
- `api/requirements.txt` declares `fastapi`, `uvicorn`, `chromadb`, langchain packages, but not `requests` even though API imports it (`api/main.py:10`).

### Import/declaration mismatches (high-signal)
- Not explicitly declared in discovered requirements surface:
  - `typer` (CLI entrypoints) (`cli/run_ingestion.py:23`)
  - `tabulate` (`cli/graph_query.py:9`)
  - `webrtcvad` (`steps/audio/segmentation/phase1_vad_segmentation.py:11`)
  - `flash_attn` (`steps/common/audio_gpu_optimizer.py:181`)
  - `zenml` (`steps/graph_builder/graph_builder.py:10`)
- Shared runtime deps used broadly but not in a single canonical base set:
  - `yaml` (`steps/common/config_loader.py:8`)
  - `python-dotenv` (`steps/common/config_loader.py:87`)
  - `requests` (`steps/common/qdrant_client.py:6`, `api/main.py:10`)

Notes:
- `pydantic` and `starlette` may arrive transitively via `fastapi`, but they are imported directly in runtime code.

## Platform Segmentation

### Windows-only runtime (host control plane)
- `cli/run_ingestion.py`, `cli/watchdog.py`, `steps/common/conda_runner.py` depend on Windows path conventions and `conda run` orchestration.
- refs: `cli/run_ingestion.py:563`, `cli/watchdog.py:603`, `steps/common/conda_runner.py:45`

### WSL-only runtime (audio acceleration)
- `steps/audio_ingest_unified/step_wsl2.py` shells into `wsl -d <distro>`.
- `wsl2_audio/requirements-locked.txt` captures Linux-side pinned stack.
- refs: `steps/audio_ingest_unified/step_wsl2.py:35`, `steps/audio_ingest_unified/step_wsl2.py:54`

### Shared Python layer
- `steps/common/*` for config/profile/memory/qdrant/router; reused by CLI and API.
- refs: `steps/common/config_loader.py:79`, `steps/common/memory_manager.py:10`, `steps/common/qdrant_client.py:26`

### Optional feature layer
- API/search (`api/routes/search.py`), Chroma (`cli/chroma_store.py`), Phase 6 (`steps/video/scene_visual_embeddings.py`), graph tooling.

### Legacy remnants
- `common/gpu_manager.py` is still referenced via optional hook in step runner (`cli/step_runner.py:217`) despite core GPU policy now living in `steps/common/gpu_config.py`.
- Root `config.yaml` contains legacy/malformed path surface while canonical loader targets `configs/config.yaml`.
  - refs: `steps/common/config_loader.py:106`-`114`, `config.yaml:70`, `config.yaml:128`

### Dead code / unresolved imports
- Missing modules referenced by scripts:
  - `cross_video_entity_resolver`, `unified_knowledge_graph`, `timeline_builder`, `knowledge_graph`
  - refs: `scripts/build_unified_kg.py:24`-`26`, `scripts/build_kg_standalone.py:20`
- Step map references missing module `steps.object_track.step`.
  - ref: `cli/step_runner.py:83`; filesystem path absent (`steps/object_track` missing)

## Hidden Runtime Assumptions

- `ffmpeg` must exist on host PATH or configured path (`steps/common/tool_paths.py:28`; extraction at `cli/run_ingestion.py:709`, `733`).
- `conda` executable must resolve (`steps/common/tool_paths.py:39`, `steps/common/conda_runner.py:45`).
- Qdrant expected reachable at configured host (default `http://127.0.0.1:6333`) (`configs/config.yaml:149`-`152`, `steps/common/qdrant_client.py:80`).
- PDF ingestion assumes `pdftotext` binary availability (`steps/pdf_text/step.py:8`-`20`).
- WSL audio path assumes distro availability and command execution through `wsl` (`steps/audio_ingest_unified/step_wsl2.py:35`, `54`).
- Memory routing defaults are applied from code if `memory` section is missing in canonical config (`steps/common/memory_manager.py:12`-`17`).

## Risk Flags

- High: shared runtime dependency set is not centrally declared (`setup.py` empty), increasing environment drift and runtime import failures.
  - refs: `setup.py:11`-`13`
- High: API imports `requests` but `api/requirements.txt` omits it.
  - refs: `api/main.py:10`, `api/requirements.txt:1`-`5`
- High: unresolved imports in KG scripts and missing step module (`object_track`) indicate dead/broken execution surfaces.
  - refs: `scripts/build_unified_kg.py:24`-`26`, `cli/step_runner.py:83`
- Medium: vector writes silently drop mismatched dimensions in router/store filtering.
  - refs: `steps/common/memory_router.py:41`-`44`, `steps/common/memory_stores.py:194`-`200`
- Medium: vector dimensions are hardcoded in multiple places (384/512/768), risking drift across components.
  - refs: `retrieval/multimodal_search.py:102`-`105`, `steps/video/scene_visual_embeddings.py:130`, `188`, `steps/text_embed/step.py:77`
- Medium: baseline/WSL/GPU dependency sets are profile-gated in code but not packaged as explicit install groups.
  - refs: `steps/common/profile_config.py:41`-`65`, `steps/audio_transcribe/step.py:509`-`620`

## Minimal Baseline Dependency Set

Python packages (minimum practical core):
- `pyyaml`, `python-dotenv`, `requests`
- `typer`, `click`, `tabulate`
- `numpy`
- `fastapi`, `uvicorn`, `pydantic`
- `psutil`, `pandas`, `chardet`
- `sentence-transformers`, `torch` (CPU acceptable), `faiss-cpu`

External/runtime tools:
- `conda` (step isolation), `ffmpeg` (video/audio extraction), `pdftotext` (PDF path)

## Minimal GPU_ENHANCED Dependency Set

Baseline set plus:
- CUDA-enabled `torch`, `torchvision`, `torchaudio`
- `transformers`, `sentencepiece`, `tokenizers`
- `opencv-python(-headless)`, `ultralytics`
- `face-recognition`, `facenet-pytorch`
- `faster-whisper`
- optional perf ext: `flash-attn`

## Minimal WSL Audio Dependency Set

Inside WSL env (Linux side):
- CUDA-enabled `torch`, `torchaudio`
- `faster-whisper` (+ `ctranslate2`)
- `librosa`, `soundfile`, `numpy`
- `pyannote.audio` (if diarization enabled)
- `webrtcvad`, `mutagen`

System requirements:
- WSL distro configured and reachable (`GOODQ_WSL_DISTRO`), NVIDIA GPU pass-through available to WSL

## Recommendations (no changes applied)

1. Define a canonical base dependency file for shared runtime (`steps/common`, CLI, API) and keep env-specific overlays for specialized steps.
2. Add explicit dependency declarations for directly imported packages currently implicit/transitive (`requests` in API env, CLI deps like `typer`/`tabulate`, etc.).
3. Split documented install groups by profile: `BASELINE`, `GPU_ENHANCED`, `WSL_AUDIO` with strict ownership.
4. Add an import-surface CI check to detect unresolved modules (`cross_video_entity_resolver`, `steps.object_track`, etc.) before runtime.
5. Consolidate vector dimension constants to one config-backed authority and enforce validation with explicit logging when vectors are dropped.
6. Keep WSL lockfile (`wsl2_audio/requirements-locked.txt`) version-aligned with host-side expectations where cross-surface behavior matters.
7. Keep canonical config source explicit (`configs/config.yaml`) and mark root `config.yaml` as legacy-only to reduce operator confusion.
8. Add dependency smoke checks per execution path (single-file/audio/image/text/retrieval) to validate declared vs actual runtime requirements.

