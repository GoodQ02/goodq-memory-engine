# CRITICAL FIX: Infinite LLMClient Initialization Loop

**Date:** December 10, 2025  
**Status:** ✅ RESOLVED  
**Severity:** CRITICAL - Blocked all multi-scene video ingestion

## Problem Description

The watchdog ingestion system was entering an infinite loop when processing videos with multiple scenes. The log showed repeated LLMClient initialization every ~4 seconds, preventing any actual processing from occurring.

### Symptoms
```
2025-12-10 00:55:25,645 [INFO] LLMClient initialized with 2 models
2025-12-10 00:55:29,740 [INFO] [OK] Phi4-Ollama healthy (2ms)
2025-12-10 00:55:33,754 [INFO] LLMClient initialized with 2 models
2025-12-10 00:55:37,857 [INFO] [OK] Phi4-Ollama healthy (2ms)
2025-12-10 00:55:47,448 [INFO] LLMClient initialized with 2 models
... (repeating infinitely)
```

## Root Cause

In `lib/kg_realtime_integration.py`, the function `extract_scene_entities()` was calling `load_configs({})` on **line 71** for EVERY scene processed. 

Since `load_configs()` initializes a Control Agent, which in turn creates an LLMClient, this meant:
- Processing 17 scenes = 17 LLMClient initializations
- Each initialization takes ~4 seconds for health checks
- The system spent all its time re-initializing instead of processing

### Code Path
1. Watchdog calls `run_ingestion()` 
2. `run_ingestion()` loops through scenes (line 1063)
3. Each scene calls `update_kg_for_scene()`
4. Which calls `extract_scene_entities()`
5. Which calls `load_configs()` ← **THE BUG**
6. Which creates Control Agent → LLMClient → health checks → 4 second delay
7. Repeat for every scene

## Solution

Modified `extract_scene_entities()` to accept an optional `cfg` parameter:

```python
def extract_scene_entities(
    scene_data: Dict[str, Any],
    scene_id: str,
    video_hash: str,
    timestamp: float,
    cfg: Optional[Dict] = None  # ← ADDED
) -> Dict[str, List[Entity]]:
```

And updated the call site in `update_kg_for_scene()` to pass the config:

```python
entities_by_source = extract_scene_entities(
    scene_data, scene_id, video_hash, timestamp, cfg  # ← PASS CONFIG
)
```

## Impact

**Before Fix:**
- 7.5GB video with 17 scenes = infinite loop, never completes
- Watchdog completely broken for multi-scene videos
- All ingestion attempts failed silently

**After Fix:**
- Config loaded ONCE at start
- Scene processing proceeds normally
- Multi-scene videos can now complete ingestion
- Estimated time savings: ~68 seconds per 17-scene video (17 × 4 sec)

## Testing

Test with `01. 1987 - 1988.mp4` (7.5GB, 17 scenes):
- ✅ Scene detection completes
- ✅ Each scene processes without re-init
- ✅ Knowledge graph updates correctly
- ✅ No infinite loops

## Commit

```
commit c8050c5
fix: Prevent infinite LLMClient initialization loop in KG scene processing
```

## Lessons Learned

1. **Always profile expensive initialization** - Config loading creates Control Agent which is NOT lightweight
2. **Watch for per-item loops** - Any expensive operation in a scene loop multiplies by scene count
3. **Log analysis is critical** - The repeating timestamps revealed the loop immediately
4. **Pass dependencies down** - Better to pass config through call stack than reload

## Related Issues

This also fixes:
- Watchdog appearing to "hang" after scene detection
- Processing appearing stuck at "Processing scene 1/17"
- High memory usage from repeated agent initialization

---

**Status:** Production-ready after fix ✅
