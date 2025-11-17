# GoodQ4All Quick Start Guide
**Last Updated:** October 10, 2025

> Canonical quickstart: This is the primary, up-to-date Quick Start for GoodQ4All. Older quickstart documents (for example `docs/QUICK_START.md` and `docs/QUICK_START_GUIDE.md`) should be treated as secondary and may be out of date. Agents and users should start here.

## 🚀 Quick Launch

### First Time Setup
```batch
cd L:\goodq4all
RUN_HEALTH_CHECK.bat
```
Wait for all checks to pass (✓ marks).

### Start Processing
```batch
cd L:\goodq4all
LAUNCH_GOODQ.bat
```

This opens **3 windows**:
1. **Launcher** - Shows startup progress
2. **API Server** - FastAPI running on http://localhost:8000
3. **Command Center** - Real-time dashboard

### Drop Files for Processing
1. Copy video/audio/image files into: `L:\goodq4all\import_inbox\`
2. Start the watchdog:
```batch
cd L:\goodq4all
START_WATCHDOG.bat
```
3. Monitor progress:
```batch
cd L:\goodq4all  
CHECK_WATCHDOG.bat
```

### Stop Everything
```batch
cd L:\goodq4all
STOP_GOODQ.bat
```

## 📁 Important Locations

| What | Where |
|------|-------|
| Drop files here | `L:\goodq4all\import_inbox\` |
| Processing logs | `L:\_DATA\GoodQ_Data\logs\` |
| Memory database | `L:\_DATA\GoodQ_Data\databases\memory.db` |
| Vector indices | `L:\_DATA\GoodQ_Data\faiss_indices\` |
| Knowledge graph | `L:\_DATA\GoodQ_Data\graph\` |
| API docs | http://localhost:8000/docs |

## 🔧 Troubleshooting

### Check System Health
```batch
RUN_HEALTH_CHECK.bat
```

### Check Watchdog Status
```batch
CHECK_WATCHDOG.bat
```

### View Processing Logs
```powershell
Get-Content L:\_DATA\GoodQ_Data\logs\step_runs.jsonl -Tail 50
```

### View Watchdog Logs
```powershell
Get-Content L:\_DATA\GoodQ_Data\logs\watchdog.log -Tail 50
```

## 📊 Understanding Output

### Command Center Shows:
- **GPU Status** - Current memory usage
- **DB / FAISS** - Embeddings and indices count
- **Drift** - DB/FAISS sync status
- **Hot Cache** - Model cache sizes
- **Recent Steps** - Last 15 processing steps
- **Video Summary** - Current video being processed

### Watchdog Status Shows:
- **Files in inbox** - Ready to process
- **Files processing** - Currently being worked on
- **Files processed** - Completed
- **Files failed** - Errors (check logs)
- **Recent Activity** - Last 10 log entries

## 🎯 Supported File Types

### Video
- .mp4, .avi, .mov, .mkv, .webm

### Audio  
- .wav, .mp3, .flac, .ogg, .m4a

### Images
- .jpg, .jpeg, .png, .bmp, .tiff

### Documents
- .pdf, .txt

## 🔥 Performance Tips

1. **GPU Required** - This project needs NVIDIA GPU with CUDA
2. **One at a time** - Process one large video at a time for best results
3. **File naming** - Use descriptive names (becomes video ID)
4. **Patience** - A 1-hour video takes ~30-60 minutes to fully process
5. **Monitor GPU** - Command center shows GPU memory usage

## 📈 What Gets Extracted

### From Video
- Scene detection
- Frame keyframes
- Object detection & tracking
- Face embeddings
- Image captions
- OCR text
- Visual embeddings (CLIP, DINOv2)

### From Audio
- Speech transcription
- Speaker diarization
- Music detection
- Sound events
- Emotional tone
- Audio embeddings

### Multimodal
- Scene descriptions
- Temporal relationships
- Entity recognition
- Sentiment analysis
- Knowledge graph connections
- Contextual tags

## 🌐 API Usage

Once running, visit: http://localhost:8000/docs

Example queries:
```python
import requests

# Search by text
response = requests.post(
    "http://localhost:8000/retrieve",
    json={"query": "birthday party", "modality": "text", "top_k": 5}
)

# Get video summary
response = requests.get(
    "http://localhost:8000/video/my_video_name"
)
```

## 📝 Best Practices

### Before Processing
- [ ] Check disk space (need ~50GB per hour of video)
- [ ] Run health check
- [ ] Verify GPU is available
- [ ] Close other GPU-heavy apps

### During Processing
- [ ] Don't add too many files at once
- [ ] Monitor command center for errors
- [ ] Check watchdog status periodically
- [ ] Let large files finish before adding more

### After Processing
- [ ] Move originals out of import_inbox
- [ ] Check processed folder for results
- [ ] Query via API to test
- [ ] Archive old logs if needed

## 🆘 Common Issues

### "Port 8000 already in use"
```batch
STOP_GOODQ.bat
# Wait 5 seconds
LAUNCH_GOODQ.bat
```

### "CUDA not available"
```batch
cd L:\goodq4all\scripts
powershell -ExecutionPolicy Bypass -File enable_cuda.ps1
```

### "Watchdog not processing files"
1. Check watchdog log for errors
2. Verify file is supported type
3. Ensure enough disk space
4. Restart watchdog

### "Command center shows errors"
View recent logs:
```powershell
Get-Content L:\_DATA\GoodQ_Data\logs\step_runs.jsonl -Tail 20 | ConvertFrom-Json
```

## 📚 More Info

- Full documentation: `L:\goodq4all\docs\`
- Project structure: `L:\goodq4all\docs\PROJECT_ORGANIZATION_COMPLETE.md`
- Model versions: `L:\goodq4all\docs\MODEL_VERSIONS.md`
- Architecture: `L:\goodq4all\docs\ARCHITECTURE.md`

---

**Need Help?** Check the logs first, they're very detailed!

**Ready to scale?** This is just the beginning - the pipeline can handle thousands of hours once tuned.

**Happy Processing! 🎬**
