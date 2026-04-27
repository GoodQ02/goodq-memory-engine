<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-27 -->

# Component Architecture Docs

This folder is for subsystem-specific architecture contracts. Component docs
should describe one bounded subsystem and link back to the system-wide
contracts in `docs/architecture/` instead of redefining orchestration,
runtime, or memory ownership.

## Current Component Docs

| Document | Scope |
| --- | --- |
| [VISION_PIPELINE.md](VISION_PIPELINE.md) | Vision pipeline architecture, contracts, and integration boundaries. |

## Placement Rule

Use this folder when a document is owned by one subsystem. Keep cross-system
contracts, canonical ingestion ownership, memory storage, and control-plane
boundaries in the parent architecture folder.

