<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_ARCHIVED_ON: 2026-02-12 -->

# STAGE 2 — CONFIG & CODE CROSSCHECK RESULTS
**Generated:** 2025-12-10 18:56 UTC  
**Mode:** READ-ONLY ANALYSIS  
**Status:** SCAN COMPLETE - NO MODIFICATIONS MADE

---

## 1. CONFIG VALUES (canonical from config.yaml):

```yaml
data_root:           L:/_DATA/GoodQ_Data
import_inbox:        L:/_DATA/GoodQ_Data/import_inbox
processing:          L:/_DATA/GoodQ_Data/processing
models_cache:        L:/_DATA/models
log_dir:             L:/goodq4all/logs
db_path:             L:/_DATA/GoodQ_Data/memory.db
knowledge_graph_db:  L:/_DATA/GoodQ_Data/knowledge_graph.db
```

---

## 2. CRITICAL PATH MISMATCHES FOUND

### 🔴 CRITICAL #1: Knowledge Graph DB Path Conflict

**Multiple conflicting declarations found:**

| Source | Declared Path | Reality |
|--------|---------------|---------|
| `config.yaml` | `L:/_DATA/GoodQ_Data/knowledge_graph.db` | Empty (0 KB) |
| `configs/paths.py` line 36 | `DATABASE_DIR / "knowledge_graph.db"` | → `L:/_DATA/GoodQ_Data/databases/knowledge_graph.db` |
| **ACTUAL USAGE** | **`L:\goodq4all\data\knowledge_graph.db`** | **256 KB (ACTIVE!)** |

**Files using WRONG hardcoded path:**
- `scripts/utils/check_kg_schema.py:8` → `L:\\goodq4all\\data\\knowledge_graph.db`
- `scripts/show_kg_insights.py:11` → `data/knowledge_graph.db` (relative to L:\goodq4all)

**Files using CORRECT config path:**
- `api/main.py:718` → `L:/_DATA/GoodQ_Data/knowledge_graph.db` ✅
- `cli/graph_query.py:18` → `L:/_DATA/GoodQ_Data/knowledge_graph.db` ✅
- `cli/run_ingestion.py:131` → `data_dir / 'knowledge_graph.db'` ✅ (uses config)
- `scripts/build_knowledge_graph_from_db.py:80` → `L:/_DATA/GoodQ_Data/knowledge_graph.db` ✅

**ROOT CAUSE:** Code in `steps/graph_builder/graph_builder.py:33` uses:
```python
graph_db_path = Path(config.get('data_dir', 'data')) / 'knowledge_graph.db'
```
When `data_dir` is not set or defaults to `'data'`, this creates `data/knowledge_graph.db` relative to project root = `L:\goodq4all\data\knowledge_graph.db` ❌

**Severity:** **CRITICAL** - This is why KG is at wrong location

---

### 🔴 CRITICAL #2: Import Inbox Path Mismatch

**In `configs/paths.py` line 64:**
```python
IMPORT_INBOX = PROJECT_ROOT / "import_inbox"  # = L:/goodq4all/import_inbox ❌
```

**This should be:**
```python
IMPORT_INBOX = DATA_ROOT / "import_inbox"  # = L:/_DATA/GoodQ_Data/import_inbox ✅
```

**Reality:**
- Legacy inbox `L:\goodq4all\import_inbox`: 14.18 GB, 3 files (ACTIVE!)
- Correct inbox `L:\_DATA\GoodQ_Data\import_inbox`: 0 GB, 0 files (EMPTY!)

**Severity:** **CRITICAL** - Watchdog scanning wrong directory

---

### 🟡 IMPORTANT #3: Legacy Data Path References

**8 files still reference `L:\goodq4all\data`:**

| File | Line | Reference |
|------|------|-----------|
| `scripts/analyze_sample_output.py` | 7 | `L:\\goodq4all\\data\\memory.db` |
| `tests/test_segment_text.py` | 7 | `L:\\goodq4all\\data\\memory.db` |
| `scripts/utils/check_db_schema.py` | 7 | `L:\\goodq4all\\data\\memory.db` |
| `scripts/utils/check_kg_schema.py` | 8 | `L:\\goodq4all\\data\\knowledge_graph.db` |
| `scripts/utils/check_sample_data.py` | 8 | `L:\\goodq4all\\data\\goodq_memory.db` |
| `scripts/utils/check_scene_meta.py` | 7 | `L:\\goodq4all\\data\\memory.db` |
| `scripts/utils/verify_phase1_fix.py` | 7 | `L:\\goodq4all\\data\\memory.db` |
| `scripts/fix_all_paths.py` | 20 | Has mapping rule but not applied everywhere |

**Severity:** **MEDIUM** - These are utility/test scripts, not core pipeline

---

## 3. HARDCODED PATHS DISCOVERED

### Paths That Should Use Config

**47 instances of `knowledge_graph.db` references found**

**Breakdown:**
- ✅ **Correct** (using `L:/_DATA/GoodQ_Data/` or config): 35 files
- ❌ **Wrong** (using `data/knowledge_graph.db` or `L:\goodq4all\data\`): 12 files

**Most Critical Wrong Reference:**
```python
# steps/graph_builder/graph_builder.py:33
graph_db_path = Path(config.get('data_dir', 'data')) / 'knowledge_graph.db'
```
The `'data'` fallback is the problem! Should be:
```python
graph_db_path = Path(config.get('knowledge_graph_db', 'L:/_DATA/GoodQ_Data/knowledge_graph.db'))
```

---

## 4. PHASE 6 TEMPORAL INDEX ISSUES

### Temporal Index Write Locations

**15 files reference `temporal_index.json`**

**Critical file:** `steps/video/cross_modal_harmonizer.py:255`
```python
temporal_index_path = os.path.join(processing_dir, 'temporal_index.json')
```

**Analysis:**
- ✅ This is **CORRECT** - writes to `processing_dir/temporal_index.json`
- ✅ `processing_dir` comes from config (`L:/_DATA/GoodQ_Data/processing/<video>`)

**But in `pipelines/direct_ingestion.py:108-111`:**
```python
temporal_index_path = processing_dir / "temporal_index.json"
# ... fallback to:
temporal_index_path = processing_dir / "metadata" / "temporal_index.json"
```

**The fallback to `/metadata/` subdirectory might be causing path confusion!**

### Why Temporal Indexes Aren't Created

**Probable Causes (requires deeper investigation):**

1. **Phase 6b `cross_modal_harmonizer.py` may not be called at all**
   - Check if Phase 6b step is registered in pipeline
   - Check if it's being skipped due to error handling

2. **Directory creation issue**
   - The `processing_dir` may not exist when harmonizer tries to write
   - Need to verify `processing_dir.mkdir(parents=True, exist_ok=True)` is called

3. **Silent exception swallowing**
   - Check for `try/except` blocks that suppress write errors

**Severity:** **CRITICAL** - This is why temporal indexes don't exist

---

## 5. KNOWLEDGE GRAPH PATH ISSUES (DETAILED)

### The Exact Problem

**In `steps/graph_builder/graph_builder.py:33`:**
```python
graph_db_path = Path(config.get('data_dir', 'data')) / 'knowledge_graph.db'
```

**What happens:**
1. Config is loaded
2. Code looks for `config['data_dir']`
3. **Config has `data_root` not `data_dir`** ← KEY MISMATCH
4. Falls back to `'data'` (relative path)
5. Creates `Path('data') / 'knowledge_graph.db'` = `data/knowledge_graph.db`
6. Relative to current working directory = `L:\goodq4all\data\knowledge_graph.db` ❌

**Fix Required:**
```python
# OLD (WRONG):
graph_db_path = Path(config.get('data_dir', 'data')) / 'knowledge_graph.db'

# NEW (CORRECT):
graph_db_path = Path(config.get('knowledge_graph_db', 
                               'L:/_DATA/GoodQ_Data/knowledge_graph.db'))
```

**Location of mismatch:** Line 33 of `steps/graph_builder/graph_builder.py`

**Severity:** **CRITICAL** - Single line fix will solve entire KG path issue

---

## 6. PROCESSING PATH MISMATCHES

### Legacy Directory References

**No active code referencing legacy processing paths** ✅

All code correctly uses:
- `config['processing']` → `L:/_DATA/GoodQ_Data/processing`
- `configs/paths.py` → `PROCESSING_DIR = DATA_ROOT / "processing"`

**However:** `configs/paths.py` has contradiction:
```python
PROCESSING_DIR = DATA_ROOT / "processing"  # ✅ Correct (L:/_DATA/GoodQ_Data/processing)
IMPORT_INBOX = PROJECT_ROOT / "import_inbox"  # ❌ Wrong (L:/goodq4all/import_inbox)
```

The `IMPORT_INBOX` needs to be changed to:
```python
IMPORT_INBOX = DATA_ROOT / "import_inbox"  # ✅ Correct
```

---

## 7. WSL2 PATH ISSUES

**Status:** ✅ **NO ISSUES DETECTED**

- WSL2 correctly mounts `L:\_DATA\GoodQ_Data` as `/mnt/l/_DATA/GoodQ_Data`
- No shadow directories detected
- `configs/paths.py` has proper `drive_path()` function for cross-platform compatibility

---

## 8. configs/paths.py ANALYSIS

**This file defines canonical paths but has 2 critical errors:**

### ❌ Error #1: Wrong IMPORT_INBOX (Line 64)
```python
# CURRENT (WRONG):
IMPORT_INBOX = PROJECT_ROOT / "import_inbox"  # L:/goodq4all/import_inbox

# SHOULD BE:
IMPORT_INBOX = DATA_ROOT / "import_inbox"  # L:/_DATA/GoodQ_Data/import_inbox
```

### ❌ Error #2: Wrong KNOWLEDGE_GRAPH_DB Path (Line 36)
```python
# CURRENT:
DATABASE_DIR = DATA_ROOT / "databases"  # L:/_DATA/GoodQ_Data/databases
KNOWLEDGE_GRAPH_DB = DATABASE_DIR / "knowledge_graph.db"  # ...databases/knowledge_graph.db

# PROBLEM: config.yaml says L:/_DATA/GoodQ_Data/knowledge_graph.db (no databases/ subdir)
# These don't match!

# SHOULD BE (to match config.yaml):
KNOWLEDGE_GRAPH_DB = DATA_ROOT / "knowledge_graph.db"  # L:/_DATA/GoodQ_Data/knowledge_graph.db
```

### ✅ Correct Paths in `configs/paths.py`:
- `DATA_ROOT` ✅
- `PROCESSING_DIR` ✅  
- `COMPLETED_DIR` ✅
- `LOGS_DIR` ✅ (but points to DATA_ROOT/logs, config says L:/goodq4all/logs - minor)
- `FAISS_DIR` ✅
- `MODELS_DIR` ✅

---

## SUMMARY

### Critical Issues: 3

1. **Knowledge Graph DB path mismatch**
   - `steps/graph_builder/graph_builder.py:33` uses wrong config key
   - Falls back to `data/` instead of `L:/_DATA/GoodQ_Data/`
   - **FIX:** Change `config.get('data_dir', 'data')` to `config.get('knowledge_graph_db', ...)`

2. **Import inbox wrong location**
   - `configs/paths.py:64` points to `L:/goodq4all/import_inbox` (legacy)
   - **FIX:** Change `PROJECT_ROOT / "import_inbox"` to `DATA_ROOT / "import_inbox"`

3. **Temporal index creation failing**
   - Likely cause: Phase 6b not executing or silently failing
   - **NEEDS:** Debug `cross_modal_harmonizer.py` execution

### Medium Issues: 2

4. **8 utility scripts** reference `L:\goodq4all\data` (legacy)
   - **FIX:** Update hardcoded paths to use config

5. **configs/paths.py DATABASE_DIR mismatch**
   - Defines `databases/` subdirectory not used by config.yaml
   - **FIX:** Align with config.yaml (no subdirectory)

### Minor Issues: 1

6. **LOGS_DIR** points to DATA_ROOT but config says PROJECT_ROOT
   - Current behavior (PROJECT_ROOT/logs) is working
   - Just a documentation mismatch

---

## RECOMMENDED FIXES (In Priority Order)

### 1. Fix Knowledge Graph Path (CRITICAL - 1 line change)
**File:** `steps/graph_builder/graph_builder.py`  
**Line:** 33  
**Change:**
```python
# FROM:
graph_db_path = Path(config.get('data_dir', 'data')) / 'knowledge_graph.db'

# TO:
graph_db_path = Path(config.get('knowledge_graph_db', 'L:/_DATA/GoodQ_Data/knowledge_graph.db'))
```

### 2. Fix Import Inbox Path (CRITICAL - 1 line change)
**File:** `configs/paths.py`  
**Line:** 64  
**Change:**
```python
# FROM:
IMPORT_INBOX = PROJECT_ROOT / "import_inbox"

# TO:
IMPORT_INBOX = DATA_ROOT / "import_inbox"
```

### 3. Align configs/paths.py KNOWLEDGE_GRAPH_DB (MEDIUM - 2 line change)
**File:** `configs/paths.py`  
**Lines:** 34-36  
**Change:**
```python
# FROM:
DATABASE_DIR = DATA_ROOT / "databases"
MEMORY_DB = DATABASE_DIR / "memory.db"
KNOWLEDGE_GRAPH_DB = DATABASE_DIR / "knowledge_graph.db"

# TO:
MEMORY_DB = DATA_ROOT / "memory.db"
KNOWLEDGE_GRAPH_DB = DATA_ROOT / "knowledge_graph.db"
# (Remove DATABASE_DIR entirely or repurpose)
```

### 4. Update Legacy Path References (MEDIUM - 8 files)
Update utility scripts to use config paths instead of hardcoded `L:\goodq4all\data`

### 5. Debug Temporal Index Creation (CRITICAL - Investigation needed)
- Add logging to `cross_modal_harmonizer.py`
- Verify Phase 6b is being called
- Check for silent exception handling
- Verify processing_dir exists before write

---

## NEXT STEP: STAGE 3

Stage 3 will generate the migration script based on these findings, including:
- Moving KG database to correct location
- Updating code references
- Migrating media to correct inbox
- Archiving legacy paths

**NO MODIFICATIONS WERE MADE IN STAGE 2**
**ALL FINDINGS ARE RECONNAISSANCE ONLY**

---

**End of Stage 2 Report**
