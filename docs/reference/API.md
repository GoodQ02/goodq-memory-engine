<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-22 -->

# GoodQ4All API Reference

This is the current API reference for the supported local GoodQ4All runtime.

## Runtime Contract

- Explicit API start: `python -m api.server` or `pwsh .\scripts\start_api.ps1`
- Related runtime launcher: `LAUNCH_GOODQ.ps1` / `LAUNCH_GOODQ.bat`
- Default bind: `127.0.0.1:30000` unless explicit environment overrides are set
- Root endpoint: `GET /` returns JSON status metadata
- OpenAPI docs: `GET /docs`
- OpenAPI schema: `GET /openapi.json`
- Supported surface: API + CLI + watchdog/runtime artifacts
- No supported product UI is currently served by the API process
- `LAUNCH_GOODQ` does not start the API process by default

## Canonical Endpoint Families

Primary status and compatibility endpoints defined in the active API surface:

- `GET /api/status`
- `GET /api/health/summary`
- `GET /api/engines`
- `GET /api/pipeline-engines`
- `GET /api/command-center`
- `GET /api/processes`
- `GET /api/scenes`

Router-backed endpoint families mounted into the same process:

- `/api/search`
- `/api/timeline`
- `/api/media`
- `/api/system`
- `/api/run-index`
- `/api/run-summary`
- `/api/videos/{video_id}/scenes`

## Active Search and Scene Retrieval Notes

- `POST /api/search/multimodal` is the canonical multimodal search surface.
- `modalities=["audio"]` is a supported request path on the active line.
- If `modalities` is omitted, the current default remains text + visual.
- `GET /api/videos/{video_id}/scenes/{scene_id}/similar` is live and resolves similar scenes from persisted multimodal scene memory.
- Similar-scene retrieval now uses text, visual, and audio signals where available instead of returning a placeholder response.

## System Mutation Policy

- `POST /api/system/ingest` is intentionally disabled on the active line.
- If an ingest API surface is introduced later, it must be:
  - explicit
  - confirmation-gated
  - policy-driven
  - budgeted
  - checkpointed
  - auditable
- Any future ingest route must remain a controlled facade over the canonical runtime path rather than a second ingest engine.
- The current supported ingest surfaces remain:
  - `conda run -n goodq_core python -m cli.watchdog`
  - `conda run -n goodq_core python -m cli.run_ingestion --input-dir <path>`
  - the configured `<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox`
- `POST /api/system/reindex` and `POST /api/system/reload` remain operator-only and intentionally unavailable as public API mutation routes on the active line.

## Scene API Truth

- Scene responses now project the persisted continuity and speaker-truth layer directly from runtime artifacts.
- Active scene read models include fields such as `speaker_count`, `dominant_speaker_id`, `continuity_key`, `diarization_status`, `emotion_status`, `speaker_voice_signature_count`, `speaker_voice_signature_meta`, `audio_emotion`, `time_hints`, `content_state`, and `candidate_visible_people`.
- Search, scene, and timeline responses now also expose `sentiment`, `sentiment_label`, and `sentiment_score` as first-class outward fields.
- Sentiment is descriptive only on the active line; it should inform interpretation without silently dictating ranking or replacing stronger multimodal evidence.

## Discovery Rule

Use `/docs` and `/openapi.json` as the authoritative machine-readable endpoint
inventory for the currently running build. Older completion reports and UI audit
notes may mention additional browser pages or retired compatibility paths that
should not be treated as the supported release surface.

## Related Docs

- Install:
  [`docs/guides/install/INSTALL.md`](../guides/install/INSTALL.md)
- Quickstart:
  [`docs/guides/install/QUICKSTART.md`](../guides/install/QUICKSTART.md)
- CLI reference:
  [`docs/CLI-REFERENCE.md`](../CLI-REFERENCE.md)
- UI status:
  [`docs/guides/ui/JUSTIFICATION_UI.md`](../guides/ui/JUSTIFICATION_UI.md)
