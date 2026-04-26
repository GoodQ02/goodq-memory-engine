<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-20 -->

# Qdrant Quick Reference

## 🚀 Start Qdrant

### Manual (Testing)
```batch
scripts\qdrant\START_QDRANT.bat
```
Keep window open. Dashboard: http://localhost:6333/dashboard

### Windows Service (Production)
```batch
# Install (run as Admin)
scripts\qdrant\INSTALL_QDRANT_SERVICE.bat

# Manage
net start GoodQ_Qdrant
net stop GoodQ_Qdrant
net stop GoodQ_Qdrant
net start GoodQ_Qdrant
```

---

## 🔧 Setup (First Time)

```batch
# 1. Start Qdrant (pick one method above)
scripts\qdrant\START_QDRANT.bat

# 2. Initialize collections
scripts\qdrant\INIT_QDRANT.bat

# 3. Verify health
scripts\qdrant\CHECK_QDRANT.bat
```

---

## 🧪 Testing

```powershell
# Runtime health / service verification
conda run -n goodq_core python scripts\bootstrap_verify.py

# Qdrant health only
scripts\qdrant\CHECK_QDRANT.bat

# Dashboard
http://localhost:6333/dashboard
```

---

## 📊 Collections

| Name | Dim | Purpose |
|------|-----|---------|
| goodq_clip_epoch_2025_12_22 | 512 | Visual scenes (CLIP) |
| goodq_dino_epoch_2025_12_22 | 768 | Visual scenes (DINO) |
| goodq_text_epoch_2025_12_22 | 384 | Transcripts/captions |
| goodq_audio_epoch_2025_12_22 | 512 | Audio embeddings (CLAP) |

Collection names are configured in `configs/config.yaml`; trust config if the active epoch changes.

---

## 🔍 Example Queries (Python)

### Search with Video Filter
```python
from retrieval.multimodal_search import MultimodalSearchEngine

engine = MultimodalSearchEngine(config)
results = engine.search_visual(
    query="birthday celebration",
    filter={"video_id": "a6800419..."}
)
```

### Search with Time Range
```python
results = engine.search_scenes(
    query="outdoor activity",
    filter={"timestamp": {"$gte": 300, "$lte": 600}}
)
```

### Search with Speaker
```python
results = engine.search_audio(
    query="excited talking",
    filter={"speaker": "SPEAKER_01"}
)
```

---

## 📁 Locations

```
Binary:  <project_root>\vendor\qdrant\qdrant.exe
Config:  <project_root>\vendor\qdrant\config.yaml
Data:    <GOODQ_DATA_ROOT>\qdrant_storage
Logs:    <project_root>\logs\qdrant_*.log (if service)
```

---

## 🐛 Troubleshooting

### Won't Start
```batch
# Check port
netstat -ano | findstr :6333

# Kill process using port
taskkill /PID <PID> /F
```

### Check Logs
```powershell
# Service logs
Get-Content <project_root>\logs\qdrant_stderr.log -Tail 50

# Or run manual to see output
scripts\qdrant\START_QDRANT.bat
```

### Reset Everything
```batch
# Stop service
net stop GoodQ_Qdrant

# Delete data (WARNING: loses all vectors!)
rmdir /s /q <GOODQ_DATA_ROOT>\qdrant_storage

# Reinitialize
scripts\qdrant\START_QDRANT.bat
scripts\qdrant\INIT_QDRANT.bat
```

---

## 🔗 URLs

- **Service Check:** http://127.0.0.1:6333/
- **Dashboard:** http://localhost:6333/dashboard
- **API Docs:** http://localhost:6333/docs
- **Collections:** http://127.0.0.1:6333/collections

---

## 📚 Full Docs

See: `docs/guides/QDRANT_SETUP.md`
