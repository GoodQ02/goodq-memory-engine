# Logging and Resilience Architecture

**Last Updated**: December 15, 2025  
**Status**: ✅ Active and Operational

---

## Overview

GoodQ implements a **dual-layer logging system** with **Q-Branch mission styling** and comprehensive error resilience. The system is designed for long-running, unattended ingestion with graceful degradation and automatic recovery.

---

## 🎯 Logging System

### 1. Mission Logger (Q-Branch Styled)

**Location**: `lib/goodq_logger.py`  
**Component Mapping**: `lib/mission_components.py`

The mission logger provides branded, contextual logging with visual clarity:

```python
from lib.goodq_logger import get_goodq_logger

logger = get_goodq_logger("audio_transcribe", component="Comms Decrypt")
logger.mission_start("Transcribing scene audio")
logger.mission_complete("audio_transcribe", duration=45.2)
```

**Output Style**:
```
[14:32:15] [MISSION] Comms Decrypt: Transcribing scene audio
[14:33:00] [SUCCESS] Comms Decrypt: Mission accomplished [45.2s]
```

#### Mission Components

Each pipeline step has a branded designation (see `lib/mission_components.py`):

| Step Name | Mission Component | Purpose |
|-----------|-------------------|---------|
| `video_scene_detect` | Recon Scanner | Scene boundary detection |
| `audio_transcribe` | Comms Decrypt | Speech-to-text |
| `audio_diarize` | Voice Separation | Speaker identification |
| `image_caption` | Visual Intel | Image understanding |
| `object_detect` | Target Identification | Object detection |
| `face_embed` | Facial Recognition | Face encoding |
| `audio_emotion` | Emotional Profiling | Emotion classification |
| `text_embed` | Linguistic Analysis | Text vectorization |
| `graph_builder` | Network Mapping | Knowledge graph construction |

**Full list**: 50+ components mapped in `MISSION_COMPONENTS` dict

---

### 2. Step Logger (CSV/JSONL Tracking)

**Location**: `steps/common/step_logger.py`

Provides structured logging for analytics and debugging:

```python
from steps.common.step_logger import log_step_run

log_step_run(
    cfg=config,
    step_name="image_caption",
    item={"source_path": "video.mp4"},
    duration_ms=1523.4,
    status="ok",  # ok | skipped | error
    error=None,
    extra={"model": "blip-base", "gpu": True}
)
```

**Outputs**:
- `logs/step_runs.csv` - Tabular step execution records
- `logs/step_runs.jsonl` - Structured JSON logs for programmatic access

**Fields Logged**:
- Timestamp
- Step name
- Status (ok/skipped/error)
- Duration (ms)
- Item fingerprint (SHA256 of source file)
- GPU usage flag
- Error messages (if failed)
- Extra metadata (model versions, configs)

---

### 3. File-Based Logs

**Location**: `logs/`

Active log files:
- `watchdog.log` - Watchdog daemon output (rotated)
- `watchdog_YYYYMMDD_HHMMSS/` - Per-run directories with full output
- `api_server_YYYYMMDD_HHMMSS.log` - API server logs (if activated)
- `scene_ingest/<video_name>/` - Per-video processing artifacts
- Individual step logs (e.g., `Comms Decrypt.log`, `Visual Intel.log`)

**Log Rotation**: Manual via `scripts/rotate_logs.py` (archives to `<GOODQ_DATA_ROOT>\archive\logs_YYYYMMDD/`)

---

## 🛡️ Error Resilience & Fallback Logic

### 1. Request Retry Logic

**Location**: `steps/common/retry.py`

Exponential backoff with jitter for HTTP requests:

```python
from steps.common.retry import request_with_retry

response = request_with_retry(
    "POST",
    "http://localhost:8000/v1/chat/completions",
    retries=3,
    base_delay=0.5,
    jitter=0.2,
    allowed=(200,),
    json=payload
)
```

**Behavior**:
- Attempt 1: Immediate
- Attempt 2: Wait 0.5-0.7s (base + jitter)
- Attempt 3: Wait 1.0-1.2s (exponential backoff)
- After 3 failures: Raise exception

**Used By**:
- LLM client (`lib/llm_client.py`)
- vLLM API calls
- Qdrant upserts
- External API integrations

---

### 2. Step-Level Graceful Degradation

**Strategy**: **Continue on failure, log and skip**

**Implementation** (in `cli/run_ingestion.py`):

```python
try:
    result = step_func(item, config)
    log_step_run(cfg, step_name, item, duration, "ok")
except Exception as exc:
    logger.error(f"Step {step_name} failed: {exc}")
    log_step_run(cfg, step_name, item, duration, "error", error=str(exc))
    # Continue to next step - DO NOT HALT PIPELINE
```

**Rationale**: A single failed OCR or emotion step should not abort 30-scene ingestion.

**Evidence**: Forensic audit showed 30 scenes processed with partial failures gracefully skipped.

---

### 3. GPU Fallback

**Location**: `steps/common/gpu_guard.py`, `common/gpu_manager.py`

Automatic CPU fallback if GPU is unavailable or OOM:

```python
from steps.common.gpu_guard import gpu_guard

@gpu_guard(fallback_device="cpu")
def my_model_step(inputs, device="cuda"):
    model = load_model().to(device)
    return model(inputs)
```

**Behavior**:
1. Attempt GPU execution
2. If `CUDA_OUT_OF_MEMORY` or device unavailable → retry on CPU
3. Log fallback event
4. Continue processing (slower, but uninterrupted)

**GPU Contention Handling**:
- RTX 4070 Ti SUPER shared by:
  - Vision models (BLIP, YOLO, DINO, CLIP)
  - Audio models (Whisper, Pyannote, Wav2Vec2)
  - vLLM (Llama-3.1-8B)
- Dynamic allocation via `torch.cuda.empty_cache()` after each step
- CUDA_VISIBLE_DEVICES per-step isolation (planned)

---

### 4. Config Healing

**Location**: `agents/config_healer.py`

Automatic config validation and repair:

```python
from agents.config_healer import validate_and_heal_config

config = validate_and_heal_config("config.yaml")
# Auto-creates missing directories
# Validates paths exist
# Checks model availability
# Reports issues without crashing
```

**Healing Actions**:
- Create missing data directories (`memory_db_path`, `kg_db_path`, `artifact_dir`)
- Validate HuggingFace token (warn if missing, don't fail)
- Check Qdrant connectivity (warn if down, allow offline mode)
- Verify model paths in envs (log if missing, use fallback)

**Invoked By**:
- `cli/run_ingestion.py` at startup
- `cli/watchdog.py` before each batch
- Config schema validator (`scripts/config_schema.py`)

---

### 5. Watchdog Recovery

**Location**: `cli/watchdog.py`

Unattended monitoring with automatic restart:

**Features**:
- Polls `smoke_inbox/` every 60 seconds
- Launches `run_ingestion.py` subprocess per video
- Timeout protection (kills if hung >2 hours)
- Exit code checking (logs failures, continues)
- Moves processed files to `<GOODQ_DATA_ROOT>\GoodQ_Data\processed/`

**Recovery Logic**:
```python
try:
    result = subprocess.run(
        ["python", "-m", "cli.run_ingestion", "--input-dir", inbox],
        timeout=7200,  # 2 hour max
        capture_output=True
    )
    if result.returncode != 0:
        logger.error(f"Ingestion failed with code {result.returncode}")
        # CONTINUE - don't stop watchdog
except subprocess.TimeoutExpired:
    logger.critical("Ingestion timed out - killing process")
    # CONTINUE - attempt next file
```

**Battle-Tested**: Ran for 8+ hours processing 6 videos (Dec 2025 audit)

---

## 📊 Observability

### Real-Time Monitoring

**1. System Status CLI**:
```bash
python -m cli.system_status
```
Shows:
- Qdrant health
- vLLM availability
- GPU utilization
- Database sizes
- Last ingestion timestamp

**2. Ingestion Monitor**:
```bash
python -m cli.monitor_ingestion
```
Live updates during processing:
- Current scene number
- Steps completed/failed
- Time remaining estimate
- GPU memory usage

**3. Process Manager**:
```bash
python -m scripts.utilities.process_manager status
```
Lists all GoodQ processes:
- Watchdog (PID, uptime)
- vLLM server (WSL2)
- Audio service (WSL2)
- Qdrant (Windows service)

---

### Log Analysis

**Analytics Engine**: `scripts/analytics_engine.py`

Query step performance:
```bash
python -m scripts.analytics_engine --step audio_transcribe --days 7
```

Output:
- Average duration
- Success rate
- Error histogram
- GPU utilization %

---

## 🚨 Known Failure Modes

### 1. WSL2 Bridge Timeout
**Symptom**: Audio transcription hangs indefinitely  
**Cause**: WSL2 process killed externally or script crash  
**Mitigation**: 60s timeout in `audio_wsl2_bridge.py` → fallback to legacy Whisper  
**Fix**: Monitor WSL2 audio service health (`systemctl --user status goodq-audio`)

### 2. Qdrant Connection Loss
**Symptom**: Upserts fail with connection refused  
**Cause**: Qdrant service stopped or port conflict  
**Mitigation**: Writes to local cache (`.qdrant_cache/`), batch upserts on reconnect  
**Fix**: Restart Qdrant (`net start qdrant_service`)

### 3. vLLM OOM on Long Contexts
**Symptom**: LLM chat fails with CUDA OOM after 15+ scenes  
**Cause**: Context grows to >8K tokens  
**Mitigation**: Truncate context to last 10 scenes before LLM call  
**Fix**: Increase vLLM `--max-num-seqs` or reduce `--max-model-len`

### 4. Scene Detection False Positives
**Symptom**: 300+ scenes detected in 22-min video (should be ~30)  
**Cause**: Aggressive threshold in `goodq_video_scene_detect`  
**Mitigation**: Pipeline continues, but slows down (1 scene = 60s processing)  
**Fix**: Tune `threshold` parameter in scene detection config

---

## 🔧 Configuration

### Enable Mission Logger

In `config.yaml`:
```yaml
logging:
  mission_style: true
  color_output: true
  level: INFO  # DEBUG for verbose
```

### Adjust Retry Policy

In `config.yaml`:
```yaml
resilience:
  http_retries: 3
  retry_delay: 0.5
  timeout_seconds: 60
```

### Configure Step Skipping

Skip expensive steps for debugging:
```yaml
steps:
  audio_emotion:
    enabled: false  # Skip emotion classification
  graph_builder:
    enabled: false  # Skip KG updates
```

---

## 📚 Related Documentation

- **Mission Components**: `lib/mission_components.py` (50+ component names)
- **Config Healing**: `docs/technical/CONFIG_HEALING.md`
- **Watchdog Setup**: `docs/guides/WATCHDOG_SETUP.md`
- **GPU Management**: `docs/technical/GPU_MANAGEMENT.md`
- **Analytics**: `docs/guides/ANALYTICS_USAGE.md` (to be created)

---

## ✅ Verification

**Test Resilience**:
```bash
# Kill vLLM mid-ingestion - should degrade gracefully
# Stop Qdrant - should cache locally
# Unplug GPU - should fallback to CPU
python -m tests.test_resilience
```

**Check Logs**:
```bash
# View last 100 step executions
python -m scripts.analytics_query --tail 100

# Count failures by step
python -m scripts.analytics_query --failures-by-step

# Show error messages
grep "error" logs/step_runs.jsonl | jq .error
```

---

## 🎖️ Mission-Critical Status

**This system has survived**:
- 8-hour unattended runs
- GPU memory exhaustion
- WSL2 process crashes
- Qdrant service restarts
- Network timeouts
- Malformed input videos

**Result**: **Zero pipeline halts. Zero data loss.**

*"The mission always continues."* — Q Branch
