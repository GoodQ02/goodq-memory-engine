<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: REFERENCE_ONLY -->
<!-- DOC_CANONICAL_POINTER: docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

# Legacy Workflows (Historical)

**Status:** Archived December 15, 2024  
**Location:** `<GOODQ_DATA_ROOT>\archive\workflows_legacy\`

## Overview

Early orchestration system using YAML-based workflow definitions for agent coordination. This was an experimental architecture that defined video ingestion as a multi-agent workflow with declarative step definitions.

## What Was It?

A declarative orchestration layer that defined:
- Step-by-step agent tasks (scene detection → frame extraction → object detection → etc.)
- Input/output contracts between steps
- Timeout and retry logic
- LLM integration points for summarization and entity extraction

## Why It Was Replaced

The current system uses **direct Python orchestration** in `cli/run_ingestion.py`:
- More explicit control flow
- Easier debugging and error handling
- Direct integration with goodq_core services
- No abstraction overhead
- Better performance (no YAML parsing, no agent broker)

## Historical Value

This shows an early architectural exploration of:
- Workflow-as-code patterns
- Agent-based orchestration
- Declarative pipeline definitions
- Self-healing strategies

## Current Equivalent

The functionality described in `video_ingestion.yaml` is now implemented in:
- **Entry Point:** `cli/run_ingestion.py`
- **Scene Processing Loop:** Lines 940-1400
- **Vision Steps:** `steps/video/*`
- **Audio Steps:** `steps/audio/*`
- **Entity Extraction:** `steps/video/entity_extractor.py`
- **Knowledge Graph:** `lib/kg_realtime_integration.py`

---

*Preserved for architectural history. Not part of active system.*
