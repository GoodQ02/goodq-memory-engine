<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-20 -->

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
- Read-only operator console: `GET /ui/operator_console_v1/`
- Read-only envelope renderer: `GET /ui/justification_v1/`
- `LAUNCH_GOODQ` does not start the API process by default

## Canonical Endpoint Families

Primary status and runtime summary endpoints defined in the active API surface:

- `api/routes/runtime.py` is the read-only aggregation surface for runtime state.
- It exists to answer "what is happening right now?" without turning into a control, mutation, or execution plane.

- `GET /api/status`
- `GET /api/health/summary`
- `GET /api/storage/summary`
- `GET /api/engines`
- `GET /api/queue`
- `GET /api/gpu/stats`
- `GET /api/wsl2-status`
- `GET /api/runs/latest/preview`
- `GET /api/runs/latest/evidence`
- `GET /api/runs/audio-proof/latest`
- `GET /api/memory/stats`
- `GET /api/read/envelope`
- `GET /api/system/videos`
- `GET /api/videos/{video_id}/timeline/full`
- `GET /api/videos/{video_id}/scenes`
- `GET /api/control-recurrence/reports`
- `GET /api/control-recurrence/reports/latest`
- `GET /api/control-recurrence/reports/trend`
- `GET /api/control-recurrence/reports/{report_id}`
- `GET /api/control-recurrence/reports/{report_id}/markdown`
- `GET /api/control-recurrence/reports/{report_id}/recommendations`

`GET /api/runs/latest/preview` is a read-only projection over indexed run artifacts under `reports/fresh_ingest_runs`.
It does not revive the retired `/runs` compatibility shell, and it does not parse raw logs as a primary source of truth.
If a clone uses a shared witness-report tree instead of a repo-local one, set
`GOODQ_RUN_REPORTS_ROOT` to point the read-only run surfaces at that artifact root.
The run index supports both wrapper-ledger roots with root `experiment_log.json`
and standalone/direct roots that expose `output/scene_ingest_results.json`.
Standalone roots are labeled with `scope=scene_ingest_results`; they are not
presented as structured wrapper-ledger runs. Both `/api/runs/latest/preview`
and `/api/runs/latest/evidence` expose `run_kind` and `scope` so UI consumers
can explain missing wrapper-only artifacts without treating them as pipeline
failures.

`GET /api/runs/latest/evidence` reports proof for the currently indexed latest
run scope. Its `audio_vector_proof` object is the strict current-run
CLAP/Qdrant verdict for that scope. When standalone scene results expose a
unique `audio.clap_meta.run_id`, the projector uses that runtime provenance id
for the Qdrant comparison instead of the report-folder slug. If
`temporal_index.json` is not co-located with the report but a standalone
`scene_ingest_results.json` exposes a valid `temporal_index_path`, the projector
follows that explicit read-only pointer. If no temporal index is available, the
`sentiment` object can still report transcript, audio-emotion, and sentiment
counts from `scene_ingest_results.json` with `source=scene_ingest_results`.

`GET /api/runs/audio-proof/latest` is a separate read-only Qdrant inventory. It
lists run-tagged audio payloads with required provenance fields so operators can
see that audio proof exists historically. It must not be used to turn the
latest-run `audio_vector_proof` green unless the payload `run_id` matches the
run being audited.

`GET /api/memory/stats` exposes storage-tier counts. `faiss.audio_vectors` is a
FAISS index count only and is not current-run Qdrant audio-vector proof. Use
the response `audio_vector_semantics` object and
`docs/architecture/AUDIO_VECTOR_PROVENANCE_CONTRACT.md` before presenting any
current-run CLAP/Qdrant coverage label.

Router-backed endpoint families mounted into the same process:

- `/api/search`
- `/api/ingest`
- `/api/timeline`
- `/api/media`
- `/api/system`
- `/api/control-recurrence`
- `/api/videos/{video_id}/scenes`

## Browser UI Surfaces

The API process serves two read-only browser surfaces:

- `/ui/operator_console_v1/` is the current operator console. It consumes the
  read-only API and persisted artifacts for Flight Deck status, proof/evidence,
  retrieval inspection, storage/runtime summaries, recurrence report readouts,
  video inventory, scene/timeline projections, and the compact audio provenance
  inventory drilldown.
- `/ui/justification_v1/` is the literal Justification Channel envelope
  renderer.

Neither surface is a control plane. They do not trigger ingestion, reindex
memory, heal configs, mutate persistence, generate recurrence reports, or
activate ControlAgent. API `GET /` intentionally remains JSON discovery rather
than a browser shell.

## Discovery Surfaces

- `GET /` is a minimal process-health and discovery pointer.
- `GET /api` is a curated human index, not a canonical API inventory.
- Keep `/api` intentionally incomplete so it stays useful as a front desk rather than drifting into a second contract surface.
- Use `/docs` and `/openapi.json` for the authoritative live inventory of supported endpoints.

## Control Recurrence API

`/api/control-recurrence` is a read-only service window over the durable recurrence artifacts under `reports/control_recurrence/`.

- `GET /api/control-recurrence/reports` reads `reports/control_recurrence/index.json` and returns the parsed index, or a structured empty response when the index is missing.
- `GET /api/control-recurrence/reports/latest` returns the newest indexed report entry by `created_or_updated_at` or indexed artifact mtime.
- `GET /api/control-recurrence/reports/trend` returns a derived read-only trend over indexed durable JSON reports.
- `GET /api/control-recurrence/reports/{report_id}` returns the indexed durable JSON report content when `json_path` is present.
- `GET /api/control-recurrence/reports/{report_id}/markdown` returns indexed markdown content as `text/plain` when `markdown_path` is present.
- `GET /api/control-recurrence/reports/{report_id}/recommendations` returns a deterministic read-only operator inspection draft from the indexed durable JSON report.

Examples:

```powershell
curl http://127.0.0.1:30000/api/control-recurrence/reports
```

```powershell
curl http://127.0.0.1:30000/api/control-recurrence/reports/latest
```

```powershell
curl http://127.0.0.1:30000/api/control-recurrence/reports/trend
```

```powershell
curl http://127.0.0.1:30000/api/control-recurrence/reports/20260424_182406_season2_fresh_witness
```

```powershell
curl http://127.0.0.1:30000/api/control-recurrence/reports/20260424_003250_season1_recompare_witness__vs__20260424_182406_season2_fresh_witness/markdown
```

```powershell
curl http://127.0.0.1:30000/api/control-recurrence/reports/20260424_003250_season1_recompare_witness__vs__20260424_182406_season2_fresh_witness/recommendations
```

Boundary: the API does not generate reports, heal, mutate configs, activate `ControlAgent`, execute commands, use LLMs, trigger ingestion, or touch `cli/run_ingestion.py`. Recommendation drafts are inspection-only and carry no execution authority. The API only reads the existing index and indexed artifacts under `reports/control_recurrence/`.

## Retired Legacy Surfaces

The active line no longer exposes the older compatibility shell that previously lived in `api/main.py`.

- Removed legacy search pointers: `/search`, `/vector_search`
- Removed legacy scene and graph mirrors: `/api/scenes`, `/api/knowledge_graph`, `/api/scene/{scene_id}`
- Removed legacy analytics placeholders: `/api/analytics/*`
- Removed legacy operator/debug stubs: `/api/command-center`, `/api/processes`, `/api/progress`, `/api/processing/stats`, `/api/logs/watchdog`, `/api/test-audio`, `/api/chat/control-agent`
- Removed broken run read shells: `/runs`, `/runs/{run_id}`

## Active Search and Scene Retrieval Notes

- `POST /api/search/multimodal` is the canonical multimodal search surface.
- `modalities=["audio"]` is a supported request path on the active line.
- If `modalities` is omitted, the current default remains text + visual.
- `GET /api/videos/{video_id}/scenes/{scene_id}/similar` is live and resolves similar scenes from persisted multimodal scene memory.
- Similar-scene retrieval now uses text, visual, and audio signals where available instead of returning an empty fallback path.
- Audio-vector coverage in API and retrieval read models must follow
  `docs/architecture/AUDIO_VECTOR_PROVENANCE_CONTRACT.md`: current-run audio
  vector success requires `clap_meta.status == ok` plus a Qdrant audio payload
  with matching `run_id` and required provenance fields. A matching `scene_id`
  alone is not current-run proof.
- Active CLAP scene outputs now echo safe provenance fields in
  `audio.clap_meta` when available: `run_id`, `embedding_id`, `commit_ts_utc`,
  `qdrant_attempted`, `qdrant_committed`, and `qdrant_collection`. These fields
  help link scene artifacts to the Qdrant inventory but still do not replace
  the strict current-run proof check above.

## System Mutation Policy

- `POST /api/system/ingest` is intentionally disabled on the active line.
- The active ingest write surface is the truthful facade:
  - `POST /api/ingest/submit`
  - `GET /api/ingest/status/{request_id}`
- If an ingest API surface is introduced later, it must be:
  - explicit
  - confirmation-gated
  - policy-driven
  - budgeted
  - checkpointed
  - auditable
- Any future ingest route must remain a controlled facade over the canonical runtime path rather than a second ingest engine.
- The active ingest facade stages a single supported local file into the canonical inbox, writes a durable request record, and returns a request handle.
- The active ingest facade does not execute ingestion, manage a second job engine, bypass watchdog, or mutate memory directly.
- The current supported ingest surfaces remain:
  - `POST /api/ingest/submit` for request intake only
  - `GET /api/ingest/status/{request_id}` for request-centric lifecycle status
  - `conda run -n goodq_core python -m cli.watchdog`
  - `conda run -n goodq_core python -m cli.run_ingestion --input-dir <path>`
  - the configured `<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox`
- `POST /api/system/reindex` and `POST /api/system/reload` remain operator-only and intentionally unavailable as public API mutation routes on the active line.

## Scene API Truth

- Scene responses now project the persisted continuity and speaker-truth layer directly from runtime artifacts.
- Active scene read models include fields such as `speaker_count`, `dominant_speaker_id`, `continuity_key`, `diarization_status`, `emotion_status`, `speaker_voice_signature_count`, `speaker_voice_signature_meta`, `audio_emotion`, `time_hints`, `content_state`, `candidate_visible_people`, `speaker_aligned_mentions`, `transcript_entity_disagreements`, `normalization_applied`, `normalization_source`, `interaction_dominance`, and `conversation_owner`.
- Search, scene, and timeline responses now also expose `sentiment`, `sentiment_label`, and `sentiment_score` as first-class outward fields.
- Sentiment is descriptive only on the active line; it should inform interpretation without silently dictating ranking or replacing stronger multimodal evidence.
- `normalization_applied` and `normalization_source` are projection-only instrumentation for exact-pair reconciliation pilots. They do not mutate raw transcript, KG truth, identity promotion, or retrieval.

## Timeline API Truth

- `GET /api/videos/{video_id}/timeline/full` is the primary read-only projection of persisted temporal truth.
- Timeline metadata now includes additive visibility rollups for the interaction ladder and transcript/entity seam:
  - `segments_with_candidate_visible_people`
  - `segments_with_interaction_dominance`
  - `segments_with_conversation_owner`
  - `segments_with_speaker_aligned_mentions`
  - `segments_with_transcript_entity_disagreements`
  - `segments_with_full_name_partial_entity_disagreements`
  - `top_candidate_visible_people`
  - `top_interaction_dominance`
  - `top_conversation_owners`
  - `top_speaker_aligned_mentions`
  - `transcript_entity_disagreement_category_counts`
  - `top_transcript_full_name_partial_entity_families`
  - `top_transcript_entity_disagreement_families`
- These are read-only operator surfaces over persisted scene truth. They do not change KG writes, identity promotion, or retrieval ranking.

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
