<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_CANONICAL_POINTER: docs/architecture/MEMORY_STORAGE.md -->
<!-- DOC_ARCHIVED_ON: 2026-02-12 -->

# MEMORY CLEANUP STAGE 1 — RECON RESULTS
**Generated:** 2025-12-10 18:45 UTC  
**Mode:** NON-DESTRUCTIVE RECONNAISSANCE  
**Status:** SCAN COMPLETE - NO MODIFICATIONS MADE

---

## INBOXES:
--------
[ACTIVE] L:\_DATA\GoodQ_Data\import_inbox
        Size: 0 GB | Files: 0 | Modified: 2025-12-06 01:51
[LEGACY] L:\goodq4all\import_inbox
        Size: 14.18 GB | Files: 3 | Modified: 2025-11-21 12:28
[ARCHIVE] L:\_ARCHIVE\GoodQ_4_All\import_inbox
        Size: 23.46 GB | Files: 11 | Modified: 2025-10-07 20:24

**ISSUE:** Active inbox is EMPTY but legacy inbox has 14.18 GB of media (3 files)

---

## PROCESSING:
-----------
[ACTIVE] L:\_DATA\GoodQ_Data\processing
         Size: 14.83 GB | Files: 36
[LEGACY] L:\goodq4all\data\processing
         Size: 14.57 GB | Files: 2
[LEGACY] L:\goodq4all\scripts\data\processing
         Size: 0 GB | Files: 0
[STUCK] L:\_DATA\GoodQ_Data\processing_stuck_20251210_065244
        Size: 7.3 GB | Files: 10 | Date: 2025-12-10 06:52

**ISSUE:** 
- Legacy processing consuming 14.57 GB (stale data)
- Stuck workspace from Dec 10 consuming 7.3 GB

---

## TEMPORAL INDEX:
---------------
[FOUND] 0 temporal_index.json files
[MISSING] Expected at: L:\_DATA\GoodQ_Data\processing\<video_id>\temporal_index.json
[STATUS] ❌ Phase 6b NOT completing - temporal indexes not being created

**CRITICAL:** This confirms the test failure - Phase 6b cross-modal harmonization is not completing

---

## SCENE MANIFESTS:
----------------
[FOUND] 2 scene_manifest.json files:
  [WRONG LOCATION] L:\goodq4all\logs\direct_ingest_workspace\sample\scene_manifest.json (29.99 KB)
  [LEGACY] L:\_DATA\GoodQ_Data\processing_stuck_20251210_065244\sample\scene_manifest.json (29.91 KB)

**ISSUE:** Scene manifests exist but in wrong locations (logs dir and stuck workspace)

---

## KG & DATABASES:
---------------
[LEGACY] control_memory.db
          Path: L:\goodq4all\data\control_memory.db
          Size: 36 KB | Modified: 2025-12-10 15:45
[WRONG LOCATION (should be L:\_DATA\GoodQ_Data\)] knowledge_graph.db
          Path: L:\goodq4all\data\knowledge_graph.db
          Size: 256 KB | Modified: 2025-12-10 15:43
[LEGACY] memory.db
          Path: L:\goodq4all\data\memory.db
          Size: 680 KB | Modified: 2025-12-09 21:33
[LEGACY] control_memory.db
          Path: L:\goodq4all\data\agent_checkpoints\control_memory.db
          Size: 28 KB | Modified: 2025-12-10 07:03
[LEGACY] knowledge_graph.db
          Path: L:\_DATA\knowledge_graph.db
          Size: 0 KB | Modified: 2025-10-11 10:24
[ACTIVE] memory.db
          Path: L:\_DATA\GoodQ_Data\memory.db
          Size: 1664 KB | Modified: 2025-12-10 15:45

**CRITICAL ISSUE:** 
- Knowledge Graph DB at WRONG LOCATION: `L:\goodq4all\data\knowledge_graph.db` (256 KB, ACTIVE)
- Config declares: `L:\_DATA\GoodQ_Data\knowledge_graph.db` (0 KB, EMPTY)
- Code is ignoring config path and using hardcoded legacy path

**Duplicates Found:**
- 2x control_memory.db (36 KB + 28 KB)
- 2x memory.db (1664 KB active + 680 KB stale)
- 2x knowledge_graph.db (256 KB wrong location + 0 KB correct location)

---

## QDRANT:
-------
[ACTIVE] Storage root: L:\goodq4all\vendor\qdrant\storage
         Size: 259.89 MB
         Collections: 4 found
           - goodq_audio
           - goodq_clip
           - goodq_dino
           - goodq_text
[OK] L:\_DATA\qdrant_storage is empty (correct)
[SERVICE] Status: Running | Startup: Automatic

**STATUS:** ✅ Qdrant is OPERATIONAL
- Storage correctly located in vendor/qdrant/storage
- All 4 collections created and active
- 259.89 MB of data stored (embeddings present)
- Windows service running and auto-starts

---

## FAISS (DEPRECATED):
-------------------
[DEPRECATED] 7 FAISS files found:
  - L:\_ARCHIVE\old_goodq_data_20251010_225307\faiss_indices\audio\faiss_audio.index (27.36 KB)
  - L:\_ARCHIVE\old_goodq_data_20251010_225307\faiss_indices\dino\faiss_dino.index (49.15 KB)
  - L:\_ARCHIVE\old_goodq_data_20251010_225307\faiss_indices\text\faiss_text.index (24.88 KB)
  - L:\_DATA\GoodQ_Data\faiss_indices\audio\faiss_audio.index (27.36 KB)
  - L:\_DATA\GoodQ_Data\faiss_indices\dino\faiss_dino.index (49.15 KB)
  - L:\_DATA\GoodQ_Data\faiss_indices\text\faiss_text.index (24.88 KB)
  - L:\goodq4all\data\faiss_indices\audio\faiss_audio.index (115.57 KB)

**STATUS:** FAISS is deprecated in favor of Qdrant
**ACTION NEEDED:** These can be archived (not deleted) once Qdrant is confirmed working

---

## WSL2 MIRRORS:
-------------
[ACTIVE] /mnt/l/_DATA/GoodQ_Data accessible
[STATUS] WSL2 can see Windows filesystem correctly

**STATUS:** ✅ WSL2 properly mounted, no shadow directories detected

---

## SUMMARY OF FINDINGS

### ✅ CORRECT:
1. Config points to `L:\_DATA\GoodQ_Data` (active inbox, processing, memory.db)
2. Qdrant operational with 4 collections and 259 MB of data
3. WSL2 mirrors working correctly
4. Main memory.db at correct location (1.6 MB)

### ❌ CRITICAL ISSUES:
1. **Temporal indexes NOT being created** (0 found, Phase 6b failing)
2. **Knowledge Graph at WRONG location** (code ignoring config)
3. **14.18 GB media in WRONG inbox** (legacy instead of active)

### ⚠️ IMPORTANT:
4. **Legacy processing: 14.57 GB** (needs archiving)
5. **Stuck workspace: 7.3 GB** (needs cleanup)
6. **Duplicate databases** (control_memory, memory.db duplicates)
7. **FAISS deprecated** (7 files can be archived)

### 📦 MINOR:
8. Empty legacy directories (can be removed)
9. Scene manifests in wrong locations (fixable)

---

## DISK SPACE BREAKDOWN

**Total Duplicated/Legacy Data:**
- Legacy inbox: 14.18 GB
- Legacy processing: 14.57 GB
- Stuck processing: 7.3 GB
- FAISS indices: ~0.3 MB (negligible)
- **TOTAL: ~36 GB recoverable**

**Active Data:**
- Active processing: 14.83 GB
- Active memory.db: 1.66 MB
- Qdrant storage: 259.89 MB
- **TOTAL: ~15.1 GB in use**

---

## NEXT STEPS: STAGE 2

Stage 2 will compare config declarations vs. actual filesystem usage to identify code that needs patching.

**NO MODIFICATIONS WERE MADE IN STAGE 1**
**ALL DATA PRESERVED EXACTLY AS SCANNED**

---

**End of Stage 1 Report**
