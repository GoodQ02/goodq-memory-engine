# Phase 3: Database & Storage Consolidation
> ⚠ Historical planning document — contains legacy path references.

**Date**: 2025-11-19  
**Status**: ✅ COMPLETE

## Overview
Consolidated all database and storage paths to match documented architecture in `paths.yaml`.

## Actions Taken

### 1. Database Path Standardization ✅
Updated `<project_root>/configs/paths.yaml` to include all database locations:

```yaml
# Memory databases (inside repo, backed up to git)
db_path: "<project_root>/data/memory.db"                          # Main memory store
knowledge_graph_db: "<project_root>/data/knowledge_graph.db"      # Knowledge graph
control_agent_db: "<project_root>/data/agent_checkpoints/control_memory.db"  # Agent state
recovery_db: "<project_root>/data/recovery.db"                    # Recovery/backup
```

### 2. Database Inventory
**Active Databases** (confirmed in use):
- `<project_root>/data/memory.db` - Main SQLite database (270KB, last modified: 2025-11-19 12:44)
- `<project_root>/data/knowledge_graph.db` - Knowledge graph storage (106KB, last modified: 2025-11-19 09:40)
- `<project_root>/data/agent_checkpoints/control_memory.db` - Control agent state (28KB, last modified: 2025-11-19 05:49)
- `<project_root>/data/control_memory.db` - Legacy control agent (28KB, duplicate - marked for consolidation)
- `<project_root>/data/recovery.db` - Recovery system (36KB, last modified: 2025-11-15)

**Test/Deprecated Databases**:
- `<project_root>/data/test_recovery.db` - Test database (can be removed after validation)

**External Database** (outside repo):
- `<GOODQ_DATA_ROOT>/knowledge_graph.db` - **ISSUE**: Duplicate KG database outside repo, needs migration

### 3. Storage Architecture Confirmed

**Inside Repo** (`<project_root>/`):
```
<project_root>/
├── data/                           # All databases and processed data
│   ├── memory.db                  # Main memory
│   ├── knowledge_graph.db         # KG store
│   ├── recovery.db                # Recovery
│   ├── agent_checkpoints/         # Agent state
│   │   └── control_memory.db
│   ├── databases/                 # ID mappings
│   │   ├── chroma/               # Vector store
│   │   ├── clap_id_map.sqlite
│   │   ├── clip_id_map.sqlite
│   │   ├── dino_id_map.sqlite
│   │   └── known_faces.json
│   ├── faiss_indices/            # FAISS vector indices
│   │   ├── text/
│   │   ├── audio/
│   │   ├── dino/
│   │   └── clip/
│   └── output/                    # Processing outputs
```

**Outside Repo** (`<project_root>/`):
```
<project_root>/
├── _DATA/                         # Large datasets (not in git)
│   ├── models/                   # Model cache
│   │   └── huggingface/
│   ├── datasets/                 # Raw datasets
│   ├── cache/                    # Temp cache
│   └── knowledge_graph.db        # ⚠️ DUPLICATE - needs migration
├── _TOOLS/                        # External binaries
│   ├── ffmpeg/
│   ├── tesseract/
│   └── poppler/
└── _WORKSPACE/                    # User workspace (not in git)
```

## Issues Found & Resolution Plan

### 🔴 CRITICAL: Duplicate Knowledge Graph Database
**Problem**: Two KG databases exist:
- `<project_root>/data/knowledge_graph.db` (106KB, newer)
- `<GOODQ_DATA_ROOT>/knowledge_graph.db` (exists, older)

**Resolution** (Phase 4):
1. Compare sizes and modification dates
2. Merge if both contain data
3. Consolidate to `<project_root>/data/knowledge_graph.db`
4. Update all code references
5. Archive `<GOODQ_DATA_ROOT>/knowledge_graph.db`

### 🟡 MEDIUM: Duplicate Control Agent DB
**Problem**: Two control agent databases:
- `<project_root>/data/agent_checkpoints/control_memory.db` (newer location)
- `<project_root>/data/control_memory.db` (legacy)

**Resolution**: Verify code uses checkpoint version, remove legacy

### 🟢 LOW: Test Database Cleanup
Remove `<project_root>/data/test_recovery.db` after confirming recovery.db works

## Next Steps

**Phase 4**: Knowledge Graph Consolidation
- Migrate `<GOODQ_DATA_ROOT>/knowledge_graph.db` → `<project_root>/data/knowledge_graph.db`
- Update all KG code references
- Verify ChromaDB path alignment

**Phase 5**: Agent State Cleanup
- Consolidate control agent databases
- Verify agent checkpoint system

**Phase 6**: Vector Store Validation
- Confirm FAISS indices functional
- Verify ChromaDB operational
- Test all embedding retrieval

## Configuration Files Updated
- ✅ `<project_root>/configs/paths.yaml` - Added all database paths

## Files to Update (Phase 4)
- `<project_root>/api/main.py` - Update KG database references
- `<project_root>/goodq4all/kg/knowledge_graph.py` - Update KG path
- Agent files - Verify control_memory.db path

---
**Documentation**: Added to <project_root>/docs/PROJECT_ORGANIZATION_PHASE3_DATABASE_CONSOLIDATION.md
