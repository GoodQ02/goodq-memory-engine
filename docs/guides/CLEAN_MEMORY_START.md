# Clean Memory Start Guide

<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-06-07 -->

Use this guide when you want to start a fresh memory run by clearing historical vector collections and local database storage without reinstalling.

## Concept & Safety Boundaries

Before resetting your databases and collections, understand what is cleared and what is preserved:

1. **Relational & Knowledge Graph Memory**: Clears all parsed scenes, timeline segment metadata, co-occurrence nodes, and links.
2. **Qdrant Vector Collections**: Clears all Clip, Dino, Text, and Audio embedding collection points.
3. **Persisted File Artifacts**: Filesystem epochs (e.g., video files, extracted frame JPGs, Wav audio segments) are **preserved**. The system does not delete raw files unless you manually clean them.

## Authoritative Step-by-Step Runbook

To prevent manual command-line errors and document drift, the step-by-step cleanup commands are maintained in the authoritative agent runbook:

👉 **[Clean Memory Start Runbook](../../agent/workflows/CLEAN_MEMORY_START.md)**

Please follow the runbook to:
- Capture pre-cleanup Qdrant manifests and count statistics.
- Safely initialize a fresh epoch configuration.
- Execute clean-up scripts under the `goodq_core` conda environment.
- Verify that fresh vector collections are initialized empty (`points = 0`) before starting new media ingestion.
