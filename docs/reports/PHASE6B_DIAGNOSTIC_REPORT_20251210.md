# PHASE 6B DIAGNOSTIC REPORT
**Generated:** 2025-12-10 19:43 UTC  
**Mode:** READ-ONLY RECONNAISSANCE  
**Status:** ROOT CAUSE IDENTIFIED

---

## 1. PHASE 6B MAIN ENTRY POINT

### Primary Function
**File:** `steps/video/cross_modal_harmonizer.py`  
**Function:** `run_cross_modal_harmonization(item, cfg)` (Line 96)

**Function Signature:**
```python
def run_cross_modal_harmonization(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 6 harmonization: Fuse all modalities into unified temporal index.
    
    This step combines:
    - Video scenes (Phase 5)
    - Scene visual embeddings (Phase 6)
    - Audio segmentation (Phase 3)
    - Transcripts (audio pipeline)
    - Diarization (speaker IDs)
    - Object detection (from frames)
    - Metadata tags
    
    Into a single multimodal temporal index suitable for retrieval.
    """
```

### Key Implementation Details (Lines 96-271)

**1. Processing Directory Construction (Lines 122-123):**
```python
data_root = cfg.get('data_root', 'L:/_DATA/GoodQ_Data')
processing_dir = os.path.join(data_root, 'processing', video_id)
```

**2. Data Loading (Lines 127-157):**
- Scene manifest: `processing_dir/video/scene_manifest.json`
- Audio segmentation: `processing_dir/audio/segmentation.json`
- Transcript: `processing_dir/audio/transcript.json`
- Diarization: `processing_dir/audio/diarization.json`
- Objects: `processing_dir/video/detected_objects.json`

**3. Temporal Index Creation & Writing (Lines 253-262):**
```python
# === SAVE TEMPORAL INDEX ===

temporal_index_path = os.path.join(processing_dir, 'temporal_index.json')
os.makedirs(os.path.dirname(temporal_index_path), exist_ok=True)

with open(temporal_index_path, 'w', encoding='utf-8') as f:
    json.dump(temporal_index, f, indent=2)

logger.info(f"[HARMONIZER] [OK] Created temporal index with {len(unified_segments)} multimodal segments")
logger.info(f"  Saved: {temporal_index_path}")
```

**4. Return Value (Lines 264-271):**
```python
return {
    'harmonization_status': 'complete',
    'temporal_index_path': temporal_index_path,
    'unified_segments': len(unified_segments),
    'has_visual': temporal_index['has_visual_embeddings'],
    'has_audio': temporal_index['has_audio'],
    'has_transcripts': temporal_index['has_transcripts']
}
```

---

## 2. TEMPORAL INDEX WRITE LOGIC

### Write Location (Line 255)
```python
temporal_index_path = os.path.join(processing_dir, 'temporal_index.json')
```

**Expected Path Structure:**
```
L:\_DATA\GoodQ_Data\processing\<video_id>\temporal_index.json
```

### Directory Creation (Line 256)
```python
os.makedirs(os.path.dirname(temporal_index_path), exist_ok=True)
```

**Analysis:**
- ✅ Directory creation is present
- ✅ Uses `exist_ok=True` (won't fail if exists)
- ✅ Creates parent directory before write

### File Write (Lines 258-259)
```python
with open(temporal_index_path, 'w', encoding='utf-8') as f:
    json.dump(temporal_index, f, indent=2)
```

**Analysis:**
- ✅ Standard file write (not wrapped in try/except at this level)
- ✅ Uses context manager (safe)
- ✅ UTF-8 encoding specified
- ⚠️ **NO try/except around write** - errors will propagate

---

## 3. PROCESSING_DIR ORIGIN

### In Harmonizer (Lines 122-123)
```python
data_root = cfg.get('data_root', 'L:/_DATA/GoodQ_Data')
processing_dir = os.path.join(data_root, 'processing', video_id)
```

**video_id Source (Lines 119-120):**
```python
video_path = item.get('source_path')
video_id = item.get('id', Path(video_path).stem if video_path else 'unknown')
```

### In Pipeline (cli/run_ingestion.py Lines 1275-1279)
```python
phase6_item = {
    'video_id': video_hash,
    'video_path': str(video_path),
    'processing_dir': str(video_workspace),
    'scene_manifest_path': str(video_workspace / 'scene_manifest.json'),
    'scenes': scene_outputs,
```

**Critical Discovery:**
- Pipeline passes: `'video_id': video_hash`
- Pipeline passes: `'processing_dir': str(video_workspace)`
- But harmonizer **IGNORES** the passed `processing_dir`!
- Harmonizer reconstructs it from `video_id`

**Path Mismatch Scenario:**
1. Pipeline uses `video_hash` (e.g., `abc123def`)
2. Pipeline creates workspace: `L:\_DATA\GoodQ_Data\processing\abc123def`
3. Harmonizer receives `item['id'] = 'abc123def'`
4. Harmonizer constructs: `L:\_DATA\GoodQ_Data\processing\abc123def`
5. ✅ **Paths SHOULD match**

---

## 4. METADATA FALLBACK PATHS

### In direct_ingestion.py (Lines 108-111)
```python
temporal_index_path = processing_dir / "temporal_index.json"
if not temporal_index_path.exists():
    # Also check in metadata subdirectory
    temporal_index_path = processing_dir / "metadata" / "temporal_index.json"
```

**Analysis:**
- This is a **READ** fallback, not a write path
- Harmonizer writes to: `processing_dir/temporal_index.json` (root level)
- Pipeline checks: `processing_dir/temporal_index.json` first (correct)
- Then falls back to: `processing_dir/metadata/temporal_index.json` (legacy)

**No Issue Here** - Harmonizer writes to correct location

---

## 5. KG LOAD PATHS

### In Harmonizer (No KG Loading)
- ✅ Harmonizer does NOT load knowledge_graph.db
- ✅ Harmonizer only loads JSON files (scene manifest, audio data, etc.)
- ✅ No legacy KG path references in harmonizer

### Knowledge Graph Is Used By:
- `steps/graph_builder/graph_builder.py` (separate step)
- Not involved in temporal index creation

**No Issue Here** - KG paths not relevant to Phase 6b

---

## 6. SILENT ERROR BLOCKS

### In Harmonizer (load_json_safe, Lines 16-24)
```python
def load_json_safe(path: str) -> Optional[Dict[str, Any]]:
    """Safely load JSON file with error handling."""
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load {path}: {e}")
    return None
```

**Analysis:**
- ⚠️ **POTENTIAL ISSUE**: Returns `None` on error
- Used for loading scene manifest (Line 131)
- Used for loading audio data (Lines 141, 146, 151, 156)

**Critical Check (Lines 133-135):**
```python
if not scene_data:
    logger.warning("No scene manifest found, skipping harmonization")
    return {"harmonization_status": "skipped", "reason": "no_scene_manifest"}
```

**ROOT CAUSE CANDIDATE #1:**
If scene manifest doesn't exist or fails to load:
- Harmonizer returns early with "skipped" status
- **NO temporal index is created**
- Pipeline continues without error

### In Pipeline (cli/run_ingestion.py Lines 1308-1343)

**Try Block (Lines 1308-1340):**
```python
try:
    # Phase 6a: Scene Visual Embeddings (CLIP + DINO)
    typer.echo('[PHASE 6a] Generating scene visual embeddings...')
    embeddings_result = _run_step('goodq_core', 'scene_visual_embeddings', phase6_item, cfg_json)
    if isinstance(embeddings_result, dict):
        phase6_item.update(embeddings_result)
        typer.echo('[PHASE 6a] [PASS] Visual embeddings complete')
    
    # Phase 6b: Cross-Modal Harmonization
    typer.echo('[PHASE 6b] Running multimodal harmonization...')
    harmonization_result = _run_step('goodq_core', 'cross_modal_harmonization', phase6_item, cfg_json)
    if isinstance(harmonization_result, dict):
        phase6_item.update(harmonization_result)
        # Load temporal index from file if path provided
        temporal_index_path = harmonization_result.get('temporal_index_path')
        if temporal_index_path and os.path.exists(temporal_index_path):
            with open(temporal_index_path, 'r', encoding='utf-8') as f:
                video_result['temporal_index'] = json.load(f)
        
        video_result['phase6_complete'] = True
        typer.echo('[PHASE 6b] [PASS] Harmonization complete')
        
        # Also load from harmonization_result if available
        if 'temporal_index' in harmonization_result:
            temporal_index = harmonization_result.get('temporal_index')
            
            # Create temporal_index_path if harmonizer didn't provide one
            if temporal_index and not temporal_index_path:
                temporal_index_path = video_workspace / 'temporal_index.json'
                with open(temporal_index_path, 'w', encoding='utf-8') as f:
                    json.dump(temporal_index, f, indent=2)
                typer.echo(f'[PHASE 6] [PASS] Temporal index written: {temporal_index_path}')

except Exception as phase6_error:
    typer.echo(f'[PHASE 6] [FAIL] Phase 6 failed: {phase6_error}', err=True)
    video_result['phase6_error'] = str(phase6_error)
    video_result['phase6_complete'] = False
```

**Analysis:**
- ✅ Errors ARE caught and logged
- ✅ `phase6_error` is recorded in video_result
- ✅ Error message is printed to stderr
- ⚠️ **BUT**: Pipeline continues after Phase 6 failure

**ROOT CAUSE CANDIDATE #2:**
If harmonization returns `{"harmonization_status": "skipped"}`:
- `isinstance(harmonization_result, dict)` → True
- `harmonization_result.get('temporal_index_path')` → None
- No error is raised
- Phase 6 marked as complete even though it was skipped

---

## 7. PHASE 6 EXECUTION CONDITIONS

### Condition Check (cli/run_ingestion.py Line 1271)
```python
if phase6_enabled and scene_outputs:
```

**Requirements:**
1. `phase6_enabled = cfg.get('phase6', {}).get('enabled', True)`
   - ✅ Defaults to True
   - ✅ Config shows `phase6.enabled: true`

2. `scene_outputs` must be non-empty
   - Populated at Line 1256: `scene_outputs.append(scene_record)`
   - Only added if scenes are detected in Phase 5

**ROOT CAUSE CANDIDATE #3:**
If Phase 5 produces zero scenes:
- `scene_outputs = []` (empty list)
- Condition fails: `if phase6_enabled and scene_outputs:` → False
- Phase 6 is **SKIPPED ENTIRELY**
- No error message logged (just skipped silently)

---

## 8. STEP RUNNER EXECUTION

### Step Mapping (cli/step_runner.py Lines 177-180)
```python
if step_name == "cross_modal_harmonization":
    from goodq4all.steps.video.cross_modal_harmonizer import run_cross_modal_harmonization
    
    return run_cross_modal_harmonization(item, cfg)
```

**Execution Flow:**
1. Pipeline calls `_run_step('goodq_core', 'cross_modal_harmonization', phase6_item, cfg_json)`
2. `_run_step` spawns subprocess: `conda run -n goodq_core python step_runner.py`
3. `step_runner.py` loads harmonizer and calls it
4. Result is serialized to JSON and returned to pipeline

**Analysis:**
- ✅ Step is correctly mapped
- ✅ Import path is correct: `goodq4all.steps.video.cross_modal_harmonizer`
- ✅ Function is called with correct arguments

---

## ROOT CAUSE HYPOTHESIS

Based on the diagnostic scan, there are **THREE possible root causes**:

### 🔴 **ROOT CAUSE #1: Scene Manifest Not Found (MOST LIKELY)**

**Evidence:**
1. Harmonizer checks for scene manifest at: `processing_dir/video/scene_manifest.json`
2. If not found, harmonizer returns: `{"harmonization_status": "skipped", "reason": "no_scene_manifest"}`
3. Pipeline doesn't check for "skipped" status - treats it as success
4. **NO temporal index is created**

**Why This Happens:**
- Pipeline writes scene manifest to: `video_workspace / 'scene_manifest.json'` (Line 1302)
- But harmonizer expects it at: `processing_dir / 'video' / 'scene_manifest.json'` (Line 130)
- **PATH MISMATCH!**

**Expected:** `L:\_DATA\GoodQ_Data\processing\<video_id>\scene_manifest.json`  
**Actual:** `L:\_DATA\GoodQ_Data\processing\<video_id>\video\scene_manifest.json`

---

### 🟡 **ROOT CAUSE #2: Empty Scene Outputs (POSSIBLE)**

**Evidence:**
1. Phase 6 only runs if `scene_outputs` is non-empty (Line 1271)
2. If Phase 5 detects zero scenes → Phase 6 skipped entirely
3. No error message, no temporal index

**Why This Happens:**
- Video might be too short
- Scene detection might fail
- Threshold might be too high

**How to Check:**
Look at logs for: `[PHASE 6] Skipped (disabled in config)` or no Phase 6 mention at all

---

### 🟢 **ROOT CAUSE #3: Phase 6 Disabled (UNLIKELY)**

**Evidence:**
1. Config shows `phase6.enabled: true` ✅
2. This is NOT the issue

---

## VERIFICATION STEPS

### 1. Check Scene Manifest Location
```bash
# Expected by harmonizer:
ls L:\_DATA\GoodQ_Data\processing\<video_id>\video\scene_manifest.json

# Written by pipeline:
ls L:\_DATA\GoodQ_Data\processing\<video_id>\scene_manifest.json
```

### 2. Check Phase 6 Execution in Logs
```bash
grep "PHASE 6" L:\goodq4all\logs\direct_ingest_sample.json
```

Look for:
- `[PHASE 6a] Generating scene visual embeddings...`
- `[PHASE 6b] Running multimodal harmonization...`
- `[PHASE 6b] [PASS] Harmonization complete`
- OR `[PHASE 6] [FAIL]`

### 3. Check Harmonizer Logs
```bash
grep "HARMONIZER" L:\goodq4all\logs\*.log
```

Look for:
- `[HARMONIZER] Starting cross-modal fusion for <video_id>`
- `[HARMONIZER] [OK] Created temporal index`
- OR `No scene manifest found, skipping harmonization`

---

## RECOMMENDED FIX

### Option A: Fix Scene Manifest Path (RECOMMENDED)

**In cli/run_ingestion.py, Line 1302:**

Change from:
```python
scene_manifest_path = video_workspace / 'scene_manifest.json'
```

To:
```python
scene_manifest_path = video_workspace / 'video' / 'scene_manifest.json'
# Ensure video subdirectory exists
scene_manifest_path.parent.mkdir(parents=True, exist_ok=True)
```

### Option B: Fix Harmonizer to Match Pipeline

**In steps/video/cross_modal_harmonizer.py, Line 130:**

Change from:
```python
scene_manifest_path = os.path.join(processing_dir, 'video', 'scene_manifest.json')
```

To:
```python
# Try both locations
scene_manifest_path = os.path.join(processing_dir, 'video', 'scene_manifest.json')
if not os.path.exists(scene_manifest_path):
    scene_manifest_path = os.path.join(processing_dir, 'scene_manifest.json')
```

### Option C: Add Better Error Handling (ADDITIONAL)

**In cli/run_ingestion.py after Line 1320:**

Add:
```python
if harmonization_result.get('harmonization_status') == 'skipped':
    reason = harmonization_result.get('reason', 'unknown')
    typer.echo(f'[PHASE 6b] [WARN] Harmonization skipped: {reason}', err=True)
    video_result['phase6_complete'] = False
    video_result['phase6_skipped'] = True
    video_result['phase6_skip_reason'] = reason
```

---

## CONCLUSION

**Root Cause:** Scene manifest path mismatch  
**Impact:** Harmonizer can't find scene manifest, skips execution, no temporal index created  
**Severity:** CRITICAL - Blocks temporal index creation  
**Fix Difficulty:** EASY - 1-2 line change  
**Recommended Action:** Apply Option A (fix pipeline to write to `video/` subdirectory)

**NO MODIFICATIONS WERE MADE IN THIS DIAGNOSTIC SCAN**

---

**End of Phase 6B Diagnostic Report**
