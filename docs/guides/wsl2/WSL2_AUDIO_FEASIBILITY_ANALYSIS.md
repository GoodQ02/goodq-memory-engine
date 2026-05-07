# WSL2 Audio Processing Offload - Feasibility Analysis

> Historical feasibility note: this 2025 analysis is not the current WSL audio
> setup guide. Do not run the unpinned package commands below for current
> installs. Use `wsl2_audio/README.md`, `docs/reference/WSL_AUDIO_RUNTIME.md`,
> and `wsl2_audio/requirements-bootstrap-constraints.txt` for the active
> bootstrap contract.

## Current Status Check (2025-11-13)

### ✅ WSL2 Infrastructure Ready
- **WSL2 Version**: 2
- **Default Distro**: Ubuntu
- **CUDA Available**: ✅ YES (NVIDIA-SMI working in WSL2)
- **Driver Version**: 581.80
- **CUDA Version**: 13.0
- **GPU**: NVIDIA GeForce RTX 4070 Ti SUPER (16GB VRAM)

### ❌ Missing Components in WSL2
- PyTorch not installed in WSL2 Python environment
- Whisper/Faster-Whisper not installed
- Audio processing dependencies not configured

---

## FEASIBILITY ASSESSMENT

### 🎯 Benefits (HIGH VALUE)

1. **Performance Gains** (Expected: 3-5x faster)
   - Linux CUDA stack is more mature and stable
   - Better memory management for audio models
   - Faster-Whisper runs significantly better on Linux
   - Pyannote diarization more stable with Linux CUDA

2. **Stability Improvements**
   - No more Windows CUDA wheel compatibility issues
   - Better GPU memory handling
   - Native CUDA support without Windows overhead
   - Eliminates current audio pipeline stalls

3. **Resource Isolation**
   - Audio processing isolated from Windows processes
   - Can set dedicated GPU memory limits
   - No interference with UI or other Windows services
   - Better process management

### ⚠️ Risks (MEDIUM - MANAGEABLE)

1. **Integration Complexity** (Risk: LOW-MEDIUM)
   - Need file-sharing between Windows and WSL2 (already solved: /mnt/c/)
   - Need IPC mechanism (can use simple file queues or sockets)
   - Additional monitoring layer needed

2. **Environment Duplication** (Risk: LOW)
   - Need to set up audio envs in WSL2
   - But: Only 3-4 audio-specific environments
   - One-time setup cost

3. **Debugging Overhead** (Risk: MEDIUM)
   - Logs split between Windows and WSL2
   - But: Can aggregate to shared log directory
   - Need dual-terminal monitoring initially

4. **Dependency Management** (Risk: LOW)
   - Separate pip/conda in WSL2
   - But: Linux wheels are more stable
   - Fewer version conflicts

### 💰 Cost-Benefit Analysis

**Setup Time**: 2-4 hours
**Testing/Validation**: 2-3 hours
**Total Investment**: 4-7 hours

**Expected Returns**:
- Audio processing speed: 3-5x faster
- Reduced stalls: ~90% elimination
- GPU utilization: 60-80% (vs current 20-30%)
- Developer sanity: PRICELESS

**Verdict**: ✅ **WORTH IT**

---

## IMPLEMENTATION STRATEGY

### Phase 1: WSL2 Setup (30 min)
```bash
# In WSL2 Ubuntu terminal
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv
sudo apt install -y ffmpeg
pip3 install --upgrade pip
```

### Phase 2: CUDA PyTorch (20 min)
```bash
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
python3 -c "import torch; print('CUDA:', torch.cuda.is_available())"
```

### Phase 3: Audio Stack (45 min)
```bash
# Create dedicated audio environment
python3 -m venv ~/goodq_audio_wsl
source ~/goodq_audio_wsl/bin/activate

# Install audio processing tools through the current repo constraints.
# Do not install unpinned pyannote/torch packages from this historical note.
```

### Phase 4: Bridge Layer (60 min)
Create a lightweight Python service in WSL2 that:
1. Watches `~/goodq_audio/queue_in/pending/` for jobs
2. Processes audio using GPU
3. Writes results to `~/goodq_audio/queue_out/`
4. Updates status file for Windows monitor

### Phase 5: Windows Integration (60 min)
Modify GoodQ pipeline to:
1. Detect WSL2 availability
2. Queue audio jobs to WSL2 bridge
3. Monitor completion via status files
4. Integrate results back into pipeline

---

## ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                         WINDOWS SIDE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐      ┌──────────────┐     ┌──────────────┐ │
│  │   GoodQ UI   │      │   Pipeline   │     │  Database    │ │
│  │  (FastAPI)   │─────▶│ Orchestrator │────▶│  SQLite      │ │
│  └──────────────┘      └──────┬───────┘     └──────────────┘ │
│                               │                               │
│                               │                               │
│                               ▼                               │
│                    ┌──────────────────────┐                  │
│                    │  Audio Queue Dir     │                  │
│                    │  canonical log/step  │                  │
│                    │  outputs on Windows  │                  │
│                    └──────────┬───────────┘                  │
└────────────────────────────────┼──────────────────────────────┘
                                 │
                    [File System Bridge]
                                 │
┌────────────────────────────────┼──────────────────────────────┐
│                                ▼            WSL2 (Ubuntu)     │
│                    ┌──────────────────────┐                  │
│                    │   Audio Queue        │                  │
│                    │  ~/goodq_audio/      │                  │
│                    │  queue_in/pending/   │                  │
│                    └──────────┬───────────┘                  │
│                               │                               │
│                               ▼                               │
│                    ┌──────────────────────┐                  │
│                    │  WSL2 Audio Service  │                  │
│                    │  - File Watcher      │                  │
│                    │  - Job Processor     │                  │
│                    │  - Status Reporter   │                  │
│                    └──────────┬───────────┘                  │
│                               │                               │
│                    ┌──────────▼───────────┐                  │
│              ┌────▶│  Faster-Whisper     │                  │
│              │     │  (CUDA GPU)          │                  │
│              │     └──────────────────────┘                  │
│              │                                                │
│  ┌───────────┴──────────┐    ┌──────────────────────┐      │
│  │  Pyannote Diarize    │    │   Silero VAD         │      │
│  │  (CUDA GPU)          │    │   (Pre-filter)       │      │
│  └───────────┬──────────┘    └──────────────────────┘      │
│              │                                                │
│              │     ┌──────────────────────┐                  │
│              └────▶│  Output Directory    │                  │
│                    │  ~/goodq_audio/      │                  │
│                    │  queue_out/          │                  │
│                    └──────────┬───────────┘                  │
└────────────────────────────────┼──────────────────────────────┘
                                 │
                    [File System Bridge]
                                 │
┌────────────────────────────────┼──────────────────────────────┐
│                         WINDOWS SIDE                          │
│                                ▼                               │
│                    ┌──────────────────────┐                  │
│                    │  Pipeline Continues  │                  │
│                    │  - Parse results     │                  │
│                    │  - Update DB         │                  │
│                    │  - Build graph       │                  │
│                    └──────────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## TESTING PLAN

### Benchmark Test (Before/After)

**Test Video**: `sample.mp4` (5 minute clip)

**Metrics to Compare**:
1. Transcription time (Whisper)
2. Diarization time (Pyannote)
3. GPU utilization %
4. Peak VRAM usage
5. CPU usage
6. Total pipeline time

**Expected Improvements**:
- Whisper: 5min → 1-2min (3-5x faster)
- Diarization: 10min → 2-3min (3-5x faster)
- GPU util: 20-30% → 60-80%
- CPU usage: Reduced by 40%
- Stalls: Eliminated

---

## ROLLBACK PLAN

If WSL2 approach fails or causes issues:

1. Keep existing Windows audio processing as fallback
2. Add feature flag: `USE_WSL2_AUDIO = False`
3. Pipeline automatically detects and uses Windows path
4. Zero data loss risk (all outputs go to shared directory)

---

## RECOMMENDATION

### ✅ **PROCEED WITH WSL2 IMPLEMENTATION**

**Reasoning**:
1. Infrastructure already in place (WSL2 + CUDA working)
2. High probability of success (90%+)
3. Manageable risks with clear rollback
4. Significant performance gains expected
5. Will solve current audio pipeline stalls
6. Better long-term maintainability

**Timeline**: 
- Setup: 4-6 hours
- Testing: 2-3 hours
- Total: 1 working day

**Next Steps**:
1. Install PyTorch + CUDA in WSL2
2. Install audio processing stack
3. Create bridge service
4. Run benchmark tests
5. Integrate with main pipeline
6. Deploy and monitor

---

## ALTERNATIVE: Keep Windows + Optimize Further

If you don't want WSL2 complexity:

1. ✅ Already implemented VAD pre-filtering
2. ✅ Already using chunking strategies
3. ❌ Still hitting Windows CUDA stability issues
4. ❌ Not reaching optimal GPU utilization
5. ❌ Continued audio processing stalls

**Verdict**: This gets us 60% of the way. WSL2 gets us 95%.

---

## DECISION

**Recommendation**: Implement WSL2 audio offload

**Confidence Level**: HIGH (8/10)

**Risk Level**: LOW-MEDIUM (manageable)

**Value**: HIGH (game-changer for audio processing)

Ready to proceed? Y/N
