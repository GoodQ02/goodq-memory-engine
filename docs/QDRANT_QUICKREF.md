# Qdrant Quick Reference

## 🚀 Start Qdrant

### Manual (Testing)
```batch
START_QDRANT.bat
```
Keep window open. Dashboard: http://localhost:6333/dashboard

### Windows Service (Production)
```batch
# Install (run as Admin)
INSTALL_QDRANT_SERVICE.bat

# Manage
net start GoodQ_Qdrant
net stop GoodQ_Qdrant
net restart GoodQ_Qdrant
```

---

## 🔧 Setup (First Time)

```batch
# 1. Start Qdrant (pick one method above)
START_QDRANT.bat

# 2. Initialize collections
INIT_QDRANT.bat

# 3. Verify health
CHECK_QDRANT.bat
```

---

## 🧪 Testing

```batch
# Full system test (should now be 6/6 passing)
test_system.bat

# Qdrant health only
CHECK_QDRANT.bat

# Dashboard
http://localhost:6333/dashboard
```

---

## 📊 Collections

| Name | Dim | Purpose |
|------|-----|---------|
| goodq_clip | 512 | Visual scenes (CLIP) |
| goodq_dino | 768 | Visual scenes (DINO) |
| goodq_text | 384 | Transcripts/captions |
| goodq_audio | 512 | Audio embeddings (CLAP) |

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
Binary:  L:\goodq4all\vendor\qdrant\qdrant.exe
Config:  L:\goodq4all\vendor\qdrant\config.yaml
Data:    L:\_DATA\qdrant_storage
Logs:    L:\goodq4all\logs\qdrant_*.log (if service)
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
Get-Content L:\goodq4all\logs\qdrant_stderr.log -Tail 50

# Or run manual to see output
START_QDRANT.bat
```

### Reset Everything
```batch
# Stop service
net stop GoodQ_Qdrant

# Delete data (WARNING: loses all vectors!)
rmdir /s /q L:\_DATA\qdrant_storage

# Reinitialize
START_QDRANT.bat
INIT_QDRANT.bat
```

---

## 🔗 URLs

- **Health Check:** http://localhost:6333/health
- **Dashboard:** http://localhost:6333/dashboard
- **API Docs:** http://localhost:6333/docs
- **Collections:** http://localhost:6333/collections

---

## 📚 Full Docs

See: `docs/guides/QDRANT_SETUP.md`
