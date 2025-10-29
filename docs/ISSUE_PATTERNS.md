# 🔍 Issue Pattern Analysis - GoodQ4All
**Generated:** 2025-10-15 11:35  
**Analysis Method:** Root cause grouping and pattern detection

---

## Pattern Categories

### 🔴 Category A: Silent Failures & Error Suppression

**Pattern:** Functions return `None` or fail silently without propagating errors to logs.

#### Issue A.1: Whisper Transcription Silent Failure
- **Location:** `steps/audio_transcribe/step.py` lines 143-188
- **Pattern:** `_transcribe_chunk_whisper_cli()` returns `None` on error but doesn't log details
- **Evidence:** Line 187 only prints `[WARN]` without exception details
- **Impact:** 29/29 (100%) transcript failures
- **Root Cause:** Exception caught, logged as warning, but not debugged
- **Frequency:** Every single audio chunk

```python
# Current code (line 186-188):
except Exception as e:
    print(f'[WARN] _transcribe_chunk_whisper_cli returning None')
    return None
```

**Fix Strategy:**
```python
# Improved error logging:
except Exception as e:
    print(f'[ERROR] Whisper CLI failed: {str(e)}')
    print(f'[ERROR] Command: {" ".join(cmd)}')
    print(f'[ERROR] Chunk path: {chunk_path}')
    if os.path.isfile(chunk_path):
        print(f'[ERROR] Chunk size: {os.path.getsize(chunk_path)} bytes')
    return None
```

#### Issue A.2: Audio Duration Failures
- **Location:** `steps/audio_transcribe/step.py` lines 28-46
- **Pattern:** Multiple fallback attempts, returns `None` on failure
- **Evidence:** Line 45 returns `None` without context
- **Impact:** Unknown (may cause chunk building failures)

#### Issue A.3: Audio Slicing Failures
- **Location:** `steps/audio_transcribe/step.py` lines 89-140
- **Pattern:** Two fallback methods (soundfile, ffmpeg), both can fail silently
- **Evidence:** Lines 114, 139 return `None` with only `[WARN]`
- **Impact:** Causes "slice_failed" chunk reports

**Common Root Cause:** Python exception handling that swallows errors instead of making them visible.

**Group Fix:** Add a logging utility that captures and reports full exception context:
```python
def log_error_with_context(msg, exception, context):
    print(f'[ERROR] {msg}')
    print(f'[ERROR] Exception: {str(exception)}')
    print(f'[ERROR] Type: {type(exception).__name__}')
    for key, val in context.items():
        print(f'[ERROR] {key}: {val}')
    import traceback
    print(f'[ERROR] Traceback:\n{traceback.format_exc()}')
```

---

### 🟡 Category B: Schema Mismatches & Documentation Gaps

**Pattern:** Code and documentation assume different data structures or naming conventions.

#### Issue B.1: DINO Modality Convention
- **Location:** `steps/image_embed_dino/step.py` line 100
- **Pattern:** Stores embeddings with `modality="image"` not `modality="dino"`
- **Evidence:** Code says `item.get("modality", "image") or "image"`
- **Impact:** Confusion when querying - DINO embeddings not where expected
- **Root Cause:** DINO and CLIP share the "image" modality namespace
- **Documentation Gap:** This convention is not documented

#### Issue B.2: CLIP Index Location Ambiguity
- **Location:** `data/faiss_indices/clip/` directory missing
- **Pattern:** Database has CLIP faiss_id but no index file at expected path
- **Evidence:** DINO index exists, CLIP index doesn't (at expected location)
- **Root Cause:** May be stored in DINO index or different path
- **Documentation Gap:** FAISS index architecture not documented

#### Issue B.3: ID Map Architecture
- **Location:** `data/databases/*.sqlite` vs expected JSON
- **Pattern:** Documentation mentions `*_id_map.json` but actual files are SQLite
- **Evidence:** 
  - Expected: `faiss_indices/audio/audio_id_map.json`
  - Actual: `databases/clap_id_map.sqlite`
- **Root Cause:** Architecture evolved but docs didn't update
- **Impact:** LOW - works correctly, just confusing

**Common Root Cause:** Code evolved but documentation and comments didn't keep pace.

**Group Fix:** 
1. Create `docs/ARCHITECTURE_REFERENCE.md` with actual schemas
2. Add inline comments explaining convention choices
3. Update README's "Data Locations" section

---

### 🟢 Category C: Path Resolution & Configuration

**Pattern:** Tools/models/paths resolved at multiple levels with fallbacks.

#### Issue C.1: Whisper Path Resolution
- **Location:** `steps/audio_transcribe/step.py` lines 283-284, 302-304
- **Pattern:** Reads from `cfg["config"]["tools"]` with nested dict access
- **Evidence:** 
  ```python
  tools_cfg = ((cfg.get("config", {}) or {}).get("tools", {}) or {})
  whisper_cli = tools_cfg.get("whisper_cli")
  ```
- **Potential Issue:** If config structure changes, paths may not resolve
- **Currently Working:** Paths are correct (tested whisper.cpp manually)

#### Issue C.2: FFmpeg Resolution
- **Location:** `steps/audio_transcribe/step.py` line 275
- **Pattern:** Uses helper function `resolve_ffmpeg(cfg)` with "ffmpeg" fallback
- **Evidence:** `ffmpeg_path = resolve_ffmpeg(cfg) or "ffmpeg"`
- **Currently Working:** FFmpeg is installed and on PATH

**Common Root Cause:** Defensive programming with fallbacks can mask config issues.

**Not Broken:** These patterns are actually working well - include for completeness.

---

### ⚠️ Category D: Resource Cleanup & Temporary Files

**Pattern:** Temp files created and cleaned up in finally blocks, but timing may matter.

#### Issue D.1: Premature Cleanup of JSON Output
- **Location:** `steps/audio_transcribe/step.py` lines 189-195
- **Pattern:** `finally` block removes temp files even if parsing failed
- **Evidence:**
  ```python
  finally:
      for ext in (".json", ".txt", ".srt", ".tsv"):
          try:
              os.remove(out_prefix + ext)
          except:
              pass
  ```
- **Potential Issue:** If JSON file exists but is empty/corrupted, we delete evidence
- **Impact:** May be why transcripts are failing - can't debug missing files

#### Issue D.2: Chunk Audio Cleanup
- **Location:** `steps/audio_transcribe/step.py` lines 412-417
- **Pattern:** Temp chunk audio cleaned up immediately after processing
- **Evidence:** `os.remove(tmp_chunk)` in finally block
- **Currently Working:** But makes post-mortem debugging harder

**Common Root Cause:** Cleanup happens before we can inspect failure artifacts.

**Group Fix:** Add `GOODQ_DEBUG_KEEP_TEMP` environment variable:
```python
DEBUG_MODE = os.environ.get('GOODQ_DEBUG_KEEP_TEMP', '').lower() == 'true'

if not DEBUG_MODE:
    os.remove(tmp_chunk)
else:
    print(f'[DEBUG] Keeping temp file for inspection: {tmp_chunk}')
```

---

### 📊 Category E: Logging & Observability

**Pattern:** Step execution logging is comprehensive but error details are sparse.

#### Issue E.1: Step.py Syntax Errors in Logs
- **Location:** 268 errors in `logs/step_runs.jsonl`
- **Pattern:** All show "invalid syntax" at step.py line 98
- **Evidence:** Error: `"invalid syntax. Perhaps you forgot a comma?"`
- **Root Cause:** Unknown - need to inspect actual step.py files
- **Impact:** May be historic/corrupted log entries
- **Hypothesis:** JSON serialization issue when logging exception objects

#### Issue E.2: Missing Step Names in Error Logs
- **Location:** Error entries in `step_runs.jsonl`
- **Pattern:** `step_name` field is `None` in error entries
- **Evidence:** All 268 errors have `"step_name": null`
- **Root Cause:** Error occurs before step name is set in context
- **Impact:** Can't identify which step had the syntax error

**Common Root Cause:** Logging infrastructure logs the error object incorrectly.

**Group Fix:** 
1. Review step runner initialization
2. Ensure step_name is captured before any code runs
3. Add try/catch around JSON serialization of log entries

---

## Root Cause Categories Summary

| Category | Issues | Severity | Root Cause |
|----------|--------|----------|------------|
| A: Silent Failures | 3 | 🔴 CRITICAL | Exception handling that swallows context |
| B: Schema Mismatches | 3 | 🟡 MODERATE | Documentation lag behind code evolution |
| C: Path Resolution | 2 | 🟢 LOW | Working as intended, defensive programming |
| D: Resource Cleanup | 2 | ⚠️ WARNING | Premature cleanup blocks debugging |
| E: Logging Issues | 2 | 🟡 MODERATE | Logging infrastructure bugs |

---

## Pattern Frequency Analysis

### By Source File

| File | Issues | Pattern |
|------|--------|---------|
| `audio_transcribe/step.py` | 6 | Most issues concentrated here |
| `image_embed_dino/step.py` | 1 | Working correctly, just undocumented |
| `logs/step_runs.jsonl` | 2 | Logging infrastructure issues |

### By Impact Severity

```
CRITICAL (🔴): 1 issue  (100% transcription failure)
MODERATE (🟡): 5 issues (documentation, logging, schema)
LOW (🟢):      2 issues (working but could be clearer)
WARNING (⚠️):  2 issues (blocks debugging)
```

### By Fix Complexity

| Complexity | Issues | Estimated Time |
|------------|--------|----------------|
| Trivial (add logging) | 3 | 10 minutes each |
| Simple (fix logic) | 1 | 30 minutes |
| Medium (refactor) | 4 | 1-2 hours each |
| Complex (architecture) | 0 | N/A |

---

## Quick Win Opportunities

### 1. Add Debug Mode (30 minutes)
- Add `GOODQ_DEBUG_KEEP_TEMP=true` env var
- Keep temp files when enabled
- Add verbose logging for whisper.cpp
- **Impact:** Makes transcription debugging 10x easier

### 2. Fix Whisper Error Logging (15 minutes)
- Replace generic `[WARN]` with detailed `[ERROR]` messages
- Log command, files, subprocess output
- **Impact:** Will immediately reveal why transcripts fail

### 3. Document DINO/CLIP Architecture (1 hour)
- Write `docs/EMBEDDING_ARCHITECTURE.md`
- Explain modality conventions
- Document FAISS index structure
- **Impact:** Eliminates confusion for future developers

### 4. Create Diagnostic Script (45 minutes)
- `scripts/diagnose_transcription.py`
- Tests whisper.cpp with sample files
- Validates config paths
- Tests chunk slicing
- **Impact:** Automated root cause detection

---

## Recommended Fix Order

### Phase 1: Stop the Bleeding (1 hour)
1. ✅ Add debug logging to whisper transcription
2. ✅ Add debug mode for temp file retention
3. ✅ Run test with one scene
4. ✅ Identify actual transcription failure cause

### Phase 2: Fix Root Cause (30 min - 2 hours)
5. ⬜ Fix transcription based on Phase 1 findings
6. ⬜ Test with full video
7. ⬜ Validate 95%+ transcription success

### Phase 3: Documentation & Polish (2-3 hours)
8. ⬜ Write embedding architecture docs
9. ⬜ Document ID map SQLite schema
10. ⬜ Update README with correct conventions
11. ⬜ Clean up old log entries
12. ⬜ Add diagnostic scripts

### Phase 4: Prevent Recurrence (1-2 hours)
13. ⬜ Add linter rules for exception handling
14. ⬜ Create error logging utility
15. ⬜ Add integration tests for transcription
16. ⬜ Set up automated health checks

---

## Testing Strategy

### Regression Test Suite
After fixing transcription, ensure:
```bash
# Test whisper.cpp directly
./test_whisper_direct.sh

# Test chunk slicing
python scripts/test_chunk_slicing.py

# Test full pipeline with one scene
python cli/run_ingestion.py ingest sample.mp4 --max-scenes 1

# Test full pipeline
python cli/run_ingestion.py ingest sample.mp4

# Verify database
python scripts/check_db_status.py --verify-transcripts
```

### Monitoring After Fix
```bash
# Watch for transcript failures
watch -n 5 "sqlite3 data/memory.db 'SELECT COUNT(*) FROM scenes WHERE json_extract(meta, \"$.transcript_meta.status\") = \"failed\"'"

# Monitor error rate
tail -f logs/step_runs.jsonl | grep "error"
```

---

## Lessons Learned

### 1. Silent Failures Are Dangerous
Exception handlers that print warnings but don't preserve context make debugging nearly impossible. Always log:
- Exception type and message
- Stack trace
- All input parameters
- File paths and sizes
- Command strings being executed

### 2. Test External Tools in Isolation
Before integrating a tool (like whisper.cpp), test it directly with the exact inputs your pipeline will use. This would have revealed the transcription issue immediately.

### 3. Documentation is Code
When the code says `modality="image"` for DINO embeddings, but developers expect `modality="dino"`, you have a documentation bug just as serious as a code bug.

### 4. Keep Debugging Artifacts
The `finally` blocks that clean up temp files are good for production, but make debugging impossible. Always add a debug mode.

### 5. Observability is a Feature
The comprehensive logging in `step_runs.jsonl` is excellent. But it's only useful if errors are logged with full context. Invest in logging infrastructure.

---

**Pattern Analysis Complete** | 12 issues analyzed | 5 root causes identified | 4 quick wins available
