# GoodQ User Guide

## 🎯 Welcome to GoodQ!

This guide will help you get started with GoodQ, your desktop-native AI companion for multimodal content processing and memory management.

---

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Understanding the System](#understanding-the-system)
3. [Running Ingestion](#running-ingestion)
4. [Monitoring & Dashboards](#monitoring--dashboards)
5. [Querying Memory](#querying-memory)
6. [Troubleshooting](#troubleshooting)
7. [Advanced Usage](#advanced-usage)
8. [Best Practices](#best-practices)

---

## 🚀 Quick Start

### Prerequisites Check

Before starting, verify your system meets requirements:

```powershell
# Check system readiness
cd L:\goodq4all
python scripts\system_readiness_check.py

# Check model cache
python scripts\cache_readiness_check.py
```

**Expected:** Both checks should return exit code 0 with all green checkmarks.

### Your First Ingestion

1. **Place a video in the inbox:**
   ```powershell
   Copy-Item "C:\Users\...\your_video.mp4" L:\goodq4all\smoke_inbox\
   ```

2. **Run lite ingestion (quick test):**
   ```powershell
   pwsh scripts\ingest_videos_lite.ps1 -InputDir smoke_inbox -MaxVideos 1 -MaxScenes 2 -VerboseSteps
   ```

3. **Check results:**
   ```powershell
   # View logs
   Get-Content L:\GoodQ_Data\logs\step_runs.jsonl -Tail 20

   # Check database
   sqlite3 L:\GoodQ_Data\data\memory_db\memory.db "SELECT COUNT(*) FROM scenes;"
   ```

**Expected Duration:** 2-3 minutes for a short video (2 scenes).

---

## 🧠 Understanding the System

### What Happens During Ingestion?

```
Your Video
    │
    ├─→ Scene Detection (splits video into logical segments)
    │
    ├─→ Image Analysis
    │   ├─ Extract text (OCR)
    │   ├─ Describe scenes (AI captions)
    │   ├─ Find objects (YOLO detection)
    │   ├─ Identify faces
    │   └─ Generate embeddings (searchable vectors)
    │
    └─→ Audio Analysis
        ├─ Who spoke when (diarization)
        ├─ What was said (transcription)
        ├─ How they felt (emotion detection)
        ├─ What happened (music events, time references)
        └─ Generate embeddings (searchable audio)
            │
            └─→ Memory Storage
                ├─ SQLite (structured data)
                └─ FAISS (vector search)
```

### Key Concepts

**Scenes:** Logical segments of video (shot boundaries, camera cuts)

**Embeddings:** Mathematical representations that enable similarity search
- Text embeddings: Find similar transcripts
- Image embeddings: Find visually similar scenes
- Audio embeddings: Find similar sounds/speech

**Deduplication:** The system remembers what it has processed and skips redundant work on second runs (76% faster!)

---

## 🎬 Running Ingestion

### Lite Ingestion (Testing & Development)

**Purpose:** Quick tests with limited scope

```powershell
# Basic usage
pwsh scripts\ingest_videos_lite.ps1 -InputDir smoke_inbox

# With limits (faster testing)
pwsh scripts\ingest_videos_lite.ps1 `
    -InputDir import_inbox `
    -MaxVideos 3 `
    -MaxScenes 5 `
    -VerboseSteps

# Custom workspace
pwsh scripts\ingest_videos_lite.ps1 `
    -InputDir smoke_inbox `
    -Workspace logs\my_test `
    -Output logs\my_test\results.json
```

**Parameters:**
- `-InputDir`: Source folder for videos (default: `smoke_inbox`)
- `-MaxVideos`: Limit number of videos (default: 1)
- `-MaxScenes`: Limit scenes per video (default: 12)
- `-VerboseSteps`: Show detailed step output
- `-Workspace`: Custom log directory
- `-NoSync`: Skip `.env.local` sync

### Full Ingestion (Production)

**Purpose:** Process complete videos without limits

```powershell
# Using Python CLI directly
conda activate goodq_zenml
python cli\run_ingestion.py `
    --input-dir "L:\Videos\to_process" `
    --workspace "logs\full_run" `
    --verbose

# Or via PowerShell wrapper
pwsh scripts\ingest_videos.ps1 -InputDir "L:\Videos\to_process"
```

### Mission Launch (Full Stack)

**Purpose:** Complete automation with health checks and monitoring

```powershell
# Dry run (validate setup)
pwsh scripts\mission_launch.ps1 -Mode dryrun -EnvPrefix goodq

# Full pipeline with dashboard
pwsh scripts\mission_launch.ps1 -Mode pipeline -OpenDashboard

# Custom configuration
pwsh scripts\mission_launch.ps1 `
    -Mode pipeline `
    -InputDir "L:\Videos\archive" `
    -EnvPrefix goodq `
    -OpenDashboard
```

**Modes:**
- `dryrun`: Validate environments and cache
- `pipeline`: Run full ingestion
- `health`: Health check only
- `dashboard`: Open Command Center only

---

## 📊 Monitoring & Dashboards

### Command Center Dashboard

**Launch:**
```powershell
pwsh scripts\command_center.ps1
```

**Features:**
- Real-time GPU stats (temp, usage, memory)
- System metrics (CPU, RAM, disk)
- Pipeline status (current video/scene)
- Memory statistics (scene count, vector counts)
- Live log tail

**Keyboard Shortcuts:**
- `R`: Refresh display
- `Q`: Quit
- `L`: Show last 50 log entries
- `D`: Detailed database stats

### Log Analysis

**View recent steps:**
```powershell
Get-Content L:\GoodQ_Data\logs\step_runs.jsonl -Tail 50 | `
    ForEach-Object { $_ | ConvertFrom-Json } | `
    Format-Table ts, step, duration_ms, status -AutoSize
```

**Find errors:**
```powershell
Get-Content L:\GoodQ_Data\logs\step_runs.jsonl | `
    Select-String '"status":"error"' | `
    ConvertFrom-Json | `
    Format-List
```

**Performance analysis:**
```powershell
# Average duration per step
Get-Content L:\GoodQ_Data\logs\step_runs.jsonl -Tail 1000 | `
    ForEach-Object { $_ | ConvertFrom-Json } | `
    Group-Object step | `
    ForEach-Object { 
        [PSCustomObject]@{
            Step = $_.Name
            AvgDuration = ($_.Group | Measure-Object duration_ms -Average).Average
            Count = $_.Count
        }
    } | Sort-Object AvgDuration -Descending
```

### Health Checks

**Full system diagnostic:**
```powershell
pwsh scripts\mission_health_check.ps1 -EnvPrefix goodq -FixMissingCaches
```

**Quick environment check:**
```powershell
pwsh scripts\audit_env.ps1
```

**Index reconciliation:**
```powershell
pwsh scripts\reconcile_indices.ps1
```

---

## 🔍 Querying Memory

### SQLite Queries

**Connect to database:**
```powershell
sqlite3 L:\GoodQ_Data\data\memory_db\memory.db
```

**Common queries:**
```sql
-- Count scenes
SELECT COUNT(*) FROM scenes;

-- Recent videos
SELECT video_hash, COUNT(*) as scene_count, MIN(created_at) as first_seen
FROM scenes
GROUP BY video_hash
ORDER BY first_seen DESC
LIMIT 10;

-- Scenes with transcripts
SELECT s.scene_id, s.video_hash, s.start_time, s.end_time
FROM scenes s
WHERE EXISTS (
    SELECT 1 FROM assets a 
    WHERE a.scene_id = s.scene_id 
    AND a.asset_type = 'audio'
);

-- Scene bundle status
SELECT status, COUNT(*) as count
FROM scene_bundles
GROUP BY status;
```

### FAISS Vector Search

**Python example:**
```python
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# Load index
index = faiss.read_index("L:/GoodQ_Data/data/memory_db/faiss_text.index")

# Load model for query encoding
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

# Search
query = "dog playing in the park"
query_vector = model.encode([query])
distances, indices = index.search(query_vector.astype('float32'), k=10)

print(f"Found {len(indices[0])} similar scenes:")
for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
    print(f"{i+1}. Index {idx}, Distance: {dist:.4f}")
```

### API Queries (if API enabled)

**Start API server:**
```powershell
pwsh scripts\start_api.ps1
```

**Query endpoints:**
```powershell
# Search by text
Invoke-RestMethod -Uri "http://localhost:8000/search/text" `
    -Method POST `
    -Body (@{ query = "sunset beach" } | ConvertTo-Json) `
    -ContentType "application/json"

# Get scene details
Invoke-RestMethod -Uri "http://localhost:8000/scenes/abc123..."
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. "Environment not found" error

**Symptom:** `EnvironmentLocationNotFound: Not a conda environment`

**Solution:**
```powershell
# Recreate the missing environment
pwsh scripts\prepare_step_envs.ps1 `
    -EnvPrefix goodq `
    -Steps <missing_step> `
    -LinkProject
```

#### 2. CUDA out of memory

**Symptom:** `RuntimeError: CUDA out of memory`

**Solutions:**
```powershell
# A) Reduce batch sizes (edit step code)
# B) Process fewer scenes at once
pwsh scripts\ingest_videos_lite.ps1 -MaxScenes 1

# C) Clear GPU cache between runs
python -c "import torch; torch.cuda.empty_cache()"
```

#### 3. PyAnnote authentication error

**Symptom:** `401 Unauthorized` during diarization

**Solution:**
```powershell
# Set your HuggingFace token
$env:PYANNOTE_TOKEN = "hf_your_token_here"
# OR
$env:PYANNOTE_AUDIO_AUTH = "hf_your_token_here"

# Persist it
pwsh scripts\set_env_vars.ps1 -Vars @{PYANNOTE_TOKEN="hf_..."} -Persist
```

#### 4. ffmpeg not found

**Symptom:** `FileNotFoundError: ffmpeg`

**Solution:**
```powershell
# Verify path
Get-Command ffmpeg

# If not found, update config
# Edit L:\goodq4all\configs\config_open.yaml
# tools:
#   ffmpeg_exe: "L:\\Tools\\ffmpeg\\bin\\ffmpeg.exe"
```

#### 5. Slow performance on reruns

**Symptom:** Second ingestion still takes long time

**Check deduplication:**
```powershell
# Verify hashes are being computed
Get-Content L:\GoodQ_Data\logs\step_runs.jsonl -Tail 100 | `
    Select-String "video_hash"

# Check for skipped entries
Get-Content L:\GoodQ_Data\logs\step_runs.jsonl -Tail 100 | `
    Select-String '"status":"skipped"'
```

### Getting Help

**Collect diagnostics:**
```powershell
# Generate full diagnostic bundle
pwsh scripts\run_full_dry_run.ps1
# Creates export in logs/run_exports/<timestamp>
```

**Check documentation:**
- [Architecture](../architecture/SYSTEM_ARCHITECTURE.md)
- [Project History](../history/PROJECT_HISTORY.md)
- [API Reference](../reference/API.md)

---

## 🎓 Advanced Usage

### Custom Scene Detection Thresholds

**Edit `configs/config_open.yaml`:**
```yaml
video:
  scene_threshold: 0.3  # Lower = more scenes (0.1-0.5)
  
  # Per-source overrides
  scene_threshold_overrides:
    by_extension:
      ".mp4": 0.25  # More sensitive for MP4
      ".mkv": 0.35  # Less sensitive for MKV
    by_path_substring:
      "GoPro": 0.4      # Action cameras
      "ScreenRecord": 0.2  # Screen recordings
```

### Custom Model Selection

**Audio emotion models (in step code):**
```python
# Edit goodq4all/steps/audio_emotion/step.py
candidates = [
    "superb/hubert-large-superb-er",  # Default
    "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition",  # Alternative
    "your-custom/model",  # Add your own!
]
```

### Batch Processing

**Process entire directory:**
```powershell
Get-ChildItem "L:\Videos\archive" -Filter *.mp4 | ForEach-Object {
    Write-Host "Processing $($_.Name)..." -ForegroundColor Cyan
    
    Copy-Item $_.FullName L:\goodq4all\import_inbox\
    
    pwsh scripts\ingest_videos_lite.ps1 `
        -InputDir import_inbox `
        -VerboseSteps
    
    # Move processed video
    Move-Item $_.FullName "L:\Videos\processed\"
    
    # Clean inbox
    Remove-Item L:\goodq4all\import_inbox\* -Force
}
```

### Export & Backup

**Create exportable bundle:**
```powershell
pwsh scripts\export_run_profile.ps1 -RunId "abc123..." -OutputDir "exports"
```

**Backup databases:**
```powershell
$backupDir = "G:\Backups\GoodQ\$(Get-Date -Format 'yyyy-MM-dd')"
New-Item -ItemType Directory -Path $backupDir -Force

Copy-Item L:\GoodQ_Data\data\memory_db\*.db $backupDir\
Copy-Item L:\GoodQ_Data\data\memory_db\*.index $backupDir\
Copy-Item L:\GoodQ_Data\data\memory_db\*.sqlite $backupDir\

Write-Host "Backup complete: $backupDir" -ForegroundColor Green
```

---

## ✅ Best Practices

### 1. Regular Health Checks

**Weekly routine:**
```powershell
# Monday morning health check
pwsh scripts\mission_health_check.ps1 -EnvPrefix goodq -FixMissingCaches

# View summary
Get-Content L:\GoodQ_Data\logs\health_check.log -Tail 50
```

### 2. Log Rotation

**Keep logs manageable:**
```powershell
# Keep last 30 days
Get-ChildItem L:\GoodQ_Data\logs\*.jsonl | `
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | `
    Remove-Item -Confirm
```

### 3. Index Maintenance

**Monthly index health:**
```powershell
# Check index integrity
pwsh scripts\reconcile_indices.ps1

# Rebuild if needed (rarely necessary)
pwsh scripts\reindex_faiss.ps1
```

### 4. Environment Updates

**Quarterly maintenance:**
```powershell
# Update pip in each environment
conda env list | Select-String "goodq" | ForEach-Object {
    $envName = ($_ -split '\s+')[0]
    conda run -n $envName python -m pip install --upgrade pip
}

# Reinstall from pinned requirements (safer)
pwsh scripts\prepare_step_envs.ps1 `
    -EnvPrefix goodq `
    -ForceReinstall `
    -LinkProject
```

### 5. Backup Strategy

**3-2-1 Rule:**
- **3** copies of data
- **2** different media types
- **1** offsite backup

```powershell
# Local backup (L:/ → G:/ NAS)
Copy-Item L:\GoodQ_Data\data\memory_db\* G:\Backups\GoodQ\current\

# External backup (monthly)
Copy-Item G:\Backups\GoodQ\current\* E:\GoodQ_Backup\$(Get-Date -Format 'yyyy-MM')\
```

---

## 🎯 Quick Reference

### Essential Commands

| Task | Command |
|------|---------|
| Health Check | `pwsh scripts\mission_health_check.ps1 -EnvPrefix goodq` |
| Lite Ingest | `pwsh scripts\ingest_videos_lite.ps1 -InputDir smoke_inbox -VerboseSteps` |
| Dashboard | `pwsh scripts\command_center.ps1` |
| View Logs | `Get-Content L:\GoodQ_Data\logs\step_runs.jsonl -Tail 50` |
| DB Query | `sqlite3 L:\GoodQ_Data\data\memory_db\memory.db` |
| Reconcile | `pwsh scripts\reconcile_indices.ps1` |
| Backup | `Copy-Item L:\GoodQ_Data\data\memory_db\* G:\Backups\` |

### File Locations

| Item | Path |
|------|------|
| Config | `L:\goodq4all\configs\config_open.yaml` |
| Logs | `L:\GoodQ_Data\logs\` |
| Database | `L:\GoodQ_Data\data\memory_db\memory.db` |
| FAISS | `L:\GoodQ_Data\data\memory_db\*.index` |
| Models | `L:\models\` |
| Scripts | `L:\goodq4all\scripts\` |

### Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `HF_HOME` | HuggingFace cache | `L:/models` |
| `TORCH_HOME` | PyTorch cache | `L:/models` |
| `PYANNOTE_TOKEN` | PyAnnote auth | `hf_...` |
| `HF_TOKEN` | HuggingFace auth | `hf_...` |
| `OPENAI_API_KEY` | OpenAI (optional) | `sk-...` |

---

## 📚 Further Reading

- **[Architecture](../architecture/SYSTEM_ARCHITECTURE.md)** - Technical deep dive
- **[Diagrams](../diagrams/PIPELINE_FLOW.md)** - Visual reference
- **[History](../history/PROJECT_HISTORY.md)** - Project evolution
- **[API Reference](../reference/API.md)** - Developer documentation

---

*User Guide - Version 1.2.0 - October 6, 2025*

**Need help?** Check the troubleshooting section or review the project history for context on common issues and their solutions.
