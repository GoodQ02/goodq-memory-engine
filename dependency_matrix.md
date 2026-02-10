# Dependency Matrix (Static Forensic Pass)

Analysis method: file inspection only (no project code executed).

## REQUIRED (core runtime)

| Dependency | Type | Why this is REQUIRED | Evidence (exact citations) |
|---|---|---|---|
| Windows host + PowerShell launch path | Runtime/OS | Canonical runtime and launch entrypoint are Windows-first. | `AGENTS.md:17`; `LAUNCH_GOODQ.bat:6`; `LAUNCH_GOODQ.ps1:21` |
| Python `>=3.10` | Runtime | Package contract pins minimum interpreter. | `setup.py:10`; `docs/architecture/SYSTEM_ARCHITECTURE.md:460` |
| Conda environment orchestration (`conda run`) | Runtime/tooling | Environment isolation + interpreter binding are contractually required. | `AGENTS.md:44`; `AGENTS.md:47`; `configs/python_paths.py:182`; `configs/python_paths.py:189` |
| YAML config loading (`PyYAML`) | Runtime library | Canonical config loader parses YAML for runtime settings. | `steps/common/config_loader.py:7`; `steps/common/config_loader.py:10`; `steps/common/config_loader.py:12` |
| SQLite persistence (memory + KG) | Data store | SQLite is listed as authoritative relational store and wired in config paths. | `AGENTS.md:11`; `AGENTS.md:22`; `configs/config.yaml:46`; `configs/config.yaml:47` |
| Qdrant service (`localhost:6333`) | Data store/service | Qdrant is canonical vector store and enabled in config. | `AGENTS.md:21`; `configs/config.yaml:139`; `configs/config.yaml:141`; `scripts/qdrant/START_QDRANT.bat:20` |
| Local storage topology on `L:/_DATA` | Hardware/storage assumption | Runtime paths are hard-wired to local Windows volumes in canonical config. | `configs/config.yaml:45`; `configs/config.yaml:53`; `configs/config.yaml:55`; `scripts/qdrant/START_QDRANT.bat:12` |
| PyTorch baseline for multimodal steps | Runtime library | Technical standard and environment matrix repeatedly require torch in active steps. | `AGENTS.md:45`; `docs/CLI-REFERENCE.md:127`; `docs/CLI-REFERENCE.md:155`; `envs/audio_diarize/requirements.txt:7` |

## OPTIONAL (feature-gated)

| Dependency | Type | Why this is OPTIONAL | Evidence (exact citations) |
|---|---|---|---|
| NVIDIA GPU + CUDA 12.1 profile | Hardware/runtime | Required only when `GPU_ENHANCED` profile is active; CPU-safe fallbacks exist for all referenced steps. | `AGENTS.md:19`; `AGENTS.md:45`; `configs/config.yaml:114`; `configs/config.yaml:115` |
| WSL2 Ubuntu audio compute extension | Runtime/OS | Audio pipeline offloads to WSL2, but architecture states optional enrichments may fail without halting ingestion. | `AGENTS.md:13`; `AGENTS.md:20`; `AGENTS.md:48`; `configs/config.yaml:194`; `scripts/wsl2_audio_bridge.py:115` |
| WSL audio services (queue daemon + direct invocation) | Runtime/service | Audio subsystem defines two WSL execution modes rather than a single mandatory service. | `docs/architecture/SYSTEM_ARCHITECTURE.md:223`; `docs/architecture/SYSTEM_ARCHITECTURE.md:224`; `docs/architecture/SYSTEM_ARCHITECTURE.md:234`; `docs/architecture/SYSTEM_ARCHITECTURE.md:238` |
| WSL audio venv + CUDA library shims | Runtime/tooling | Required only for WSL audio path. | `wsl2_audio/setup_cuda_env.sh:6`; `wsl2_audio/setup_cuda_env.sh:12`; `wsl2_audio/setup_cuda_env.sh:15` |
| FFmpeg binary | External tool | Used for media extraction if present; system probes for availability and handles missing tool states. | `steps/common/tool_paths.py:33`; `steps/audio_diarize/step.py:150`; `api/main.py:265`; `api/main.py:271` |
| Tesseract OCR (`pytesseract` + binary) | External tool/library | OCR step is best-effort and gracefully degrades when dependency/tool missing. | `envs/ocr/requirements.txt:1`; `steps/image_ocr/step.py:14`; `steps/image_ocr/step.py:19`; `steps/image_ocr/step.py:23` |
| Poppler `pdftotext` | External tool | PDF text extraction is tool-backed and returns `None` on failure. | `envs/pdf_text/requirements.txt:1`; `steps/pdf_text/step.py:8`; `steps/pdf_text/step.py:19`; `steps/pdf_text/step.py:29` |
| FastAPI + Uvicorn server | Runtime/service | API scaffold exists and is toggled by config; not required for ingestion core. | `api/requirements.txt:1`; `api/requirements.txt:2`; `api/server.py:19`; `configs/config.yaml:273` |
| FAISS indices | Vector store | Explicitly described as enabled fallback behind Qdrant. | `AGENTS.md:51`; `envs/text_embed/requirements.txt:6`; `steps/image_embed_clip/step.py:93`; `steps/image_embed_clip/step.py:128` |
| ChromaDB / LangChain components | Library stack | Present in API requirements and health checks, but not canonical primary store. | `api/requirements.txt:3`; `api/requirements.txt:4`; `api/main.py:305`; `api/main.py:311` |
| Local LLM servers (LM Studio / vLLM / Ollama) | Service endpoints | Multiple local endpoints are configured as selectable backends. | `configs/config.yaml:73`; `configs/config.yaml:77`; `configs/config.yaml:81` |
| Home Assistant integration token + client | Integration | Separate integration block and dedicated environment dependency. | `configs/config.yaml:92`; `configs/config.yaml:94`; `envs/home_assistant_status/requirements.txt:1` |
| Face detection (`facenet-pytorch`) | Model/package | Marked disabled when dependency absent. | `envs/face_embed/requirements.txt:4`; `docs/goodq4all_agent_status.md:17` |
| Audio diarization stack (`pyannote`, `whisperx`, `faster-whisper`) | Model/package | Audio feature path dependencies in dedicated envs. | `envs/audio_diarize/requirements.txt:12`; `envs/audio_diarize/requirements.txt:13`; `envs/audio_transcribe/requirements.txt:2` |
| Scene detection (`scenedetect`, OpenCV) | Model/package | Step-specific dependency loaded conditionally in API capability checks. | `envs/video_scene_detect/requirements.txt:1`; `envs/video_scene_detect/requirements.txt:2`; `api/main.py:286`; `api/main.py:297` |
| GPU execution path for diarization (with CPU fallback) | Runtime behavior | Code resolves `cuda` when available and falls back to CPU on known GPU errors. | `steps/audio_diarize/step.py:23`; `steps/audio_diarize/step.py:26`; `steps/audio_diarize/step.py:71`; `steps/audio_diarize/step.py:73` |
| NAS / secondary external storage paths | Hardware/storage assumption | Config references external/network-attached paths beyond local data root. | `configs/config.yaml:66`; `configs/config.yaml:67`; `configs/config.yaml:107` |

## DEVELOPMENT-ONLY

| Dependency | Type | Why this is DEVELOPMENT-ONLY | Evidence (exact citations) |
|---|---|---|---|
| `pytest` | Test framework | Unit test discovery/config is pytest-specific. | `pytest.ini:1`; `pytest.ini:2`; `tests/README.md:227`; `tests/README.md:239` |
| `pytest-cov` | Test tooling | Coverage workflow documented for test runs only. | `tests/README.md:245`; `tests/README.md:389` |
| `black` | Dev tooling | Formatting check command documented in contributor workflow. | `README.md:923` |
| `mypy` | Dev tooling | Static typing check command documented in contributor workflow. | `README.md:926` |
