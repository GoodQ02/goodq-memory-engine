# 🧪 GoodQ4All - Laptop Testing Checklist

## After Fresh Installation

### ✅ Phase 1: Environment Validation

- [ ] **Miniconda installed**
  ```powershell
  conda --version
  # Expected: conda 23.x.x or higher
  ```

- [ ] **All environments created**
  ```powershell
  conda env list
  # Expected: 6+ environments (goodq_zenml, goodq_video_scene_detect, etc.)
  ```

- [ ] **Python paths configured**
  ```powershell
  python test_python_paths.py
  # Expected: ✓ ALL TESTS PASSED
  ```

- [ ] **GPU accessible**
  ```powershell
  nvidia-smi
  python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
  # Expected: CUDA: True
  ```

---

### ✅ Phase 2: Database Initialization

- [ ] **Databases created**
  ```powershell
  python check_db_status.py
  # Expected: All databases OK
  ```

- [ ] **FAISS indices initialized**
  ```powershell
  dir L:\goodq4all\output\faiss
  # Expected: text.index, clip.index, dino.index, audio.index
  ```

- [ ] **Directory structure correct**
  ```powershell
  python diagnose_system.py
  # Expected: Overall: 5/5 checks passed (or 4/5 before starting API)
  ```

---

### ✅ Phase 3: LM Studio Integration

- [ ] **LM Studio installed**
  - Download from https://lmstudio.ai/
  - Install and launch

- [ ] **Model downloaded**
  - Recommended: qwen2.5-7b-instruct, phi-4, or llama-3.1-8b
  - Verify in LM Studio model library

- [ ] **Server running**
  - Start LM Studio local server
  - Verify: http://localhost:1234/v1/models
  - Should return list of available models

- [ ] **Configuration updated**
  ```powershell
  notepad .env.local
  # Set:
  # LM_STUDIO_URL=http://localhost:1234
  # LM_STUDIO_MODEL=your-model-name
  ```

---

### ✅ Phase 4: System Startup

- [ ] **API server starts**
  ```powershell
  python api_server.py
  # Expected: Uvicorn running on http://0.0.0.0:30000
  ```

- [ ] **API responding**
  - Open browser: http://localhost:30000/api/status
  - Expected: JSON response with system status

- [ ] **Watchdog starts**
  ```powershell
  python scripts\watchdog_ingest.py
  # Expected: GoodQ Watchdog Starting, no errors
  ```

- [ ] **Web UI accessible**
  - Open browser: http://localhost:30000
  - Expected: GoodQ interface loads

---

### ✅ Phase 5: First Ingestion Test

- [ ] **Copy sample video**
  ```powershell
  copy "C:\path\to\test\video.mp4" ".\import_inbox\"
  ```

- [ ] **Watchdog detects file**
  - Check logs: `logs/watchdog.log`
  - Expected: "New file detected: video.mp4"

- [ ] **Processing starts**
  - Monitor: http://localhost:30000 (Command Center)
  - Expected: See pipeline steps executing

- [ ] **Scene detection completes**
  - Check output: `output/videos/video_HASH/scenes/`
  - Expected: Scene .mp4 files created

- [ ] **Transcription works**
  - Check: `output/videos/video_HASH/transcripts/`
  - Expected: Transcript .json files

- [ ] **Embeddings generated**
  - Check database:
  ```powershell
  python check_db_stats.py
  # Expected: Embeddings > 0
  ```

- [ ] **Ingestion completes**
  - Final status in UI: "Processing complete"
  - No errors in logs

---

### ✅ Phase 6: UI Features

- [ ] **Chat works**
  - Ask: "Show system status"
  - Expected: LLM responds with actual data

- [ ] **Scene explorer loads**
  - Navigate to Scenes
  - Expected: List of detected scenes

- [ ] **Knowledge graph displays**
  - Navigate to Knowledge
  - Expected: Graph visualization (or coming soon message)

- [ ] **Analytics dashboard**
  - Navigate to Analytics
  - Expected: Charts with real data

- [ ] **Command center live**
  - Navigate to Command Center
  - Expected: Live log streaming

- [ ] **Process control**
  - Navigate to Processes
  - Expected: See running processes, can stop/start

---

### ✅ Phase 7: Advanced Features

- [ ] **Search functionality**
  - Search for: "person" or "scene"
  - Expected: Results from database

- [ ] **Memory browsing**
  - Navigate to Memories
  - Expected: Timeline or list of memories

- [ ] **Export works**
  - Click Export button
  - Expected: Download data or see export options

- [ ] **Settings accessible**
  - Navigate to Settings
  - Expected: Can view/edit configuration

---

### ✅ Phase 8: Performance Tests

- [ ] **GPU utilization**
  ```powershell
  nvidia-smi -l 1
  # Monitor during ingestion
  # Expected: GPU usage 50-90%, memory within limits
  ```

- [ ] **Memory management**
  - Monitor RAM usage during processing
  - Expected: No OOM errors, stable memory

- [ ] **Concurrent processing**
  - Add 2 videos simultaneously
  - Expected: Both process (or queue correctly)

- [ ] **Long video (30+ min)**
  - Test with longer video
  - Expected: Completes without hanging

---

### ✅ Phase 9: Error Handling

- [ ] **Invalid file handling**
  - Add a .txt file to import_inbox
  - Expected: Skipped or handled gracefully

- [ ] **Corrupted video**
  - Add a corrupted .mp4
  - Expected: Error logged, doesn't crash system

- [ ] **Out of disk space**
  - Simulate low disk (optional)
  - Expected: Graceful error message

- [ ] **GPU memory overflow**
  - Process very large video (4K+)
  - Expected: Handled with batch size reduction or warning

---

### ✅ Phase 10: Cleanup & Maintenance

- [ ] **Log rotation works**
  - Check log sizes after several ingestions
  - Expected: Logs don't grow indefinitely

- [ ] **Temp files cleaned**
  - Check: `data/processing/`
  - Expected: Old temp files removed after completion

- [ ] **Database integrity**
  ```powershell
  python check_db.py
  # Expected: No corruption, all tables valid
  ```

- [ ] **Restart resilience**
  - Stop all processes
  - Restart system
  - Expected: Picks up where left off, or cleanly restarts

---

## Common Issues & Fixes

### Issue: "CUDA out of memory"
```python
# Edit gpu_config.py
GPU_MEMORY_FRACTION = 0.3  # Reduce
MAX_CONCURRENT_GPU_TASKS = 1
```

### Issue: "Conda command not found"
```powershell
# Reinstall Miniconda or fix PATH
$env:Path += ";C:\Users\YOUR_USERNAME\miniconda3\Scripts"
```

### Issue: "Port 30000 already in use"
```powershell
# Find and kill process
netstat -ano | findstr :30000
taskkill /PID <PID> /F
```

### Issue: "LM Studio not responding"
```powershell
# Restart LM Studio
# Verify server is running on correct port
# Check .env.local configuration
```

---

## Performance Benchmarks

### Expected Processing Times (Sample Video - 1min, 720p)

- **Scene Detection**: 10-30 seconds
- **Audio Transcription**: 30-60 seconds
- **Face Embedding**: 15-30 seconds
- **Object Detection**: 30-60 seconds
- **Emotion Classification**: 15-30 seconds
- **Knowledge Graph**: 10-20 seconds

**Total**: 2-4 minutes for 1 minute of video

### For Your Home Movies (2 hours each)

- **Per Video**: 4-8 hours
- **24 Hours Total Content**: 4-8 days (sequential)
- **With Optimization**: 2-3 days (parallel processing)

---

## Success Criteria

✅ **Installation Successful If:**
- All tests pass
- Can process sample video end-to-end
- UI loads and is interactive
- Chat responds with real data
- No critical errors in logs

✅ **Production Ready If:**
- Processed at least 1 full home movie (2hr)
- All UI features working
- LLM chat provides accurate responses
- Analytics show real insights
- System stable for 24+ hours

---

## Next Steps After Testing

1. **Optimize settings** based on laptop performance
2. **Start ingesting** full home movie library
3. **Monitor** first few ingestions closely
4. **Fine-tune** GPU settings if needed
5. **Explore** analytics and insights as data grows

---

**Last Updated**: November 11, 2025
**For**: Laptop Installation Testing
**Status**: Ready for deployment ✅
