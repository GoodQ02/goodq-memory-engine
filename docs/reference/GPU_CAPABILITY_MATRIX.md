<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-02-12 -->

# GPU Capability Matrix (Repository Intent)

Scope: static repository analysis of GPU-related code/config references.  
Policy target applied: system should stay functional without a GPU; GPU use should be feature-gated.

## 1) Components That Benefit From GPU Acceleration

| Component | GPU intent | Workload class | API assumption | Evidence |
|---|---|---|---|---|
| Audio transcription (Windows path + WSL2 path) | Benefits strongly; has CPU path | Inference | CUDA-assumed in accelerated path | `steps/audio_transcribe/step.py:34`, `steps/audio_transcribe/step.py:469`, `steps/audio_transcribe/step.py:481`, `wsl2_audio/process_audio.py:74`, `wsl2_audio/process_audio.py:98` |
| Audio diarization (+ OSD/resegmentation extras) | Benefits strongly; core diarization can still run CPU | Inference | CUDA-assumed in accelerated path | `steps/audio_diarize/step.py:51`, `steps/audio_diarize/step.py:67`, `steps/audio_diarize/step.py:441`, `steps/audio_diarize/step.py:462`, `steps/audio_diarize/step.py:627` |
| Video scene detection (GPU frame-diff / histogram) | Benefits; CPU fallback exists | Preprocessing | CUDA-assumed in accelerated path | `steps/video_scene_detect/step.py:108`, `steps/video_scene_detect/step.py:110`, `steps/video_scene_detect/gpu_scene_detect.py:31`, `steps/video_scene_detect/gpu_scene_detect.py:74` |
| Object detection (YOLO) | Benefits; CPU retry exists | Inference | CUDA-assumed in accelerated path | `steps/object_detect/step.py:34`, `steps/object_detect/step.py:35`, `steps/object_detect/step.py:65` |
| Face embedding (OpenCV YuNet/SFace) | CPU-safe primary capability pack; dlib is a visible fallback | Inference | Vendor-agnostic CPU path | `steps/face_embed/step.py` |
| Text embedding (SentenceTransformer) | Benefits; CPU fallback exists | Inference | CUDA-assumed in accelerated path | `steps/text_embed/step.py:40`, `steps/text_embed/step.py:41`, `steps/text_embed/step.py:46` |
| Text emotion classification (transformers) | Benefits; CPU path exists | Inference | CUDA-assumed in accelerated path | `steps/emotion_classify/step.py:39`, `steps/emotion_classify/step.py:40`, `steps/emotion_classify/step.py:92`, `steps/emotion_classify/step.py:93` |
| Image captioning (BLIP / fallback pipeline) | Benefits; CPU path exists | Inference | CUDA-assumed in accelerated path | `steps/image_caption/step.py:32`, `steps/image_caption/step.py:45`, `steps/image_caption/step.py:67`, `steps/image_caption/step.py:106` |
| Phase 6 scene visual embedding (CLIP + DINO) | Benefits strongly for batching throughput | Inference | CUDA-assumed in accelerated path | `steps/video/scene_embedder.py:33`, `steps/video/scene_embedder.py:41`, `steps/video/scene_embedder.py:67`, `steps/video/scene_embedder.py:74`, `steps/video/scene_visual_embeddings.py:103`, `configs/config.yaml:256` |

## 2) Components That Currently Act As GPU-Required Profiles

| Component | Why it trends toward “required” | Workload class | API assumption | Evidence |
|---|---|---|---|---|
| `GPU_ENHANCED` runtime profile | CUDA is intentionally expected only when the accelerated host profile or strict flags are selected; `BASELINE` must remain CPU-safe | Optional optimization (platform profile) | CUDA-assumed when explicitly selected | `AGENTS.md:19`, `AGENTS.md:45`, `configs/config.yaml:139`, `configs/config.yaml:140`, `docs/reference/PLATFORM_SUPPORT.md:1` |
| WSL2 unified audio worker (`process_audio.py`) | Accelerated audio path prefers CUDA when available and is configured from live runtime settings | Inference | CUDA-assumed in accelerated path | `configs/config.yaml:221`, `configs/config.yaml:229`, `wsl2_audio/process_audio.py:527`, `wsl2_audio/process_audio.py:621`, `wsl2_audio/process_audio.py:727` |
| WSL2 audio bootstrap constraints | Active WSL audio setup pins the conservative CUDA 12.1 torch lane and the PyAnnote/Hugging Face Hub compatibility pair; historical lock snapshots may lag until regenerated | Optional optimization (runtime packaging) | CUDA-assumed | `wsl2_audio/requirements-bootstrap-constraints.txt`, `wsl2_audio/setup_wsl2_audio.sh`, `docs/reference/WSL_AUDIO_RUNTIME.md` |

## 3) Components That Must Remain CPU-Safe

| Component | CPU-safe intent | Workload class | API assumption | Evidence |
|---|---|---|---|---|
| Scene detection fallback path | Explicit fallback to CPU PySceneDetect when GPU unavailable/fails | Preprocessing | Vendor-agnostic CPU path | `steps/video_scene_detect/step.py:114`, `steps/video_scene_detect/step.py:119`, `steps/video_scene_detect/step.py:120` |
| Object detection fallback path | Retries on CPU for known CUDA NMS failures | Inference | Vendor-agnostic CPU path | `steps/object_detect/step.py:90`, `steps/object_detect/step.py:93` |
| Audio transcription fallback path | Falls back to CPU device and int8 compute type | Inference | Vendor-agnostic CPU path | `steps/audio_transcribe/step.py:469`, `steps/audio_transcribe/step.py:471`, `steps/audio_transcribe/step.py:481`, `steps/audio_transcribe/step.py:482` |
| Audio diarization fallback path | CPU selected when CUDA unavailable; GPU move failures explicitly downgrade to CPU; GPU-only extras skipped | Inference | Vendor-agnostic CPU path | `steps/audio_diarize/step.py:26`, `steps/audio_diarize/step.py:72`, `steps/audio_diarize/step.py:73`, `steps/audio_diarize/step.py:490`, `steps/audio_diarize/step.py:491` |
| Image captioning fallback path | BLIP failure resets to CPU and fallback pipeline supports non-CUDA device | Inference | Vendor-agnostic CPU path | `steps/image_caption/step.py:50`, `steps/image_caption/step.py:51`, `steps/image_caption/step.py:67`, `steps/image_caption/step.py:110` |
| WSL2 audio emotion stage | Explicitly forced to CPU to preserve GPU memory budget | Inference | Vendor-agnostic CPU path | `wsl2_audio/process_audio.py:197`, `wsl2_audio/process_audio.py:206`, `wsl2_audio/process_audio.py:221` |
| OCR pipeline | Tesseract/Pillow path is CPU toolchain | Preprocessing | Vendor-agnostic CPU path | `steps/image_ocr/step.py:19`, `steps/image_ocr/step.py:26` |
| PDF text extraction | `pdftotext` shell path is CPU toolchain | Preprocessing | Vendor-agnostic CPU path | `steps/pdf_text/step.py:8`, `steps/pdf_text/step.py:19` |
| Frame extraction + embedding pooling | FFmpeg frame extraction and NumPy pooling are CPU-safe foundations | Preprocessing | Vendor-agnostic CPU path | `steps/video/scene_frame_extractor.py:41`, `steps/video/scene_frame_extractor.py:175`, `steps/video/embedding_pooler.py:27`, `steps/video/embedding_pooler.py:28` |
| Global GPU feature gating | Auto-GPU setup can be disabled and scene config exposes `use_gpu` flag | Optional optimization | CUDA-assumed acceleration with CPU toggle | `steps/common/gpu_config.py:178`, `steps/common/gpu_config.py:182`, `scripts/config_schema.py:211`, `configs/config.yaml:227` |

## API Assumption Summary

- CUDA/NVIDIA is the dominant assumption in active GPU paths (PyTorch `torch.cuda`, explicit `"cuda"` devices, CUDA version pinning):  
  `steps/common/gpu_config.py:72`, `steps/common/gpu_config.py:108`, `configs/config.yaml:114`, `wsl2_audio/config.json:8`.
- ROCm usage in project runtime code: **none found**.  
  Docs explicitly describe current scope as CUDA/NVIDIA-only: `docs/guides/gpu/GPU_SETUP.md:299`, `docs/guides/gpu/GPU_OPTIMIZATION_GUIDE.md:284`.
- Vendor-agnostic CPU-safe paths exist for core preprocessing/retrieval surfaces (OCR, PDF, frame extraction, pooling, CPU fallbacks above).

## Training vs Inference Note

- GPU references are overwhelmingly inference/preprocessing/optimization oriented; no explicit model-training loops were identified in active pipeline step code.
