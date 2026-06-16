# UCF Qdrant Status Backfill Plan

<!-- DOC_STATUS: RESOLVED -->
<!-- DOC_LAST_VERIFIED: 2026-06-16 -->

> [!NOTE]
> **RESOLVED (2026-06-16)**: This backfill plan is no longer needed. All Qdrant
> write paths now include `ucf_promotion_status: "staged"` at point creation
> time, achieving 100% lifecycle coverage. The scope-based sync in
> `mini_agent_client.py` handles promote/reject/supersede updates across all
> points in epoch-scoped collections.

## Historical Context

This document originally described a plan to retroactively patch Qdrant points
that lacked the `ucf_promotion_status` payload field. The gap arose because the
UCF Retrieval Bridge was forward-sync only — it updated status during lifecycle
transitions but did not set it at write time.

## Resolution

Commits `99943a19`, `c9a7b50d`, `430efa08` (2026-06-16) closed this gap by
adding `ucf_promotion_status: "staged"` at write time in all 7 Qdrant payload
write paths:

| Write Path | File |
|---|---|
| Phase 6a visual embeddings | `steps/video/scene_visual_embeddings.py` |
| Per-scene CLIP | `steps/image_embed_clip/step.py` |
| Per-scene DINO | `steps/image_embed_dino/step.py` |
| CLAP audio | `steps/audio_embed_clap/step.py` |
| Text embed (MemoryRouter) | `steps/text_embed/step.py` |
| Scene bundle memory | `steps/common/memory.py` |
| Lifecycle sync (scope-based) | `agents/mini_agent_client.py` |

Verification: 16/16 Qdrant points carry `ucf_promotion_status` after clean
2-scene smoke ingest. 948 tests pass with zero regressions.

No backfill tool is needed. Future ingestion epochs will produce 100%
lifecycle-addressable Qdrant points from the start.
