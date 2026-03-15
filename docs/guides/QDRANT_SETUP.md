# Qdrant Setup Guide for GoodQ4All

## Overview

Qdrant is now integrated into GoodQ4All as a **Windows native service** (no Docker required). This provides metadata filtering capabilities for your multimodal search pipeline.

---

## 🎯 What You Get with Qdrant

### Advanced Query Capabilities

With Qdrant, you can now do:

```python
# Filter by video and time range
results = search_visual(
    query="birthday cake",
    filter={
        "video_id": "a6800419...",
        "timestamp": {"$gte": 300, "$lte": 600}  # 5-10 minutes
    }
)

# Filter by speaker and emotion
results = search_audio(
    query="excited talking",
    filter={
        "speaker": "SPEAKER_01",
        "emotion": "happy"
    }
)

# Filter by detected objects
results = search_scenes(
    query="outdoor activity",
    filter={
        "objects": {"$contains": "tree"},
        "scene_type": "outdoor"
    }
)
```

### Without Qdrant
- ❌ No metadata filtering during search
- ❌ Must retrieve ALL results, then filter in Python
- ❌ Slow on large datasets
- ❌ No multi-constraint queries

### With Qdrant
- ✅ Filter by video_id, scene_id, timestamp, speaker, emotion, objects
- ✅ Database-level filtering (fast!)
- ✅ Complex queries with multiple conditions
- ✅ Payload-based relevance boosting

---

## 📦 Installation Status

✅ **Qdrant binary installed:** `<project_root>\vendor\qdrant\qdrant.exe`  
✅ **Configuration created:** `<project_root>\vendor\qdrant\config.yaml`  
✅ **Data directory:** `<GOODQ_DATA_ROOT>\qdrant_storage`  
✅ **Config updated:** `configs/config.yaml` (qdrant.enabled = true)

---

## 🚀 Quick Start

### Option 1: Install as Windows Service (Recommended)

```batch
# Right-click and "Run as Administrator"
INSTALL_QDRANT_SERVICE.bat
```

This will:
- Install Qdrant as a Windows service named `GoodQ_Qdrant`
- Configure auto-start on system boot
- Set up logging to `<project_root>\logs\qdrant_*.log`

### Option 2: Run Manually (Foreground Testing Fallback)

```batch
# Start Qdrant in foreground
START_QDRANT.bat
```

Then in another terminal:
```batch
# Initialize collections
INIT_QDRANT.bat
```

Access dashboard: **http://127.0.0.1:6333/dashboard**

Then initialize collections:
```batch
INIT_QDRANT.bat
```

---

## 🛠️ Managing the Service

### Start/Stop Service

```batch
# Start
net start GoodQ_Qdrant

# Stop
net stop GoodQ_Qdrant

# Restart
net stop GoodQ_Qdrant && net start GoodQ_Qdrant
```

### Check Status

```batch
# Windows Services GUI
services.msc
# Look for "GoodQ4All - Qdrant Vector Database"
```

Or visit: **http://127.0.0.1:6333/health**

### Uninstall Service

```batch
# Right-click and "Run as Administrator"
UNINSTALL_QDRANT_SERVICE.bat
```

---

## 📊 Collections

GoodQ4All creates 4 collections:

| Collection | Dimension | Purpose |
|-----------|-----------|---------|
| `goodq_clip` | 512 | CLIP visual scene embeddings |
| `goodq_dino` | 768 | DINOv2 visual scene embeddings |
| `goodq_text` | 384 | Text embeddings (transcripts, captions) |
| `goodq_audio` | 512 | CLAP audio embeddings |

These are automatically created when you run `INIT_QDRANT.bat`.

---

## 🔧 Configuration

### Qdrant Config (`vendor/qdrant/config.yaml`)

```yaml
storage:
  storage_path: <GOODQ_DATA_ROOT>/qdrant_storage

service:
  http_port: 6333      # REST API
  grpc_port: 6334      # gRPC API
  host: 127.0.0.1      # Localhost only (secure)
  enable_cors: true    # For web dashboard

optimizer:
  memmap_threshold: 50000
  indexing_threshold: 20000
  flush_interval_sec: 5

storage:
  on_disk_payload: true  # Efficient for large datasets

log_level: INFO
```

### GoodQ Config (`configs/config.yaml`)

```yaml
qdrant:
  enabled: true  # ← Enables Qdrant integration
  host: http://127.0.0.1:6333
  collections:
    clip: goodq_clip
    dino: goodq_dino
    text: goodq_text
    audio: goodq_audio
  embedding_dims:
    clip: 512
    dino: 768
    text: 384
    audio: 512
```

---

## 🧪 Testing Qdrant

### 1. Verify Service is Running

```powershell
# Test health endpoint
Invoke-RestMethod -Uri http://127.0.0.1:6333/health

# Expected output:
# status
# ------
# ok
```

### 2. List Collections

```powershell
$response = Invoke-RestMethod -Uri http://127.0.0.1:6333/collections
$response.result.collections
```

### 3. Check Collection Details

```powershell
Invoke-RestMethod -Uri http://localhost:6333/collections/goodq_clip
```

### 4. Run Full System Test

```batch
test_system.bat
```

Now the Qdrant test should **PASS** instead of fail.

---

## 📈 Performance Tuning

### For Your RTX 4070 Ti SUPER (16GB VRAM)

Current settings are optimized for your hardware:

- **memmap_threshold: 50000** - Keeps up to 50K vectors in memory
- **indexing_threshold: 20000** - Triggers indexing at 20K vectors
- **on_disk_payload: true** - Stores payloads on disk to save RAM

### If Processing Large Archives (100+ videos):

Increase thresholds in `vendor/qdrant/config.yaml`:

```yaml
optimizer:
  memmap_threshold: 100000  # More in-memory vectors
  indexing_threshold: 50000
```

---

## 🔍 Web Dashboard

Access the Qdrant web dashboard at:

**http://localhost:6333/dashboard**

Features:
- Browse collections
- View vector statistics
- Test queries
- Monitor performance

---

## 📁 File Locations

```
<project_root>\
├── vendor\
│   ├── qdrant\
│   │   ├── qdrant.exe          # Main executable
│   │   └── config.yaml         # Qdrant configuration
│   └── nssm.exe                # Service manager (if installed)
├── logs\
│   ├── qdrant_stdout.log       # Service output (if using service)
│   └── qdrant_stderr.log       # Service errors (if using service)
├── START_QDRANT.bat            # Manual start script
├── INSTALL_QDRANT_SERVICE.bat  # Service installer
├── UNINSTALL_QDRANT_SERVICE.bat # Service uninstaller
└── INIT_QDRANT.bat             # Collection initializer

<GOODQ_DATA_ROOT>\
└── qdrant_storage\             # Database files
    ├── collections\
    ├── wal\
    └── snapshots\
```

---

## 🐛 Troubleshooting

### Port Already in Use

```powershell
# Find what's using port 6333
netstat -ano | findstr :6333

# Kill the process (replace PID)
taskkill /PID <PID> /F
```

### Service Won't Start

1. Check logs: `<project_root>\logs\qdrant_stderr.log`
2. Re-run `INSTALL_QDRANT_SERVICE.bat` as Administrator to repair the Windows service
3. Check config syntax: `vendor\qdrant\config.yaml`
4. Use `START_QDRANT.bat` only as a foreground diagnostic fallback

### Collections Not Created

1. Make sure Qdrant is running
2. Run `INIT_QDRANT.bat` again
3. Check connection: `http://localhost:6333/health`

### Ingestion Not Using Qdrant

1. Verify `configs/config.yaml` has `qdrant.enabled: true`
2. Check Qdrant is running: `net start GoodQ_Qdrant`
3. Test connection from Python:
   ```python
   import requests
   requests.get('http://localhost:6333/health')
   ```

---

## 🎓 Next Steps

1. **Start Qdrant:**
   - Preferred: `INSTALL_QDRANT_SERVICE.bat` (as Admin)
   - Testing fallback: `START_QDRANT.bat`

2. **Initialize Collections:**
   ```batch
   INIT_QDRANT.bat
   ```

3. **Run Test Ingestion:**
   ```batch
   test_system.bat
   ```

4. **Process Real Videos:**
   ```batch
   LAUNCH_GOODQ_v2.bat
   ```
   Drop videos into `<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox\`

5. **Test Multimodal Search:**
   ```batch
   conda activate goodq_core
   python cli/retrieve.py "find birthday celebrations"
   ```

---

## 📚 Additional Resources

- **Qdrant Documentation:** https://qdrant.tech/documentation/
- **API Reference:** http://localhost:6333/docs (when running)
- **GoodQ Search Guide:** `docs/guides/SEARCH_GUIDE.md` (coming soon)

---

**Installation Date:** 2025-12-11  
**Qdrant Version:** 1.7.4  
**Status:** ✅ Ready for Production
