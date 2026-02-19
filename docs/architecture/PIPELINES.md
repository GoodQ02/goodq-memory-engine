# Pipelines Architecture

**Status:** Active (Compatibility Layer)  
**Last Updated:** December 15, 2025

## Overview

The `pipelines/` directory serves as a compatibility and abstraction layer for different ingestion entry points. The actual processing logic lives in `cli/run_ingestion.py`.

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

## Placeholder/Future Components

### goodq_chat.py
**Status:** 🚧 PLACEHOLDER (Not Implemented)  
**Purpose:** Future conversational interface pipeline  
**Priority:** LOW - Focus is on ingestion stability  

Stub exists for:
- LLM chat integration (`steps.llm_chat.step`)
- TTS output (`steps.tts.step`)
- System metrics context
- Home Assistant integration

**Do Not Use:** This is a design placeholder only.

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

- **Pre-December 2025:** legacy orchestration-based pipelines existed in `ingest_multimodal_conda.py`
- **Current:** Pure Python sequential execution (legacy orchestration removed)
- **Backup:** `ingest_multimodal_conda.py.backup_20251204` preserved for reference

## Why This Structure?

1. **Decoupling:** CLI tools can call ingestion without importing CLI-specific code
2. **Testing:** Test harnesses can invoke processing programmatically
3. **Future Flexibility:** Can add new pipeline types (streaming, batch, chat) without changing core logic
4. **Legacy Compatibility:** Existing code calling `pipelines.*` continues to work

## Related Documentation

- [CLI Commands](../CLI-REFERENCE.md) - User-facing command reference
- [Watchdog System](../systems/WATCHDOG_SYSTEM.md) - Automated ingestion trigger
- Run Ingestion - Main processing orchestrator
