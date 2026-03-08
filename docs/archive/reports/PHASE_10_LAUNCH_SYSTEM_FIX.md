<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_ARCHIVED_ON: 2026-02-12 -->

> [!WARNING]
> ARCHIVE / NON-CANONICAL / DO NOT COPY PATHS
> This document is preserved as historical evidence and may contain obsolete fixed-drive paths, host-specific assumptions, stale commands, or superseded runtime guidance.
> Do not use it for current runtime, setup, migration, or copy-paste path decisions.
> Use active documentation, `config_loader`, and canonical path abstractions such as `<project_root>`, `<GOODQ_DATA_ROOT>`, and `<GOODQ_WSL_WORKSPACE>` instead.

# Phase 10: Launch System Fix Report
**Date:** 2025-12-09  
**Status:** ✅ FIXING CRITICAL LAUNCH ISSUES

## 🎯 Issues Identified

### 1. **Python Path Configuration**
- **Problem:** PYTHONPATH not consistently set across launch scripts
- **Impact:** Import errors when watchdog calls ingestion
- **Solution:** Ensure `PYTHONPATH=L:\goodq4all` in all launch contexts

### 2. **Watchdog → CLI Integration**
- **Current:** Watchdog calls `python -m cli.run_ingestion`
- **Status:** Working correctly - uses subprocess with proper paths
- **Note:** Requires L:\goodq4all to be in sys.path

### 3. **Import Path Issues**
- **Problem:** Some modules expect `goodq4all.steps.*` imports
- **Current:** Watchdog uses `steps.*` imports directly (which works from repo root)
- **Status:** Both patterns work when PYTHONPATH is set correctly

## ✅ Launch System Architecture

```
LAUNCH_GOODQ.bat
├── Sets PYTHONPATH=L:\goodq4all
├── Uses .venv\Scripts\python.exe if available
├── Falls back to base conda python
├── Launches:
    ├── API Server (port 30000)
    ├── Processing Stats Service
    ├── WSL vLLM Services (systemd)
    └── Watchdog (watchdog_ingest.py)
```

### Watchdog Video Ingestion Flow
```
watchdog_ingest.py
└── ingest_video()
    ├── Creates temp processing dir
    ├── Copies video to temp location
    ├── Calls: python -m cli.run_ingestion
        ├── --input-dir <temp_dir>
        ├── --workspace <log_dir>
        ├── --output <results.json>
        ├── --step-timeout 600
        ├── --force
        └── --verbose
    └── Timeout: 8+ hours (3hrs per GB)
```

### CLI Ingestion Flow
```
cli/run_ingestion.py
├── Loads config via config_loader
├── Scans input directory for videos
├── For each video:
    ├── Extracts metadata
    ├── Processes via conda step runner
    ├── Calls Phase 0-6 steps
    └── Generates temporal_index.json
```

## 🔧 Fixes Applied

### 1. **PYTHONPATH Consistency**
```batch
REM In LAUNCH_GOODQ.bat (line 32)
set "PYTHONPATH=L:\goodq4all"
```

### 2. **Watchdog Python Path** ✅ ALREADY CORRECT
```python
# In watchdog_ingest.py (lines 24-25)
REPO_ROOT = Path(__file__).resolve().parents[1]  # L:\goodq4all
sys.path.insert(0, str(REPO_ROOT))
```

### 3. **CLI Python Path** ✅ ALREADY CORRECT
```python
# In cli/run_ingestion.py (lines 15-16)
REPO_ROOT = Path(__file__).resolve().parents[1]  # L:\goodq4all
sys.path.insert(0, str(REPO_ROOT))
```

## 🎬 Testing Protocol

### Test 1: Manual Ingestion via CLI
```bash
cd L:\goodq4all
set PYTHONPATH=L:\goodq4all
python -m cli.run_ingestion --input-dir "L:\goodq4all\import_inbox" --verbose
```

### Test 2: Watchdog Auto-Ingestion
```bash
cd L:\goodq4all
python scripts\watchdog_ingest.py
# Drop video in import_inbox and monitor
```

### Test 3: Full System Launch
```bash
LAUNCH_GOODQ.bat
# Select option 1 (Complete System)
# Drop video in import_inbox
```

## 📊 Current System State

### ✅ Working Components
- [x] LAUNCH_GOODQ.bat structure
- [x] PYTHONPATH injection
- [x] Watchdog file monitoring
- [x] Watchdog → CLI subprocess call
- [x] CLI ingestion entrypoint exists
- [x] Config loader
- [x] Step runner framework
- [x] Conda environment routing

### ⚠️ Needs Validation
- [ ] End-to-end ingestion (Phase 0-6)
- [ ] Phase 6 execution (embeddings + harmonizer)
- [ ] temporal_index.json generation
- [ ] Retrieval engine integration
- [ ] API serving processed videos

## 🚀 Next Steps

1. **Run Test Ingestion**
   - Use sample.mp4 (small file)
   - Monitor all phases
   - Validate artifacts generated

2. **Fix Phase 6 Integration**
   - Ensure scene_visual_embeddings runs
   - Ensure cross_modal_harmonization runs
   - Validate temporal_index.json created

3. **Validate Retrieval**
   - Test MultimodalSearchEngine
   - Query for scenes
   - Verify results

4. **Production Launch**
   - Process full video library
   - Monitor for errors
   - Optimize performance

## 📝 Configuration Reference

### Key Paths
- **Repo Root:** `L:\goodq4all`
- **Import Inbox:** `L:\goodq4all\import_inbox`
- **Processing:** `L:\goodq4all\data\processing`
- **Processed:** `L:\goodq4all\data\processed`
- **Failed:** `L:\goodq4all\data\failed`
- **Logs:** `L:\goodq4all\logs`

### Key Configs
- **Main Config:** `L:\goodq4all\configs\config.yaml`
- **Schema:** `L:\goodq4all\config_schema.py` (Pydantic)
- **Watchdog State:** `L:\goodq4all\logs\watchdog_state.json`

### Conda Environments
- **goodq_core:** Main GPU processing (CUDA 12.1)
- **goodq_audio_*:** WSL2 audio processing
- **Base:** Python 3.13.5 (watchdog, API, CLI)

## 🎯 Success Criteria

✅ **System is LIVE when:**
1. Watchdog monitors import_inbox
2. Video dropped → automatically ingested
3. All phases execute (0-6)
4. temporal_index.json generated
5. Retrieval returns scenes
6. API serves results

---

**Status:** Ready to test with "L:\goodq4all\import_inbox\01. 1987 - 1988.mp4"
