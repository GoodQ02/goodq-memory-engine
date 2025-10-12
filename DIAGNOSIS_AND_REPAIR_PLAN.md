# GoodQ Pipeline Diagnosis & Repair Plan
**Mission Date**: 2025-10-11  
**Agent**: Q (AI Assistant)  
**Status**: CRITICAL DEBUGGING IN PROGRESS

---

## 🎯 MISSION OBJECTIVE
Identify and eliminate all weak links in the ingestion pipeline to achieve **100% reliable, end-to-end processing** of home video memories.

---

## 📊 CURRENT STATUS ASSESSMENT

### ✅ What's Working
1. **File Watchdog**: Successfully detects and queues files
2. **Scene Detection**: Extracting frames and audio clips correctly
   - Example: 6 scenes detected from "02. 1988 - 1989.mp4"
   - Frames: 6 .jpg files created
   - Audio: 6 .wav files created
3. **Environment Isolation**: All 22+ conda environments are operational
4. **CUDA Support**: GPU acceleration confirmed across all vision/audio envs
5. **Model Caching**: Models are pinned and locked at L:\models

### ❌ Critical Issues Identified

#### **Issue #1: Silent Failures (FIXED but need verification)**
- **Problem**: Steps reporting "ok" status but not actually producing output
- **Root Cause**: Lack of proper error handling and output validation
- **Impact**: Database shows empty/minimal data despite "successful" runs
- **Status**: Fixes applied in `diagnose_silent_failures.py` audit

#### **Issue #2: 2-Hour Timeout on Long Videos**
- **Problem**: Watchdog times out after 7200 seconds (2 hours)
- **Example**: "02. 1988 - 1989.mp4" (7.4GB, ~2 hours long) timed out
- **Impact**: Large home movies never complete processing
- **Root Cause**: 
  - Hardcoded 2-hour timeout in watchdog_ingest.py
  - No progress tracking or resume capability
  - Processing is single-threaded per video

#### **Issue #3: Missing Step Logs**
- **Problem**: No `step_log.jsonl` files found in workspace directories
- **Impact**: Can't track which steps completed/failed
- **Root Cause**: Steps may not be writing logs, or logs are going to wrong location

#### **Issue #4: Database Not Populating**
- **Problem**: Memory.db shows minimal embeddings (33) vs expected (hundreds+)
- **Problem**: Knowledge graph "not created yet"
- **Impact**: No queryable data despite processing
- **Root Cause**: Steps may not be calling `store_embedding()` correctly

#### **Issue #5: Embedding Storage Inconsistency**
- **FAISS Indices**: text=13, dino=13, audio=10, clip=missing
- **Database**: 33 embeddings total
- **Drift**: 60.6% drift on text embeddings (FAISS vs DB mismatch)
- **Impact**: Retrieval will fail or return incorrect results

---

## 🔧 REPAIR STRATEGY

### Phase A: Add Comprehensive Logging & Validation ✅ (APPLIED)
**Goal**: Make ALL failures visible

1. ✅ Add output validation to every step
2. ✅ Log actual output sizes/counts
3. ✅ Fail loudly when outputs are empty/invalid
4. ✅ Write step_log.jsonl to workspace root
5. ✅ Track processing time per step

**Files Modified**:
- All step files in `steps/` directory
- Added validation wrappers
- Enhanced error logging

### Phase B: Fix Timeout & Progress Tracking (IN PROGRESS)
**Goal**: Support multi-hour video processing

**Changes Needed**:
1. **Increase watchdog timeout** from 2 hours to 8 hours (or remove entirely)
2. **Add progress callbacks** so user can monitor long-running jobs
3. **Implement checkpointing**: Save completed scenes to DB incrementally
4. **Add resume capability**: Skip already-processed scenes on restart
5. **Parallel scene processing**: Process multiple scenes concurrently (where safe)

**Target Files**:
- `scripts/watchdog_ingest.py` - timeout & progress
- `cli/run_ingestion.py` - add checkpoint support
- Steps: Add scene-level commits to DB

### Phase C: Database Integration Test (NEXT)
**Goal**: Verify data actually flows to memory.db and FAISS

**Test Plan**:
1. Clear all databases
2. Process single 1-minute test video
3. Verify:
   - Step_log.jsonl has all entries
   - memory.db has scene records
   - memory.db has embedding records  
   - FAISS indices have matching counts
   - Knowledge graph has entities/relationships
4. Query API to retrieve the test video

### Phase D: Production Run (FINAL)
**Goal**: Full 7GB+ video processing end-to-end

**Target**: 1987_1988.mp4 (your first birthday tape!)

**Success Criteria**:
- All scenes processed (no timeouts)
- Step_log shows all steps completed
- Database populated with:
  - Scene metadata
  - Object detections
  - Transcriptions
  - Embeddings (text, audio, CLIP, DINO)
  - Entities (people, dates, events)
- Knowledge graph built
- API can retrieve and search video content

---

## 🚀 NEXT ACTIONS

### Immediate (Right Now):
1. **Fix watchdog timeout** - increase to 8 hours
2. **Add progress logging** - show "Scene X/Y processing..."
3. **Test on sample.mp4** - verify end-to-end with known-good short video

### Short-term (Today):
4. **Clear databases** - fresh start with clean slate
5. **Run 1987_1988.mp4** - the birthday tape, full production run
6. **Monitor in real-time** - watch step_log.jsonl as it processes
7. **Verify outputs** - check DB, FAISS, and knowledge graph

### Medium-term (Next Session):
8. **Add parallel processing** - speed up multi-scene videos
9. **Add checkpointing** - resume interrupted jobs
10. **Build monitoring dashboard** - real-time progress UI

---

## 📝 TESTING CHECKLIST

- [ ] Watchdog starts and monitors inbox
- [ ] Sample.mp4 processes completely (< 5 minutes)
- [ ] Step_log.jsonl written to workspace
- [ ] All steps report success with output counts
- [ ] memory.db populated with embeddings
- [ ] FAISS indices created and sized correctly
- [ ] Knowledge graph built with entities
- [ ] API can retrieve video via text query
- [ ] Command Center shows non-zero stats
- [ ] 1987_1988.mp4 processes completely (estimate: 3-4 hours)
- [ ] No silent failures or empty outputs

---

## 🎖️ MISSION NOTES

**Why this matters**: We're building a **personal memory archive system** that extracts deep semantic meaning from irreplaceable family videos. Every bug we fix brings us closer to:

1. Searchable memories ("Show me my first birthday")
2. Entity tracking ("Show all scenes with Grandma")
3. Emotional timeline ("Show happy Christmas moments")
4. Knowledge graph ("What years did we visit the beach?")

**The stakes**: These are once-in-a-lifetime moments. We can't afford silent failures or lost data. Every video must be processed completely and correctly.

**The goal**: Transform raw video into a queryable, analyzable, preservable digital memory palace.

---

## 📈 PROGRESS LOG

**2025-10-11 Morning**: 
- Discovered silent failure bug (steps reporting "ok" with no output)
- Applied validation fixes to all steps
- Identified 2-hour timeout issue
- Confirmed scene extraction working

**2025-10-11 Afternoon**:
- Creating comprehensive diagnosis
- Planning timeout fix and progress tracking
- Preparing for clean-slate production run

**2025-10-11 Late Afternoon** (CURRENT):
- ✅ Increased watchdog timeout (4hrs base + 2hrs per GB)
- ✅ Created progress monitoring system (MONITOR_PROGRESS.bat)
- ✅ Created clean test suite (TEST_CLEAN_RUN.bat)
- ✅ Created comprehensive code audit tool
- ✅ Created full diagnostic suite (RUN_FULL_DIAGNOSTIC.bat)
- 🔄 Ready for production testing

---

## 🔐 AGENT NOTES (Internal)

This is the breakthrough moment. We've been debugging shadows - steps that claimed to work but didn't. Now we're about to turn on the lights:

1. **Validation everywhere** - no more lies
2. **Verbose logging** - see everything happening
3. **Incremental commits** - save progress as we go
4. **Graceful timeouts** - handle long videos properly
5. **Real monitoring** - watch it actually work

Once this is done, GoodQ becomes **operational**. Not just "kinda works" but "reliably processes multi-hour home movies with full semantic extraction and knowledge graph construction."

That's the mission. That's what we're building.

**Q out. 🎯**
