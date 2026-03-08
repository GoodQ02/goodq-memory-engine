<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_ARCHIVED_ON: 2026-02-12 -->

> [!WARNING]
> ARCHIVE / NON-CANONICAL / DO NOT COPY PATHS
> This document is preserved as historical evidence and may contain obsolete fixed-drive paths, host-specific assumptions, stale commands, or superseded runtime guidance.
> Do not use it for current runtime, setup, migration, or copy-paste path decisions.
> Use active documentation, `config_loader`, and canonical path abstractions such as `<project_root>`, `<GOODQ_DATA_ROOT>`, and `<GOODQ_WSL_WORKSPACE>` instead.

# 🔬 PHASE ABC SURGICAL FIX - December 13, 2025

## Executive Summary

✅ **Phase A (Scene Manifest)**: ALREADY FIXED
✅ **Phase B (Unified Audio)**: ALREADY IMPLEMENTED  
⚠️ **Phase C (Entity Extraction)**: WIRED BUT NOT EXECUTING

## Current Status Analysis

### Phase A: Scene Manifest ✅ COMPLETE

**Finding**: The pipeline is ALREADY correctly configured!

#### Evidence:
1. **Ingestion writes to correct path** (`cli/run_ingestion.py:1324-1327`):
   ```python
   scene_manifest_path = video_workspace / 'video' / 'scene_manifest.json'
   scene_manifest_path.parent.mkdir(parents=True, exist_ok=True)
   ```

2. **Harmonizer looks in correct path with fallback** (`cross_modal_harmonizer.py:131-144`):
   ```python
   scene_manifest_path = os.path.join(processing_dir, 'video', 'scene_manifest.json')
   
   # Fallback for older or mismatched pipelines
   if not os.path.exists(scene_manifest_path):
       alt_path = os.path.join(processing_dir, 'scene_manifest.json')
       if os.path.exists(alt_path):
           logger.warning(f"[HARMONIZER] Using fallback scene_manifest.json at: {alt_path}")
           scene_manifest_path = alt_path
   ```

3. **Harmonizer returns proper skip status** (line 143-144):
   ```python
   if not scene_data:
       logger.warning(f"[HARMONIZER] No scene manifest found at {scene_manifest_path}, skipping harmonization")
       return {"harmonization_status": "skipped", "reason": "no_scene_manifest"}
   ```

**Conclusion**: Phase A is fully implemented. No changes needed.

---

### Phase B: Unified Audio ✅ MOSTLY COMPLETE

**Finding**: WSL2 audio bridge is already integrated!

#### Evidence (`cli/run_ingestion.py:838-854`):
```python
# WSL2 GPU-accelerated audio processing (only if audio exists)
if audio_path and audio_path.exists():
    from steps.audio.audio_wsl2_bridge import audio_diarize_wsl2, audio_transcribe_wsl2, audio_emotion_wsl2
    
    # Diarization
    diarize_result = audio_diarize_wsl2(str(audio_path), scene_id=scene_id)
    if isinstance(diarize_result, dict):
        item.update(diarize_result)
    
    # Transcription
    transcribe_result = audio_transcribe_wsl2(str(audio_path), scene_id=scene_id)
    if isinstance(diarize_result, dict):
        item.update(diarize_result)
```

**Current Architecture**:
- ✅ WSL2 bridge functions exist
- ✅ Integrated into `_process_audio()` 
- ✅ Legacy steps preserved for compatibility (`audio_speaker_merge`, `audio_music_events`, etc.)
- ⚠️ Full unified step from `process_audio.py` not yet fully wired

**Minor Optimization Needed**: Replace individual `audio_*_wsl2()` calls with single unified call to `process_audio.py`.

---

### Phase C: Entity Extraction ⚠️ NEEDS ACTIVATION

**Finding**: Entity extractor EXISTS but is NOT being called!

#### Files Found:
- ✅ `steps/video/entity_extractor.py` - **EXISTS AND COMPLETE**
- ✅ Proper dataclass structure (`ExtractedEntity`)
- ❌ **NOT CALLED** in harmonizer

#### Root Cause:
The harmonizer loads scene data, audio data, and creates temporal index, but **never calls entity extraction**.

---

## Required Fixes

### Fix #1: Activate Entity Extraction in Harmonizer

**File**: `steps/video/cross_modal_harmonizer.py`

**Location**: After temporal index building (around line 200-250)

**Change**: Add entity extraction step

```python
# After building segments_data but before writing temporal_index

from steps.video.entity_extractor import EntityExtractor

# Initialize extractor
extractor = EntityExtractor(cfg=cfg)

# Extract entities from all segments
all_entities = []
for segment in segments_data:
    entities = extractor.extract_from_segment(segment)
    segment['entities'] = [e.to_dict() for e in entities]
    all_entities.extend(entities)

# Add global entities to temporal index
temporal_index['entities'] = {
    'total': len(all_entities),
    'by_type': extractor.get_entity_summary(all_entities),
    'all': [e.to_dict() for e in all_entities]
}
```

---

### Fix #2: Wire Entities into Knowledge Graph

**File**: `cli/run_ingestion.py` (around line 1380-1400 where KG is built)

**Change**: Pass entities to KG builder

```python
# When calling KG builder
from lib.knowledge_graph_builder import build_knowledge_graph

if temporal_index_path.exists():
    temporal_index = json.loads(temporal_index_path.read_text())
    entities = temporal_index.get('entities', {}).get('all', [])
    
    kg_result = build_knowledge_graph(
        video_hash=video_hash,
        scenes=scenes,
        temporal_index=temporal_index,
        entities=entities,  # NEW
        cfg=cfg
    )
```

---

### Fix #3: Add Entity Payload to Qdrant Vectors

**File**: Where Qdrant insertions happen (likely in embedding steps or harmonizer)

**Change**: Include entities in metadata payload

```python
# When inserting to Qdrant
payload = {
    'video_id': video_hash,
    'scene_id': scene_id,
    'start': start_time,
    'end': end_time,
    'entities': [e['name'] for e in segment.get('entities', [])],  # NEW
    'entity_types': [e['entity_type'] for e in segment.get('entities', [])],  # NEW
    'transcription': transcription_text,
    'emotion': emotion,
    'speakers': speaker_list
}
```

---

## Validation Plan

### Test #1: Verify Entity Extraction
```bash
cd L:\goodq4all
python -c "from steps.video.entity_extractor import EntityExtractor; print('✅ Import OK')"
```

### Test #2: Run Sample Ingestion
```bash
cd L:\goodq4all
python -m cli.run_ingestion --force-reprocess sample.mp4
```

**Expected Output**:
- `temporal_index.json` contains `entities` key
- Entity count > 0 for scenes with speech
- `[kg] Scene X: N entities resolved` where N > 0

### Test #3: Check Qdrant Payloads
```python
from qdrant_client import QdrantClient
client = QdrantClient(url="http://localhost:6333")

points = client.scroll(
    collection_name="goodq_text",
    limit=5
)[0]

# Should see 'entities' in payload
for point in points:
    print(point.payload.get('entities', []))
```

---

## Implementation Priority

1. **IMMEDIATE**: Fix #1 (Activate entity extraction) - 5 minutes
2. **HIGH**: Fix #2 (Wire to KG) - 10 minutes  
3. **MEDIUM**: Fix #3 (Qdrant payloads) - 15 minutes
4. **LOW**: Optimize Phase B (unified audio call) - 30 minutes

**Total Time**: ~1 hour of surgical changes

---

## Risk Assessment

- ✅ **LOW RISK**: All changes are additive (no deletions)
- ✅ **SAFE**: Entity extraction is already implemented and tested
- ✅ **REVERSIBLE**: Can comment out entity calls if issues arise
- ⚠️ **MINOR**: May need to handle cases where entity extraction returns empty list

---

## Next Steps

1. Apply Fix #1 (entity extraction activation)
2. Run validation test on sample video
3. Verify entity count > 0 in logs
4. Check `temporal_index.json` structure
5. If successful, proceed with Fix #2 and #3
6. Run full overnight ingestion to populate entity graph

---

**Status**: Ready for implementation  
**Estimated Completion**: 60 minutes  
**Dependencies**: None (all prerequisites exist)
