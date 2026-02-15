<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-02-12 -->

# Watchdog Automatic Ingestion System

**Status**: ✅ **OPERATIONAL** (December 14, 2025)  
**Location**: `cli/watchdog.py` (Canonical)  
**Duplicate**: `scripts/watchdog_ingest.py` (Legacy, functionally identical)

---

## Overview

The Watchdog is GoodQ's **zero-touch ingestion system** that automatically monitors the `import_inbox` folder and processes any media dropped into it. No manual commands required—just drop files and walk away.

### What It Does

- **Monitors**: `<project_root>/import_inbox` every 2 seconds
- **Detects**: Video, audio, image, and document files
- **Validates**: Waits 3 seconds for file stability (copy completion)
- **Deduplicates**: SHA-256 hash prevents reprocessing identical files
- **Processes**: Routes to appropriate pipeline (video/audio/image/document)
- **Tracks**: AI Control Agent monitors and diagnoses failures
- **Archives**: Moves to `processed/` (success) or `failed/` (error)

---

## Features

### ✅ Confirmed Operational (Dec 14, 2025)

| Feature | Implementation | Status |
|---------|---------------|--------|
| **File Detection** | 2s polling loop, FileState tracking | ✅ Active |
| **Stability Check** | 3s wait + size/mtime comparison | ✅ Active |
| **Hash Deduplication** | SHA-256 streaming, registry in JSON | ✅ Active |
| **Control Agent Integration** | AI diagnosis on failure, retry recommendations | ✅ Active |
| **Single-Instance Lock** | PID-based lockfile, stale lock detection | ✅ Active |
| **Multi-Format Support** | Video, audio, image, PDF/text documents | ✅ Active |
| **Progress Tracking** | `progress_tracker` integration | ✅ Active |
| **Graceful Shutdown** | Queue drain, thread join on Ctrl+C | ✅ Active |

---

## Supported File Types

### Video (via Direct Ingestion)
```
.mp4, .avi, .mov, .mkv, .wmv, .flv, .webm, .m4v
```
**Pipeline**: `pipelines/direct_ingestion.py` → Full scene detection, audio/video analysis

### Audio (via Conda Step Runner)
```
.mp3, .wav, .flac, .m4a, .aac, .ogg, .wma
```
**Steps**: Transcription → CLAP embedding → Emotion → Metadata → Text embed → Sentiment

### Image (via Conda Step Runner)
```
.jpg, .jpeg, .png, .bmp, .gif, .tiff, .webp
```
**Steps**: OCR → Caption → Object Detection → Face Embed → DINO/CLIP → Text Embed

### Documents (via Conda Step Runner)
```
.pdf, .txt, .md
```
**Steps**: PDF text extraction → Text embed → Sentiment → Emotion → Tagging

---

## Architecture

### Component Diagram
```
┌─────────────────────────────────────────────────────────────┐
│                    Watchdog System                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐         ┌──────────────┐                │
│  │  Monitor     │ 2s poll │  FileState   │                │
│  │  Thread      │────────▶│  Tracker     │                │
│  └──────────────┘         └──────────────┘                │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────┐         ┌──────────────┐                │
│  │  Stability   │  3s     │  SHA-256     │                │
│  │  Check       │────────▶│  Hash        │                │
│  └──────────────┘         └──────────────┘                │
│         │                        │                          │
│         ▼                        ▼                          │
│  ┌──────────────┐         ┌──────────────┐                │
│  │  Processed   │  lookup │  Queue       │                │
│  │  Registry    │────────▶│  (FIFO)      │                │
│  └──────────────┘         └──────────────┘                │
│                                  │                          │
│                                  ▼                          │
│                           ┌──────────────┐                 │
│                           │  Worker      │                 │
│                           │  Thread      │                 │
│                           └──────────────┘                 │
│                                  │                          │
│                                  ▼                          │
│         ┌────────────────────────┼────────────────────┐   │
│         │                        │                    │   │
│    ┌────▼────┐          ┌───────▼──────┐      ┌─────▼───┐│
│    │ Video   │          │ Audio/Image  │      │Document ││
│    │Pipeline │          │ Conda Steps  │      │Pipeline ││
│    └────┬────┘          └───────┬──────┘      └─────┬───┘│
│         │                       │                    │   │
│         └───────────────────────┼────────────────────┘   │
│                                 ▼                          │
│                         ┌──────────────┐                  │
│                         │ Control      │                  │
│                         │ Agent        │                  │
│                         └──────────────┘                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Dataflow

```
import_inbox/video.mp4
    │
    ▼ [Monitor detects]
FileState(path, size, mtime)
    │
    ▼ [Wait 3s, check stable]
Compute SHA-256 hash
    │
    ▼ [Check registry]
Already processed? ──YES──▶ Rename PROCESSED_*, skip
    │
   NO
    │
    ▼ [Add to queue]
Worker thread pulls from queue
    │
    ▼ [Copy to processing/]
<GOODQ_DATA_ROOT>/GoodQ_Data/processing/video_<hash>/video.mp4
    │
    ▼ [Route by file type]
    │
    ├─▶ VIDEO: run_direct_ingestion() → Scene detect → Audio WSL2 → Vision → KG
    │
    ├─▶ AUDIO: Conda steps → Transcribe → Embed → Emotion → Metadata
    │
    ├─▶ IMAGE: Conda steps → OCR → Caption → Detect → Embed
    │
    └─▶ DOCUMENT: Conda steps → Extract text → Embed → Sentiment
    │
    ▼ [Success?]
    │
┌───┴───┐
│       │
YES    NO
│       │
▼       ▼
<GOODQ_DATA_ROOT>/GoodQ_Data/processed/    <GOODQ_DATA_ROOT>/GoodQ_Data/failed/
PROCESSED_video.mp4                FAILED_video.mp4
```

---

## Key Configuration

### File Locations (Hardcoded in `cli/watchdog.py`)

```python
WATCH_DIR = "<project_root>/import_inbox"
PROCESSING_DIR = "<GOODQ_DATA_ROOT>/GoodQ_Data/processing"
PROCESSED_DIR = "<GOODQ_DATA_ROOT>/GoodQ_Data/processed"
FAILED_DIR = "<GOODQ_DATA_ROOT>/GoodQ_Data/failed"
STATE_FILE = "<project_root>/logs/watchdog_state.json"
LOG_FILE = "<project_root>/logs/watchdog.log"
```

### Timing Parameters

```python
POLL_INTERVAL = 2.0      # Scan directory every 2 seconds
STABILITY_WAIT = 3.0     # File must be unchanged for 3s
MAX_WORKERS = 1          # Process one file at a time
```

### Timeouts (Dynamic, based on file size)

```python
# Minimum 8 hours, +3 hours per GB
timeout_seconds = max(28800, int(file_size_gb * 10800))

# Per-step timeout for conda runner
GOODQ_STEP_TIMEOUT_MS = 600_000  # 10 minutes per step
```

---

## Control Agent Integration

The Watchdog integrates with `agents/control_agent.py` for AI-powered monitoring:

### Hooks
```python
# On file detection
control_agent.on_file_detected(filename, file_type, size)

# On processing start
control_agent.on_processing_start(filename, file_type)

# On error
diagnosis = control_agent.analyze_error(error, context)
# Returns: {'diagnosis': str, 'recommended_action': str, 'changes': str}

# On completion
control_agent.on_processing_complete(filename, success, error)
```

### AI Diagnosis Example
```
[BOT] AI Diagnosis: Audio diarization timeout - speaker overlap detected
[BOT] AI Recommendation: Increase VAD threshold to 0.5, reduce max_speakers to 3
```

---

## Usage

### Start Watchdog

#### Option 1: Batch Script
```batch
START_WATCHDOG.bat
```

#### Option 2: PowerShell
```powershell
cd <project_root>
python -m cli.watchdog
```

#### Option 3: Python
```python
python <project_root>\cli\watchdog.py
```

### Drop Files
```
1. Copy files to <project_root>\import_inbox\
2. Watchdog detects within 2 seconds
3. Wait 3 seconds for stability check
4. Processing begins automatically
5. Monitor logs or console for progress
```

### Monitor Progress

#### View Live Logs
```powershell
Get-Content <project_root>\logs\watchdog.log -Wait -Tail 20
```

#### Check Processed Registry
```powershell
Get-Content <project_root>\logs\watchdog_state.json | ConvertFrom-Json | Format-List
```

#### Check If Watchdog Running
```powershell
Get-Process | Where-Object {$_.CommandLine -like "*watchdog*"}
```

---

## State Management

### Processed Registry (`watchdog_state.json`)

```json
{
  "a3f5b8c2e1d9f4a6...": {
    "original_name": "interview_clip.mp4",
    "status": "success",
    "timestamp": "2025-12-14T15:23:10.123456"
  },
  "7d2e9f1a4b6c8e3d...": {
    "original_name": "corrupted_audio.wav",
    "status": "failed",
    "error": "Audio file truncated",
    "timestamp": "2025-12-14T16:45:22.654321"
  }
}
```

### Single-Instance Locking

```python
# Creates <GOODQ_DATA_ROOT>/GoodQ_Data/.watchdog.lock with PID
# On startup:
#   - If lock exists, check if PID is alive
#   - If alive: exit (already running)
#   - If dead: remove stale lock, create new one
# On shutdown: remove lock
```

---

## Pipeline Details

### Video Processing (`ingest_video`)

1. **Copy to temp**: `processing/video_<hash>/video.mp4`
2. **Call**: `pipelines.direct_ingestion.run_direct_ingestion()`
3. **Stages**:
   - Scene detection (scenedetect)
   - Per-scene loop:
     - Extract keyframe → Vision pipeline
     - Extract audio chunk → WSL2 unified audio
     - Entity extraction
     - Knowledge graph update
4. **Cleanup**: Remove temp dir on success, preserve on failure

### Audio Processing (`ingest_audio`)

```python
step_plan = [
    ("goodq_audio_transcribe", "audio_transcribe"),      # Whisper
    ("goodq_audio_embed", "audio_embed_clap"),           # CLAP embeddings
    ("goodq_audio_emotion", "audio_emotion"),            # Wav2Vec2 emotion
    ("goodq_audio_metadata", "audio_metadata"),          # Duration, channels
    ("goodq_audio_metadata", "audio_time_hints"),        # Temporal markers
    ("goodq_audio_metadata", "audio_music_events"),      # Music detection
    ("goodq_text_embed", "text_embed"),                  # Sentence embeddings
    ("goodq_sentiment", "sentiment"),                    # Sentiment analysis
    ("goodq_emotion_classify", "emotion_classify"),      # Text emotion
    ("goodq_emotion_classify", "tagger")                 # Taxonomy tags
]
```

### Image Processing (`ingest_image`)

```python
step_plan = [
    ("goodq_image_caption", "image_ocr"),                # Tesseract OCR
    ("goodq_image_caption", "image_caption"),            # BLIP captioning
    ("goodq_object_detect", "object_detect"),            # YOLO detection
    ("goodq_face_embed", "face_embed"),                  # Face embeddings
    ("goodq_image_caption", "image_exif"),               # EXIF metadata
    ("goodq_image_caption", "image_embed_dino"),         # DINOv2 embeddings
    ("goodq_image_caption", "image_embed_clip"),         # CLIP embeddings
    ("goodq_text_embed", "text_embed"),                  # Text embeddings
    ("goodq_sentiment", "sentiment"),                    # Sentiment
    ("goodq_emotion_classify", "emotion_classify"),      # Emotion
    ("goodq_emotion_classify", "tagger")                 # Tags
]
```

---

## Troubleshooting

### Watchdog Not Starting

**Symptom**: Script exits immediately

**Diagnosis**:
```powershell
# Check for existing instance
Get-Content <GOODQ_DATA_ROOT>\GoodQ_Data\.watchdog.lock
```

**Fix**:
```powershell
# If stale lock, delete manually
Remove-Item <GOODQ_DATA_ROOT>\GoodQ_Data\.watchdog.lock -Force
```

---

### Files Not Detected

**Symptom**: Dropped files ignored

**Diagnosis**:
1. Check file extension is supported
2. Verify watch directory exists
3. Check logs for errors

**Fix**:
```powershell
# Verify directory
Test-Path <project_root>\import_inbox

# Check logs
Get-Content <project_root>\logs\watchdog.log -Tail 50
```

---

### Processing Hangs

**Symptom**: File stuck in processing

**Diagnosis**:
- Check GPU memory (may be full from vLLM)
- Check WSL2 audio service (may be crashed)
- Check per-step timeout (10 min default)

**Fix**:
```powershell
# Check GPU
nvidia-smi

# Restart WSL2 audio service
wsl -d Ubuntu bash -c "pkill -f audio_service.py && nohup python3 ~/goodq_audio/audio_service.py &"

# Kill watchdog, increase timeout in code
# GOODQ_STEP_TIMEOUT_MS = 1200_000  # 20 minutes
```

---

### Duplicate Files Skipped

**Symptom**: File marked PROCESSED without ingestion

**Diagnosis**: SHA-256 hash already in registry

**Fix**:
```powershell
# View registry
Get-Content <project_root>\logs\watchdog_state.json | ConvertFrom-Json

# Remove specific hash to force reprocess
# Edit JSON manually or delete entire file to reset
```

---

## Performance Notes

- **Single-threaded** (`MAX_WORKERS = 1`) to prevent GPU memory contention
- **Hash computation** is streaming (no full file load)
- **File stability check** prevents incomplete copies
- **Timeout scaling** prevents premature kills on large files
- **Control Agent** adds ~50ms overhead per event (negligible)

---

## Comparison: `cli/watchdog.py` vs `scripts/watchdog_ingest.py`

| Feature | `cli/watchdog.py` | `scripts/watchdog_ingest.py` |
|---------|-------------------|------------------------------|
| **Status** | ✅ Canonical | ⚠️ Legacy duplicate |
| **Location** | `cli/watchdog.py` | `scripts/watchdog_ingest.py` |
| **Video Pipeline** | `run_direct_ingestion()` (no subprocess) | Subprocess call to `cli.run_ingestion` |
| **Logging** | ASCII filter for Windows console | ASCII filter for Windows console |
| **Control Agent** | Integrated | Integrated |
| **Lines of Code** | 983 lines | 972 lines |
| **Recommendation** | **Use this** | Archive or delete |

**Verdict**: Both are functionally identical. `cli/watchdog.py` is the canonical version (discovered via forensic audit). `scripts/watchdog_ingest.py` should be retired.

---

## Integration Points

### With Config System
- **Loads**: `steps/common/config_loader.py::load_configs()`
- **Uses**: Database paths, model settings, thresholds
- **Run context**: Injects `run.id`, `run.pipeline`, `run.git_sha`

### With Progress Tracker
- **Start**: `start_processing(filename, total_steps)`
- **Finish**: `finish_processing("completed" | "failed")`
- **Errors**: `add_error(error_msg, step_name)`

### With Knowledge Graph
- Indirect via `run_direct_ingestion()` → `update_kg_for_scene()`
- Entities written to `knowledge_graph.db`

### With Memory DB
- Indirect via `run_direct_ingestion()` → `register_scene_bundle()`
- Scene bundles written to `memory.db`

---

## Future Enhancements

### Planned (Not Yet Implemented)
- [ ] Parallel processing (increase `MAX_WORKERS`)
- [ ] Priority queue (size/type-based scheduling)
- [ ] Email/webhook notifications
- [ ] Remote API for upload
- [ ] Web UI for queue management
- [ ] Cloud storage sync (S3, Drive)

### Already Implemented (But Latent)
- ✅ Control Agent diagnosis (active)
- ✅ Hash-based deduplication (active)
- ✅ Multi-format support (active)
- ✅ Graceful shutdown (active)

---

## Security & Reliability

### Security
- ✅ Single-instance lock prevents concurrent runs
- ✅ No network access required
- ✅ Files never leave local system
- ✅ State file is plaintext JSON (auditable)
- ⚠️ Runs with user permissions (no privilege escalation)

### Reliability
- ✅ Hash-based deduplication (collision-resistant)
- ✅ File stability check (prevents partial reads)
- ✅ Queue persistence (survives crashes)
- ✅ Temp files preserved on failure (debugging)
- ✅ Stale lock detection (auto-recovery)
- ✅ Graceful shutdown (queue drain)

---

## Testing

### Unit Tests
```bash
pytest tests/test_watchdog.py
```

### Integration Tests
```bash
# Drop test file
cp samples/smoke/sample.mp4 import_inbox/

# Monitor logs
Get-Content logs/watchdog.log -Wait -Tail 20

# Verify moved to processed
Test-Path <GOODQ_DATA_ROOT>\GoodQ_Data\processed\PROCESSED_sample.mp4
```

---

## Summary

The Watchdog system is **production-ready** and **operational** as of December 14, 2025. It provides:

- **Zero-touch ingestion** for all supported media types
- **AI-powered diagnostics** via Control Agent
- **Robust deduplication** via SHA-256 hashing
- **Graceful error handling** with preservation of failed files
- **Comprehensive logging** for auditing and debugging

**Canonical Implementation**: `cli/watchdog.py`  
**Duplicate (Legacy)**: `scripts/watchdog_ingest.py` (recommend archiving)

---

**Last Updated**: December 14, 2025  
**Verified By**: Forensic code audit + live system testing
