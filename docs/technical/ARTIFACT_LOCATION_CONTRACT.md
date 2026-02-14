# Artifact Location Contract

**Status:** ⚠️ **KNOWN INCONSISTENCY** (Acceptable for v2.0)  
**Last Updated:** December 15, 2025  
**Priority:** Low (deferred to v2.1+)

---

## Overview

There is a **documented inconsistency** between the configured artifact location and the actual runtime behavior. This is **non-breaking** and does not impact functionality, but is tracked for future cleanup.

---

## The Inconsistency

### Config Contract
**File:** `config.yaml`
```yaml
processing: <GOODQ_DATA_ROOT>\GoodQ_Data\processing\
```

**Expectation:** Scene artifacts should be written to:
```
<GOODQ_DATA_ROOT>\GoodQ_Data\processing\<video_name>\
  ├── audio\
  └── video\
```

### Runtime Reality
**File:** `cli/run_ingestion.py` (lines 931-932)
```python
output: Path = typer.Option(Path('logs/scene_ingest_results.json'), ...),
workspace: Path = typer.Option(Path('logs/scene_ingest'), ...),
```

**Actual Location:** Scene artifacts are written to:
```
<project_root>\logs\scene_ingest\<video_name>\
  ├── audio\          # scene_0000.wav to scene_XXXX.wav
  └── video\          # scene_0000.jpg to scene_XXXX.jpg
      └── scene_manifest.json
```

---

## Why This Is Acceptable

### ✅ No Data Loss
- All artifacts are created successfully
- All downstream consumers use `scene_manifest.json` (which contains correct paths)
- No ambiguity in file locations

### ✅ Phase 6+ Works Correctly
- Entity extraction reads from actual locations
- Knowledge graph integration functions properly
- Memory storage receives correct data

### ✅ Documentation Is Truthful
As of December 15, 2025, all documentation reflects **actual** locations:
- `README.md`
- `docs/architecture/SYSTEM_ARCHITECTURE.md`
- `docs/SCENE_MANIFEST_SPECIFICATION.md`
- `docs/architecture/diagrams/PIPELINE_FLOW.md`

### ✅ No Breaking Changes Required
- Existing workflows are stable
- Users know where to find artifacts
- Pipeline runs unattended for hours

---

## Impact Assessment

### User Experience
**Impact:** ✅ None
- Users follow documentation (which is correct)
- File locations are predictable and consistent
- No confusion reported

### Development
**Impact:** ⚠️ Minor
- Config file misleads developers expecting `processing/` to be used
- New features might assume config is authoritative
- Code comments reference non-existent paths

### Production
**Impact:** ✅ None
- System operates correctly
- Monitoring and observability work as expected
- No runtime errors or data corruption

---

## Future Resolution Options

### Option A: Update Config (Recommended)
**Effort:** Low  
**Risk:** None  
**Action:** Change `config.yaml` to document actual behavior

```yaml
# Current (misleading)
processing: <GOODQ_DATA_ROOT>\GoodQ_Data\processing\

# Updated (truthful)
scene_artifacts: logs\scene_ingest\
processing_workspace: logs\scene_ingest\
```

**Pros:**
- Zero code changes
- Config becomes documentation
- No regression risk

**Cons:**
- Breaking change for anyone parsing config
- Need to update config loaders

---

### Option B: Update Runtime (Not Recommended)
**Effort:** Medium  
**Risk:** High  
**Action:** Modify `cli/run_ingestion.py` to respect config path

```python
# Load from config
workspace = Path(config['processing']) / 'scene_ingest'
```

**Pros:**
- Config becomes authoritative
- Aligns with original design intent

**Cons:**
- **BREAKS EXISTING PATHS** - All downstream consumers would need updates
- Would move 13 existing video directories
- Requires migration script
- Risk of data loss during migration
- Testing burden is significant

---

### Option C: Hybrid Approach (Future)
**Effort:** Medium  
**Risk:** Low  
**Action:** Add migration flag for new installations

```yaml
# New config option
artifact_locations:
  legacy_mode: true                # Uses logs/scene_ingest/
  unified_storage: false           # Uses <GOODQ_DATA_ROOT>\GoodQ_Data\processing/
```

**Pros:**
- Backward compatible
- Allows gradual migration
- User choice

**Cons:**
- Increases code complexity
- Two code paths to maintain
- More testing required

---

## Recommendation

**For v2.0:** ✅ **No Action Required**

- System is operational and stable
- Documentation is accurate
- No user complaints
- No data integrity issues

**For v2.1+:** ⚠️ **Update Config (Option A)**

When next making breaking changes:
1. Update `config.yaml` to document actual paths
2. Update config loaders to use new keys
3. Add migration guide for users who parse config
4. Update any remaining code comments

---

## Verification Commands

### Check Where Artifacts Actually Land
```powershell
# Windows
Get-ChildItem "logs\scene_ingest\" -Directory | Select-Object Name, LastWriteTime

# Should show video directories with recent timestamps
```

### Check Config Value
```powershell
# View config
Get-Content config.yaml | Select-String "processing"

# Will show: processing: <GOODQ_DATA_ROOT>\GoodQ_Data\processing\
```

### Confirm Scene Manifests Exist
```powershell
# Find all scene manifests
Get-ChildItem "logs\scene_ingest\*\video\scene_manifest.json" -Recurse
```

---

## Related Documentation

- [`docs/SCENE_MANIFEST_SPECIFICATION.md`](../SCENE_MANIFEST_SPECIFICATION.md) - Canonical artifact format
- [`docs/architecture/SYSTEM_ARCHITECTURE.md`](../architecture/SYSTEM_ARCHITECTURE.md) - System-wide artifact locations
- [`cli/run_ingestion.py`](../../cli/run_ingestion.py) - Runtime artifact creation (lines 931-932, 1377-1382)
- [`config.yaml`](../../config.yaml) - Configuration file with misleading path

---

## Conclusion

This is a **cosmetic contract violation**, not a functional bug. The system:
- ✅ Works correctly
- ✅ Is fully documented
- ✅ Has no data integrity issues
- ✅ Requires no immediate action

The inconsistency is **acknowledged**, **tracked**, and **deferred** to a future release when breaking changes are acceptable.

