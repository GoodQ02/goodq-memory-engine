# 🚀 GoodQ4All - Quick Start Card

## Launch System (30 seconds)

```batch
1. Double-click: LAUNCH_GOODQ.bat
2. Press: 1 (Launch Complete System)
3. Wait: 10 seconds
4. Check: Browser opens to http://localhost:3000
```

---

## Verify It's Working (60 seconds)

✅ **Two command windows open:**
- "GoodQ API Server" → Shows HTTP requests
- "GoodQ Watchdog" → Shows processing logs

✅ **Watchdog window shows:**
```
[INFO] New file detected: 01. 1987 - 1988.mp4
[INFO] Queued for processing: 01. 1987 - 1988.mp4
[INFO] Processing video: 01. 1987 - 1988.mp4
```

✅ **UI shows:**
- System Status: Active (green)
- Progress bar appears at top
- Command Center logs streaming
- Pipeline Engines lighting up

---

## Monitor Progress (ongoing)

### **Command Center Tab**
Live logs, updates every 2s:
```
[TIMER] Step: video_scene_detect
[INFO] Scene 12/45 detected
[GPU] Using CUDA device 0
```

### **Pipeline Engines Tab**
Color-coded engine status:
- 🟢 Green = Active (currently processing)
- ⚪ Gray = Idle (waiting)

### **Progress Bar** (top of screen)
```
Processing: 01. 1987 - 1988.mp4 | Step: Audio Transcription | 45%
```

### **Chat Tab**
Ask questions:
```
You: "What step are we on?"
Q: "Currently running audio transcription (step 4/12)"

You: "How many scenes detected?"
Q: "Found 127 scenes, 45 processed so far"
```

---

## Expected Timeline

| Time | What's Happening |
|------|------------------|
| **0-5min** | Scene Detection starting |
| **5-30min** | Scene Detection (GPU active) |
| **30min-2hr** | Audio Transcription (per scene) |
| **2-3hr** | Audio Diarization + Face Recognition |
| **3-4hr** | Emotion + Embeddings (CLIP/DINO) |
| **4-5hr** | Knowledge Graph Building |

**Total: ~2.5-5 hours for 4.5-hour video**

---

## GPU Activity Check

### **In UI:**
- Go to **Pipeline Engines** tab
- Active engines show 🟢 green
- Recent activity in Command Center logs

### **In System:**
```powershell
# Open PowerShell and run:
nvidia-smi

# You should see:
# python.exe using 8-12GB VRAM
```

---

## Stop System

### **Method 1: Launcher Menu**
```
1. Run LAUNCH_GOODQ.bat again
2. Select: 5 (Stop All Services)
```

### **Method 2: Close Windows**
- Close "GoodQ API Server" window
- Close "GoodQ Watchdog" window

### **Method 3: Force Kill**
```powershell
Stop-Process -Name python -Force
```

---

## After Processing Completes

✅ **Check Results:**

1. **Scene Explorer** → 100+ scenes with thumbnails
2. **Analytics** → Emotion charts, entity graphs
3. **Knowledge Graph** → Relationship visualization
4. **Memories** → Timeline of moments
5. **Chat** → Query: "Show me happy scenes"

✅ **Database Populated:**
```
data/unified_goodq.db  → Main database
data/faiss_indices/    → Vector search
output/                → Generated artifacts
```

---

## Common Issues

### ❌ "Nothing happens"
**Fix:** Check API Server window for errors. Should see:
```
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:3000
```

### ❌ "GPU not showing"
**Fix:** This is normal until processing starts. Wait for scene detection to begin.

### ❌ "Video not detected"
**Fix:** Check watchdog window. Should show:
```
[INFO] Watching directory: L:\goodq4all\import_inbox
```
Verify video is in `import_inbox` folder.

### ❌ "Processing stuck"
**Fix:** Check Command Center tab. If truly stuck:
1. Stop services (Option 5)
2. Check `logs/watchdog.log` for errors
3. Restart system

---

## Pro Tips

💡 Keep both command windows visible  
💡 Don't close windows until complete  
💡 Check Command Center for real-time status  
💡 Chat tab can answer questions  
💡 GPU indicators only show when actively processing  
💡 First run takes longer (model loading)  
💡 Subsequent videos process faster  

---

## Key URLs

| Endpoint | Purpose |
|----------|---------|
| http://localhost:3000 | Main UI |
| http://localhost:3000/api/status | System health JSON |
| http://localhost:3000/api/progress | Current progress JSON |
| http://localhost:3000/api/pipeline-engines | Engine status JSON |

---

## Files To Watch

| File | What It Shows |
|------|---------------|
| `logs/command_center.log` | Unified system log |
| `logs/progress.json` | Current processing state |
| `logs/watchdog.log` | File monitoring activity |
| `logs/step_runs.jsonl` | Step execution history |

---

## Need Help?

1. Check `LAUNCH_INSTRUCTIONS.md` for detailed guide
2. Check `AUDIT_COMPLETE.md` for system status
3. Check Command Center tab for live logs
4. Ask in Chat: "What's the current status?"

---

**Status: ✅ READY TO LAUNCH**

Run `LAUNCH_GOODQ.bat` and select option 1!

🎬 Your home movies → 🧠 Intelligent memory system
