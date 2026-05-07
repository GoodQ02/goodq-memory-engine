<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: REFERENCE_ONLY -->
<!-- DOC_CANONICAL_POINTER: docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

# GoodQ4All Pipeline Diagnosis - 2025-11-11

> Historical planning document. Preserved as a readable summary of the original
> large-file diagnosis and proposed mitigations.

## Executive Summary

The original diagnosis concluded that the pipeline behaved correctly on small
media but failed on very large assets because Windows ran out of process or
kernel resources during long-running ingestion.

## Historical Context

At the time of this note:

- the pipeline succeeded on small validation media
- large multi-gigabyte home-movie assets could crash during ingestion
- the API surface stayed up while the watchdog retried failed work
- the UI could continue showing stale success state from earlier small-file runs

## Root Cause Identified Then

The recorded crash signature was:

```text
STATUS_INSUFFICIENT_RESOURCES
```

The working theory was that one or more of these heavy steps could exhaust
memory or process resources on very large assets:

- scene detection on long video files
- audio diarization across multi-hour audio
- Whisper transcription on very long recordings

## Historical Evidence

Representative excerpts from the original investigation:

```text
2025-11-10 20:29:33,981 [WARNING] Removing stale lock from dead process 39912
2025-11-10 23:21:00,041 [WARNING] Removing stale lock from dead process 14272
2025-11-10 23:22:43,107 [ERROR] Mission failed: Video ingestion returned code 3221225786
```

```text
[OK] Found sample video: <project_root>\samples\smoke\sample.mp4
Exit code: 0
[SUCCESS]
```

```text
2025-11-10 20:29:57,492 [INFO] Mission timeout: 78668s (21.9h) for 7.28GB asset
2025-11-10 20:29:57,492 [INFO] Asset: 01. 1987 - 1988.mp4
[CRASH within 1 minute]
```

## Remediations Proposed Then

### [Critical] Immediate Fixes

1. Pre-split very large videos into manageable chunks before ingestion.
2. Stream or batch scene-detection work instead of treating the entire asset as
   one in-memory unit.
3. Add explicit memory monitoring and fail-visible thresholds.

### [Medium] Resource Optimization

4. Reduce scene-detection sensitivity when large assets produce excessive scene
   counts.
5. Use a smaller Whisper model for the initial pass on very long media.
6. Chunk diarization work into shorter audio windows.

### [Low] Long-Term Improvements

7. Improve progress reporting across long-running steps.
8. Add graceful degradation paths when a high-cost configuration fails.

## Important Note

This document is a historical diagnosis snapshot, not current runtime guidance.
Trust the canonical runtime docs, current manifests, and run artifacts for the
present state of the system.
