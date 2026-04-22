# Pipelines Architecture

**Status:** Active (Compatibility Reference)  
**Last Updated:** April 2, 2026

## Overview

The `pipelines/` directory is a small compatibility/reference layer for
programmatic ingestion entry points. The actual ingestion authority lives in
`cli/run_ingestion.py`.

## Active Components

### direct_ingestion.py
**Status:** ✅ ACTIVE  
**Purpose:** Thin wrapper for programmatic ingestion calls

```python
from pipelines.direct_ingestion import run_direct_ingestion

result = run_direct_ingestion(video_path="path/to/video.mp4", cfg=config_dict)
```

**Used By:**
- `cli/watchdog.py` - Automated file monitoring
- `cli/test_ingestion.py` - Testing harness
- `cli/run_ingestion.py` - CLI entry point

**Implementation:** Imports and delegates to `cli.run_ingestion.run()` with scene-based processing.

## Architecture Flow

```
Entry Points (CLI, Watchdog, Tests)
    ↓
pipelines/direct_ingestion.py (Compatibility Layer)
    ↓
cli/run_ingestion.py (Main Orchestrator)
    ↓
Scene-Based Processing Loop
    ↓
Vision + Audio + Entity + KG Steps
```

## Historical Notes

- **Pre-December 2025:** a legacy orchestration path existed in `ingest_multimodal_conda.py`
- **Current:** pure Python sequential execution through `cli/run_ingestion.py`
- **Historical only:** any mention of `ingest_multimodal_conda.py` or its backup
  should be treated as archive/reference material, not an alternate runtime

## Why This Structure?

1. **Decoupling:** CLI tools can call ingestion without importing CLI-specific code
2. **Testing:** Test harnesses can invoke processing programmatically
3. **Future Flexibility:** Can add new programmatic entry points without changing core logic
4. **Legacy Compatibility:** Existing code calling `pipelines.*` continues to work

## Non-Action Rules

- Do not treat `pipelines/` as an alternate orchestration authority.
- Do not revive `ingest_multimodal_conda.py` from historical notes.
- Do not add new pipeline doctrines here without updating
  `INGEST_ORCHESTRATION_CONTRACT.md` first.

## Related Documentation

- [CLI Commands](../CLI-REFERENCE.md) - User-facing command reference
- [Watchdog System](../systems/WATCHDOG_SYSTEM.md) - Automated ingestion trigger
- [INGEST_ORCHESTRATION_CONTRACT.md](INGEST_ORCHESTRATION_CONTRACT.md) - Canonical ingestion authority
- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) - Runtime authority and component layout
