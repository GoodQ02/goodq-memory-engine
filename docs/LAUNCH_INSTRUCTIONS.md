# 🚀 GoodQ4All Launch Instructions

> Role: Detailed launch/runbook for the desktop companion. For the canonical Quick Start, see `docs/user-guides/QUICK_START_CLEAN.md`; for the official shipping surface and supported entrypoints, see `docs/SHIP_PROFILE.md`.

## Current Status: ✅ READY TO LAUNCH

All systems have been audited and optimized. The system is clean and ready for production testing.

---

## 🎬 Quick Start

### **Option 1: Launch Complete System (Recommended)**

1. **Run:** `LAUNCH_GOODQ.bat`
2. **Select:** Option 1 (Launch Complete System)
3. **Wait:** System will open:
   - API Server window
   - Watchdog window  
   - Web browser at http://localhost:3000

### **Option 2: Launch from PowerShell**

```powershell
cd L:\goodq4all
.\LAUNCH_GOODQ.bat
```

---

## 📊 What You'll See

### **1. Immediately After Launch:**

- **Command Center Tab**: Live log streaming (updates every 2 seconds)
- **Pipeline Engines Tab**: All engines showing "idle" status
- **Chat Interface**: Ready for queries
- **System Status**: Active, 0 videos processed

### **2. Once Watchdog Detects Video:**

The watchdog will automatically pick up `01. 1987 - 1988.mp4` from `import_inbox`:

- **Progress Bar**: Appears at top showing current step
- **Pipeline Engines**: Each engine lights up as it activates
- **GPU Usage**: Shows in engines tab (real-time when active)
- **Command Center**: Logs scroll with detailed progress

### **3. GPU Monitoring:**

The `/api/pipeline-engines` endpoint checks:
- Current step from `logs/progress.json`
- Recent activity from `logs/step_runs.jsonl`
- Marks engines as "active" when running within last 60 seconds

---

## 🔍 Monitoring Your Run

### **Web Interface** (http://localhost:3000)

| Tab | What To Watch |
|-----|---------------|
| **Chat** | Ask questions about progress: "What step are we on?" |
| **Pipeline Engines** | See which tools are active (color-coded by category) |
| **Command Center** | Raw logs from watchdog (auto-scrolls to bottom now) |
| **Scene Explorer** | Scenes appear as they're processed |
| **Analytics** | Database grows in real-time |
| **Memories** | Emotion/entity graphs populate |

### **Command Windows**

- **API Server Window**: HTTP requests, endpoint calls
- **Watchdog Window**: Step execution, progress updates

---

## 🎯 Expected Processing Timeline

For a **7.5GB home video (~4.5 hours)**:

| Stage | Time | Notes |
|-------|------|-------|
| **Scene Detection** | 15-30 min | GPU accelerated, VAD pre-filtering |
| **Audio Transcription** | 45-90 min | Whisper on GPU (per scene) |
| **Audio Diarization** | 30-60 min | PyAnnote with VAD optimization |
| **Face Recognition** | 20-40 min | DeepFace on GPU |
| **Emotion Classification** | 15-30 min | GPU accelerated |
| **CLIP/DINO Embeddings** | 20-30 min | GPU batch processing |
| **Knowledge Graph Build** | 5-10 min | CPU intensive |

**Total: 2.5 - 5 hours** (optimized with GPU acceleration)

---

## ✅ Verification Checklist

After launching, verify these in order:

### 1. Services Running
```powershell
# Check from PowerShell
Get-Process | Where-Object {$_.MainWindowTitle -like "*GoodQ*"}
```
Should see: `GoodQ API Server` and `GoodQ Watchdog`

### 2. API Responding
Visit: http://localhost:3000/api/status  
Should return JSON with `"status": "active"`

### 3. Video Detection
**Watchdog window** should show:
```
[INFO] New file detected: 01. 1987 - 1988.mp4
[INFO] File stable: 01. 1987 - 1988.mp4
[INFO] Queued for processing: 01. 1987 - 1988.mp4
```

### 4. GPU Active
**After processing starts**, check engines tab in UI:
- Scene Detection engine should show "active" with green indicator
- Command Center logs should show GPU being used

---

## 🐛 Troubleshooting

### "Nothing Happens After Launch"

**Check for errors in windows:**
- API Server window should say `INFO: Application startup complete`
- Watchdog window should say `[INFO] Starting file monitor...`

### "Video Not Processing"

**Check import_inbox:**
```powershell
Get-ChildItem L:\goodq4all\import_inbox
```
Should show `01. 1987 - 1988.mp4`

**Check watchdog is monitoring:**
Look for `[INFO] Watching directory: L:\goodq4all\import_inbox` in watchdog window

### "GPU Not Showing in UI"

**This is normal until processing actually starts!**

Once scene detection or transcription begins, the engines tab will update.

**To force verify GPU is accessible:**
```powershell
conda activate goodq_audio_diarize
python -c "import torch; print('CUDA:', torch.cuda.is_available())"
```
Should print: `CUDA: True`

### "Services Won't Stop"

Run `LAUNCH_GOODQ.bat` → Option 5 (Stop All Services)

Or manually:
```powershell
Stop-Process -Name python -Force
```

---

## 📁 Key Files to Watch

| File | Purpose | Updates |
|------|---------|---------|
| `logs/progress.json` | Current processing state | Every step change |
| `logs/step_runs.jsonl` | Step execution history | Every step completion |
| `logs/watchdog.log` | Watchdog activity | Continuous |
| `logs/command_center.log` | Unified system log | Continuous |
| `data/unified_goodq.db` | Main database | Every artifact |

---

## 🎨 UI Features Now Live

### ✅ Fully Wired & Functional:

- **Real-time system status** (10s polling)
- **Command Center logs** (2s streaming)
- **Pipeline Engines status** (active/idle indicators)
- **Scene Explorer** (database-driven, searchable)
- **Analytics Dashboard** (emotion charts, entity graphs)
- **Knowledge Graph Visualization** (Neo4j-style)
- **Chat Interface** (LLM-powered queries)
- **Progress Bar** (top of screen, step-by-step)
- **Database Stats** (live counters)
- **Memory Timeline** (temporal visualization)

### 🚧 Coming Soon:

- Process control (start/stop/restart from UI)
- GPU memory graphs
- Performance metrics dashboard
- Export functionality

---

## 💡 Pro Tips

1. **Keep both command windows visible** so you can see logs in real-time
2. **Don't close windows until processing completes** - Progress is not saved between runs yet
3. **Watch the progress bar** at the top of the UI - it's your best indicator
4. **Command Center auto-scrolls** to most recent now (fixed!)
5. **Chat is functional** - Ask "What step are we on?" or "How many scenes detected?"

---

## 🎉 You're All Set!

Run `LAUNCH_GOODQ.bat` and watch your home movies transform into an intelligent, searchable memory system!

The UI will populate with real data as processing happens - no placeholders, no fake data.

**🚀 Ready to launch when you are!**
