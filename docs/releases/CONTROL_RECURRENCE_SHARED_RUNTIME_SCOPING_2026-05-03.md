<!-- DOC_BADGE: RELEASE -->
<!-- DOC_STATUS: OPERATOR_NOTE -->
<!-- DOC_LAST_VERIFIED: 2026-05-03 -->

# Control Recurrence Shared Runtime Scoping Note

## Summary

Commit `a036f75` fixes shared runtime recurrence scoping for direct canonical
run roots. Captured direct-run stdout events are now filtered by persisted
video and scene identity before they become recurrence signals.

## What Changed

- Shared direct-run stdout files can cover more than one video.
- Runtime `step_error` and retry events are now attached only to the episode
  scope whose `video_id`, `video_hash`, `scene_id`, or `scene_index` matches
  persisted truth surfaces.
- Recovered native retries still coalesce once across run warnings, runtime
  events, stderr text, and `step_runs.jsonl`.
- Scene/video attribution is preserved when those fields exist in captured
  runtime events.

## Validation

- `tests/unit/test_control_recurrence_report.py`
- Re-run against the prior two-episode witness with real native retry evidence:
  two recovered `native_crash_retry:0xC0000409` incidents were counted once
  each, both attributed to the correct video/scene context.
- Fresh one-episode witness:
  `reports/fresh_ingest_runs/20260503_135503_native_retry_attribution_02x02_witness`
  completed with 38 scenes, healthy Phase 6/Qdrant truth, no native retry
  reproduction, and one non-blocking CLAP `audio_silent` skip.

## Boundary

This is observer-only recurrence scoping. It does not activate `ControlAgent`,
enable healing, mutate configs, trigger ingestion, change retry behavior,
change model behavior, write Qdrant, backfill vectors, or create a second
execution path.
