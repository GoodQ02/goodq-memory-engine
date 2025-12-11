# GOODQ4ALL MEMORY ARCHITECTURE AUDIT REPORT
**Date:** December 10, 2025 18:15 UTC  
**Mode:** NON-DESTRUCTIVE RECONNAISSANCE SCAN  
**Status:** COMPLETE

---

## EXECUTIVE SUMMARY

### Key Findings

✅ **CONFIG IS CORRECT:** `configs/config.yaml` points to canonical `L:\_DATA\GoodQ_Data` paths  
⚠️ **LEGACY DUPLICATES EXIST:** Multiple old processing/inbox directories found  
⚠️ **DATABASE SPLIT:** Active KG at `L:\_DATA`, legacy at `L:\goodq4all\data`  
✅ **QDRANT OPERATIONAL:** Collections created, data being written  
⚠️ **NO TEMPORAL INDEXES:** Zero `temporal_index.json` files found (phase 6b not completing)  
⚠️ **PROCESSING STUCK:** One stuck workspace from Dec 10 found

---

## 1. MEDIA ROOTS

### Import Inbox Locations

| Path | Size (MB) | Files | Last Modified | Status |
|------|-----------|-------|---------------|--------|
| `L:\_DATA\GoodQ_Data\import_inbox` | 0.00 | 0 | 2025-12-06 | ✅ **ACTIVE (EMPTY)** |
| `L:\goodq4all\import_inbox` | 14,516.23 | 3 | 2025-11-21 | ⚠️ **LEGACY (HAS DATA)** |
| `L:\_ARCHIVE\GoodQ_4_All\import_inbox` | 24,022.16 | 11 | 2025-10-07 | 📦 **ARCHIVED** |

**ISSUE:** Active inbox is empty but legacy inbox has 14.5GB of media files

**RECOMMENDATION:**
```powershell
# Move media from legacy to active
Move-Item L:\goodq4all\import_inbox\* L:\_DATA\GoodQ_Data\import_inbox\
```

### Processing Directories

| Path | Size (MB) | Files | Last Modified | Status |
|------|-----------|-------|---------------|--------|
| `L:\_DATA\GoodQ_Data\processing` | 15,182.73 | 36 | 2025-12-10 | ✅ **ACTIVE** |
| `L:\_DATA\GoodQ_Data\processing_stuck_20251210_065244` | (see workspaces) | | 2025-12-10 | ⚠️ **STUCK WORKSPACE** |
| `L:\goodq4all\data\processing` | 14,917.86 | 2 | 2025-11-15 | ⚠️ **LEGACY (STALE)** |
| `L:\goodq4all\scripts\data\processing` | 0.00 | 0 | 2025-11-15 | ⚠️ **EMPTY LEGACY** |

**ISSUE:** Legacy processing contains 14.9GB of old workspaces

**RECOMMENDATION:**
```powershell
# Archive legacy processing
Move-Item L:\goodq4all\data\processing L:\goodq4all\archive\processing_legacy_20251210
```

### Processed (Output) Directories

| Path | Size (MB) | Files | Status |
|------|-----------|-------|--------|
| `L:\_DATA\GoodQ_Data\processed` | 0.00 | 0 | ✅ **ACTIVE (EMPTY)** |
| `L:\_DATA\video_library\processed` | 0.00 | 0 | ⚠️ **UNKNOWN (WHY?)** |
| `L:\goodq4all\data\processed` | 0.00 | 0 | ⚠️ **LEGACY (EMPTY)** |

**NOTE:** All processed directories are currently empty (expected if no full ingestions completed)

---

## 2. PROCESSING WORKSPACES (VIDEO-SPECIFIC)

### Active Workspaces

| Video | Path | Size | Files | Audio | Frames | Scenes | Manifest | Last Modified |
|-------|------|------|-------|-------|--------|--------|----------|---------------|
| `sample` | `L:\_DATA\GoodQ_Data\processing\sample` | 0.01MB | 1 | ✅ | ✅ | ❌ | ❌ | 2025-12-10 |
| `sample` | `L:\_DATA\GoodQ_Data\processing_stuck_20251210_065244\sample` | 1.58MB | 5 | ✅ | ✅ | ❌ | ✅ | 2025-12-09 |

**ISSUE:** Current `sample` workspace has only 1 file (incomplete)  
**ISSUE:** Stuck workspace from Dec 10 has more complete data (5 files, has manifest)

**RECOMMENDATION:**
- Investigate why current processing is incomplete
- Consider recovering data from stuck workspace if needed

---

## 3. TEMPORAL INDEX STATUS

### Search Results

**FOUND:** 0 `temporal_index.json` files

**SEARCHED LOCATIONS:**
- `L:\goodq4all\**`
- `L:\_DATA\**`

**CONCLUSION:** Phase 6b (temporal index creation) is NOT completing successfully

**EXPECTED LOCATION (per code):**
```
L:\_DATA\GoodQ_Data\processing\<video_id>\temporal_index.json
```

**ISSUE:** This confirms the test failure - temporal indexes are not being written

---

## 4. SCENE MANIFESTS

### Found Manifests

| Path | Size (KB) | Scenes | Last Modified | Status |
|------|-----------|--------|---------------|--------|
| `L:\goodq4all\logs\direct_ingest_workspace\sample\scene_manifest.json` | 29.99 | 2 | 2025-12-08 | ⚠️ **LEGACY (IN LOGS)** |
| `L:\_DATA\GoodQ_Data\processing_stuck_20251210_065244\sample\scene_manifest.json` | 29.91 | 2 | 2025-12-10 | ✅ **RECENT (STUCK)** |

**ISSUE:** Scene manifests ARE being created, but:
1. One ended up in logs directory (wrong)
2. One is in stuck processing workspace (incomplete pipeline)
3. Current processing workspace has NO manifest

**EXPECTED LOCATION:**
```
L:\_DATA\GoodQ_Data\processing\<video_id>\scene_manifest.json
```

---

## 5. LOG LOCATIONS

### Log Directory Summary

| Directory | Files | Size (MB) | Date Range | Status |
|-----------|-------|-----------|------------|--------|
| `L:\goodq4all\logs` | 78 | 2.92 | 2025-10-28 to 2025-12-10 | ✅ **ACTIVE** |
| `L:\goodq4all\data\workflow_logs` | 1 | 0.00 | 2025-11-15 | ⚠️ **LEGACY (ZenML)** |

**CONFIG DECLARES:** `log_dir: L:/goodq4all/logs` ✅ **CORRECT**

**OBSERVATIONS:**
- Logs are correctly written to `L:\goodq4all\logs`
- 78 log files totaling 2.92MB (reasonable)
- One ZenML log in old location (can be archived)

---

## 6. DATABASE FILES

### Database Inventory

| Database | Path | Size (KB) | Last Modified | Status |
|----------|------|-----------|---------------|--------|
| **memory.db** | `L:\_DATA\GoodQ_Data\memory.db` | 1,664 | 2025-12-10 | ✅ **ACTIVE (PRIMARY)** |
| memory.db | `L:\goodq4all\data\memory.db` | 680 | 2025-12-09 | ⚠️ **LEGACY (STALE)** |
| **knowledge_graph.db** | `L:\goodq4all\data\knowledge_graph.db` | 256 | 2025-12-10 | ⚠️ **ACTIVE BUT WRONG LOCATION** |
| knowledge_graph.db | `L:\_DATA\knowledge_graph.db` | 0 | 2025-10-11 | ❌ **EMPTY (EXPECTED LOCATION)** |
| control_memory.db | `L:\goodq4all\data\control_memory.db` | 36 | 2025-12-10 | ⚠️ **ACTIVE (LEGACY LOCATION)** |
| control_memory.db | `L:\goodq4all\data\agent_checkpoints\control_memory.db` | 28 | 2025-12-10 | ⚠️ **DUPLICATE** |
| recovery.db | `L:\goodq4all\data\recovery.db` | 36 | 2025-12-09 | ⚠️ **LEGACY LOCATION** |

**CRITICAL ISSUE:** Knowledge Graph DB is being written to `L:\goodq4all\data\knowledge_graph.db` instead of config-declared `L:\_DATA\GoodQ_Data\knowledge_graph.db`

**CONFIG DECLARES:**
```yaml
db_path: L:/_DATA/GoodQ_Data/memory.db ✅ (correct)
knowledge_graph_db: L:/_DATA/GoodQ_Data/knowledge_graph.db ❌ (not followed)
```

---

## 7. PHASE 6 OUTPUTS & EMBEDDINGS

### FAISS Indices

**FOUND:** 0 FAISS `.faiss` index files

**EXPECTED LOCATION:**
```
L:/_DATA/GoodQ_Data/faiss/ (or faiss_indices/)
```

**ISSUE:** No FAISS indices created yet (expected if ingestion incomplete)

### Qdrant Status

✅ **SERVICE RUNNING:** GoodQ_Qdrant (Windows Service)  
✅ **COLLECTIONS CREATED:** 4/4 (goodq_clip, goodq_dino, goodq_text, goodq_audio)  
✅ **DATA PRESENT:** Qdrant has lock files indicating active use  
✅ **STORAGE LOCATION:** `L:\goodq4all\vendor\qdrant\storage` (relocated from `L:\_DATA\qdrant_storage`)

**NOTE:** Qdrant storage moved itself to vendor directory (standard behavior when run from there)

---

## 8. CONFIG-DECLARED vs. REALITY

### Configuration Analysis (`configs/config.yaml`)

| Config Key | Declared Path | Reality | Match? |
|------------|---------------|---------|--------|
| `data_root` | `L:/_DATA/GoodQ_Data` | ✅ Used | ✅ YES |
| `import_inbox` | `L:/_DATA/GoodQ_Data/import_inbox` | ✅ Exists (empty) | ✅ YES |
| `processing` | `L:/_DATA/GoodQ_Data/processing` | ✅ Active | ✅ YES |
| `models_cache` | `L:/_DATA/models` | (not scanned) | ❓ TBD |
| `log_dir` | `L:/goodq4all/logs` | ✅ Active | ✅ YES |
| `db_path` | `L:/_DATA/GoodQ_Data/memory.db` | ✅ Active (1.6MB) | ✅ YES |
| `knowledge_graph_db` | `L:/_DATA/GoodQ_Data/knowledge_graph.db` | ❌ Empty | ❌ **NO** |

**CONCLUSION:** Config is mostly correct, but Knowledge Graph DB is being written to wrong location

---

## 9. DUPLICATE DETECTION

### Critical Duplicates

1. **Import Inbox:**
   - Active (empty): `L:\_DATA\GoodQ_Data\import_inbox`
   - Legacy (14.5GB): `L:\goodq4all\import_inbox` ← **NEEDS MIGRATION**

2. **Processing:**
   - Active: `L:\_DATA\GoodQ_Data\processing`
   - Legacy (14.9GB): `L:\goodq4all\data\processing` ← **NEEDS ARCHIVING**

3. **Memory Database:**
   - Active: `L:\_DATA\GoodQ_Data\memory.db` (1.6MB)
   - Legacy: `L:\goodq4all\data\memory.db` (680KB) ← **STALE**

4. **Knowledge Graph:**
   - Expected: `L:\_DATA\GoodQ_Data\knowledge_graph.db` (empty)
   - Actual: `L:\goodq4all\data\knowledge_graph.db` (256KB) ← **WRONG LOCATION**

5. **Control Memory:**
   - `L:\goodq4all\data\control_memory.db` (36KB)
   - `L:\goodq4all\data\agent_checkpoints\control_memory.db` (28KB) ← **DUPLICATE**

---

## 10. WSL2 MIRRORING CHECK

**STATUS:** Not scanned (requires WSL2 active session)

**TO CHECK MANUALLY:**
```bash
wsl bash -c "ls -R /mnt/l/_DATA/GoodQ_Data"
wsl bash -c "find /mnt/l -name temporal_index.json"
```

**EXPECTED:** WSL2 should see `/mnt/l/_DATA/GoodQ_Data/` as mirror, but should NOT create parallel directories

---

## 11. ROOT CAUSE ANALYSIS

### Why Temporal Index Isn't Created

**Evidence:**
1. Zero `temporal_index.json` files found anywhere
2. Scene manifests ARE created (2 found)
3. Processing workspaces have partial data

**Hypothesis:** Phase 6b (cross-modal harmonization) is not completing, which is responsible for temporal index generation

**Needs Investigation:**
- Check `pipelines/direct_ingestion.py` Phase 6b call
- Verify `steps/video/cross_modal_harmonization.py` writes temporal index
- Check recent logs for Phase 6b errors

### Why Knowledge Graph in Wrong Location

**Evidence:**
- Config declares: `L:/_DATA/GoodQ_Data/knowledge_graph.db`
- Actually at: `L:\goodq4all\data\knowledge_graph.db`
- File is recent (Dec 10) and has data (256KB)

**Hypothesis:** Code has hardcoded path that overrides config

**Needs Investigation:**
- Grep for `knowledge_graph.db` in `lib/` and `steps/`
- Find where KG is initialized
- Check if config path is being used

---

## 12. RECOMMENDED ACTIONS

### Immediate (Before Next Ingestion)

1. **Migrate Media to Active Inbox:**
   ```powershell
   Move-Item L:\goodq4all\import_inbox\* L:\_DATA\GoodQ_Data\import_inbox\
   ```

2. **Fix Knowledge Graph Path:**
   - Find code creating KG at wrong location
   - Update to use config-declared path
   - OR update config to match actual location

3. **Clean Stuck Processing:**
   ```powershell
   Remove-Item L:\_DATA\GoodQ_Data\processing_stuck_* -Recurse
   ```

### Short Term (This Week)

4. **Archive Legacy Processing:**
   ```powershell
   Move-Item L:\goodq4all\data\processing L:\goodq4all\archive\processing_legacy_20251210
   ```

5. **Consolidate Control Memory:**
   - Determine which control_memory.db is canonical
   - Delete duplicate

6. **Investigate Temporal Index:**
   - Debug Phase 6b completion
   - Ensure temporal_index.json is written to processing dir

### Long Term (Cleanup)

7. **Archive Entire Legacy Data Tree:**
   ```powershell
   Move-Item L:\goodq4all\data L:\goodq4all\archive\data_legacy_20251210
   ```

8. **Remove Empty Legacy Directories:**
   - `L:\goodq4all\data\processed`
   - `L:\goodq4all\scripts\data\`

9. **Document Path Architecture:**
   - Create `docs/FILESYSTEM_ARCHITECTURE.md`
   - Clarify L:/goodq4all (code) vs. L:/_DATA (media/state)

---

## 13. FILESYSTEM ARCHITECTURE (DESIRED STATE)

### Canonical Structure

```
L:\
├── goodq4all\                      # CODE REPOSITORY
│   ├── pipelines\                  # Python code
│   ├── steps\                      # Processing steps
│   ├── cli\                        # Command-line tools
│   ├── configs\                    # Configuration files
│   ├── logs\                       # ✅ Runtime logs (current)
│   ├── vendor\                     # 3rd party binaries (Qdrant)
│   └── archive\                    # Legacy code/data (not active)
│
└── _DATA\                          # DATA STORAGE
    ├── GoodQ_Data\                 # MEDIA & ARTIFACTS
    │   ├── import_inbox\           # ✅ Input videos (should be active)
    │   ├── processing\<video_id>\  # ✅ Active ingestion workspaces
    │   │   ├── audio\              # Audio chunks
    │   │   ├── frames\             # Extracted frames
    │   │   ├── scenes\             # Scene frames
    │   │   ├── scene_manifest.json # Scene metadata
    │   │   └── temporal_index.json # ❌ NOT BEING CREATED
    │   ├── processed\              # Completed ingestions
    │   ├── memory.db               # ✅ Main memory database
    │   └── knowledge_graph.db      # ❌ SHOULD BE HERE (but isn't)
    │
    ├── models\                     # Model cache
    ├── faiss_indices\              # FAISS vector indices
    └── qdrant_storage\             # Qdrant data (relocated to vendor/)
```

---

## 14. SUMMARY OF ISSUES

### CRITICAL (Fix Before Production)

1. ❌ **Temporal index not being created** - Phase 6b incomplete
2. ❌ **Knowledge graph at wrong location** - Code not using config path
3. ⚠️ **Media in wrong inbox** - 14.5GB sitting in legacy location

### IMPORTANT (Fix This Week)

4. ⚠️ **Legacy processing consuming 14.9GB** - Should be archived
5. ⚠️ **Duplicate control_memory.db** - Two active copies
6. ⚠️ **Stuck processing workspace** - Cleanup needed

### MINOR (Cleanup Later)

7. 📦 **Empty legacy directories** - Safe to remove
8. 📦 **Old ZenML logs** - Can be archived

---

## 15. NEXT STEPS FOR INVESTIGATION

1. **Grep for temporal_index writes:**
   ```bash
   grep -rn "temporal_index" pipelines/ steps/
   ```

2. **Grep for knowledge_graph.db path:**
   ```bash
   grep -rn "knowledge_graph.db" lib/ steps/
   ```

3. **Check Phase 6b logs:**
   ```bash
   tail -100 logs/direct_ingest_*.log | grep -i "phase.6"
   ```

4. **Test manual temporal index creation:**
   - Run Phase 6b step standalone
   - Verify file creation location

---

**END OF AUDIT REPORT**

**Generated:** 2025-12-10 18:15 UTC  
**Mode:** Read-only reconnaissance  
**Files Scanned:** 1000+ files across L:\ drive  
**No modifications made**

