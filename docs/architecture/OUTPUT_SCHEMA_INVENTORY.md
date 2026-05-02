<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-29 -->

# Output Schema Inventory

This document inventories the active GoodQ4All output surfaces that future UI,
API, Codex, and operator layers are allowed to consume.

It does not introduce a new runtime schema, execution path, validator, or
mutation layer. It is a read-only map of existing persisted artifacts and
derived read models.

## Scope

Covered surfaces:

- `scene_manifest.json`
- `temporal_index.json`
- `scene_ingest_results.json`
- run summary projection
- audio vector provenance
- control recurrence reports
- control recurrence recommendation drafts
- API previews and read models

Not covered here:

- raw media files
- raw model caches
- raw databases except as upstream persistence behind API/read-model surfaces
- historical archived schema drafts

## Field Status Legend

| Status | Meaning |
| --- | --- |
| `authoritative` | The field is a truth surface for its scope and should be preferred over derived copies. |
| `derived` | The field is computed from authoritative surfaces and must not override them. |
| `operator` | The field is for audit, diagnosis, or local operations. It is not product-facing truth by itself. |
| `ui_safe` | The field may be exposed in local UI/API surfaces after normal path and privacy hygiene. |
| `local_only` | The field may contain local paths, runtime details, raw errors, or machine-specific evidence. Do not expose broadly. |
| `compatibility` | The field exists for older consumers or transitional read models. Prefer the active field when available. |

## Surface Map

| Surface | Owner | Primary Role | Authority | UI Boundary |
| --- | --- | --- | --- | --- |
| `scene_manifest.json` | `cli/run_ingestion.py`, Phase 6 | Canonical per-video scene bundle | authoritative per scene | selected scene, modality, and truth fields are `ui_safe`; paths/errors are `local_only` |
| `temporal_index.json` | `steps/video/cross_modal_harmonizer.py` | Canonical multimodal rollup | authoritative per video timeline and rollups | timeline segments and aggregate counts are `ui_safe`; raw paths remain `local_only` |
| `scene_ingest_results.json` | `cli/run_ingestion.py` | Canonical run output summary | authoritative per ingestion output file | run/video status fields are `ui_safe`; embedded paths and raw errors are `local_only` |
| run summary projection | `lib/run_summary.py` | Read-only wrapper-run summary | derived | local dashboard/operator preview only |
| control recurrence report | `lib/control_recurrence_report.py` | Read-only recurrence intelligence | derived from persisted artifacts | operator-facing and `ui_safe` after path hygiene |
| control recurrence index | `lib/control_recurrence_index.py` | Discoverable report filing cabinet | derived index | `ui_safe` when paths are relative/sanitized |
| recommendation draft | `lib/control_recurrence_recommendations.py` | Deterministic inspection plan | derived from durable recurrence JSON | operator-facing; no execution authority |
| API previews | `api/routes/runtime.py`, API routers | Local read-model projections | derived | `ui_safe` local API surface |

## Canonical Artifact Hierarchy

Use this precedence when the same fact appears in more than one surface:

1. `scene_manifest.json` for per-scene persisted truth.
2. `temporal_index.json` for per-video timeline rollups and harmonized segment summaries.
3. `scene_ingest_results.json` for per-run/video ingestion outcome and final output summary.
4. Run summary/API preview surfaces for local read-only status projections.
5. Control recurrence reports for cross-artifact recurrence intelligence.
6. Recommendation drafts for deterministic operator inspection steps.

Derived surfaces may summarize, classify, or reformat canonical truth. They must
not silently override canonical artifact fields.

## `scene_manifest.json`

Location:

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video_name>/video/scene_manifest.json
```

Primary contract:

- canonical per-video scene bundle
- consumed by Phase 6 visual embeddings and cross-modal harmonization
- later re-read by API loaders, identity rebuilds, and recurrence tools

### Top-Level Fields

| Field | Status | Notes |
| --- | --- | --- |
| `video_id` | authoritative, ui_safe | Stable video identifier for the manifest scope. |
| `video_path` | authoritative, local_only | Source path; sanitize or omit in broad UI. |
| `phase5_complete` | authoritative, ui_safe | Scene bundle completion truth after Phase 5. |
| `phase6_status` | authoritative, ui_safe | Phase 6 status when present. |
| `phase6_complete` | authoritative, ui_safe | Canonical Phase 6 completion truth for the video bundle. |
| `total_scenes` | authoritative, ui_safe | Must align with `len(scenes)` after harmonization. |
| `content_summary` | authoritative, ui_safe | Counts of `signal`, `empty`, and `processing_error`. |
| `scenes` | authoritative | Canonical scene objects. |

### Scene Fields

| Field Family | Representative Fields | Status | Notes |
| --- | --- | --- | --- |
| Identity and bounds | `scene_id`, `index`, `start`, `end`, `duration`, `confidence` | authoritative, ui_safe | Atomic scene identity and timing. |
| Content state | `content_state` | authoritative, ui_safe | Expected values include `signal`, `empty`, and `processing_error`. |
| Vector truth | `clip_id`, `dino_id`, `qdrant_ok`, `faiss_ok`, `vector_points_attempted` | authoritative, ui_safe | Qdrant/FAISS status is scene-level store truth. |
| Speaker truth | `speaker_ids`, `speaker_count`, `dominant_speaker_id`, `dominant_speaker_share`, `dominance_confidence` | authoritative, ui_safe | Speaker labels are structural unless stitched to identity elsewhere. |
| Continuity | `continuity_key`, `conversation_speaker_ids` | authoritative, ui_safe | Supports cross-scene continuity views. |
| Keyframe payload | `keyframe` | authoritative | See keyframe table below. |
| Audio payload | `audio` | authoritative | See audio table below. |
| Harmonized context | `scene_context_llm`, `scene_context_epistemic`, `scene_context_arbitration` | authoritative additive fields | Interpretive but persisted; do not treat as raw evidence replacement. |
| Interaction fields | `candidate_visible_people`, `speaker_aligned_mentions`, `interaction_dominance`, `conversation_owner` | authoritative additive fields, ui_safe | Conservative read-model fields, not automatic identity promotion. |
| Perception rollups | `visible_person_object_count`, `music_events`, `time_hints`, `audio_emotion`, `speaker_voice_signature_count` | authoritative additive fields, ui_safe | Derived from modality payloads and persisted back to the manifest. |
| Status and errors | `diarization_status`, `diarization_error`, `emotion_status`, `emotion_error`, `diarization_note` | authoritative/operator | Status is UI-safe; raw errors are operator/local-only. |

### Keyframe Payload

| Field Family | Representative Fields | Status | Notes |
| --- | --- | --- | --- |
| Local frame reference | `path` | authoritative, local_only | Local artifact path; do not expose as broad product text. |
| Timing | `timestamp`, `scene` | authoritative, ui_safe | Representative frame timing. |
| Visual text and caption | `ocr_text`, `caption`, `caption_meta`, `frame_text` | authoritative, ui_safe | Caption quality is represented by meta status, not only step success. |
| Objects and faces | `objects`, `detect_meta`, `faces`, `faces_meta` | authoritative, ui_safe | Optional enrichments may be empty or unavailable. |
| Embedding metadata | `dino_meta`, `clip_meta` | authoritative/operator | Useful for vector health inspection. |
| Tags and entities | `tags`, `entities`, `usefulness` | authoritative/derived | Scene-level visual interpretation support. |
| Error details | `keyframe_error`, `keyframe_error_step`, `keyframe_error_env`, `keyframe_error_raw` | operator, local_only | Preserve for audits; do not flatten into generic failure text. |

### Audio Payload

| Field Family | Representative Fields | Status | Notes |
| --- | --- | --- | --- |
| Local audio reference | `path` | authoritative, local_only | Scene audio artifact path. |
| Timing | `start`, `end`, `duration` | authoritative, ui_safe | Scene audio window. |
| Backend truth | `audio_backend_selected`, `audio_backend_effective`, `audio_backend_downgraded` | authoritative, ui_safe | Distinguishes selected backend from actual effective backend. |
| Transcript | `transcript`, `transcript_meta`, `segments` | authoritative, ui_safe | Transcript payload is canonical scene text evidence. |
| Diarization | `diarization`, `diarization_meta`, `diarization_status`, `diarization_error` | authoritative/operator | Status is UI-safe; raw errors are local/operator. |
| Speaker alignment | `speaker_transcript`, `speaker_voice_signatures`, `speaker_voice_signature_meta` | authoritative/operator | Voice signatures support stitching but do not equal identity by themselves. |
| Emotion | `emotions`, `emotion_meta`, `emotion_status`, `emotion_error` | authoritative/operator | Optional enrichment; unavailable is not necessarily failure. |
| CLAP status | `clap_meta.status`, `clap_meta.reason` | authoritative/operator, ui_safe summary | Current-run audio vector coverage requires `clap_meta.status == ok` plus matching Qdrant run provenance. |
| Embeddings | `embeddings`, `embedding_dim` | authoritative/operator | Internal vector payload and dimensionality. This field alone does not prove current-run Qdrant audio-vector success. |
| Runtime attribution | `wsl2_unified`, `gpu_used`, device/engine meta fields | operator | Useful for runtime audits; not product-facing truth. |

## Audio Vector Provenance

Contract:

```text
docs/architecture/AUDIO_VECTOR_PROVENANCE_CONTRACT.md
```

Primary rule:

- current-run audio vector success is proven only by `clap_meta.status == ok`
  and a Qdrant audio payload with matching `run_id` and required provenance
  fields
- matching `scene_id` alone is not proof
- legacy audio vectors with missing `run_id` are provenance-unverified, not
  current-run success
- Qdrant audio points with a different `run_id` are stale for the audited run
- `clap_meta.status == skipped` or `clap_meta.status == error` must not be
  counted as current-run audio vector coverage

Required Qdrant audio payload fields for active-line CLAP commits:

- `run_id`
- `embedding_id`
- `component`
- `step`
- `model`
- `created_at`
- `commit_ts_utc`

Preferred read-model labels:

- `current_run_audio_vector_proven`
- `provenance_unverified_audio_vector_exists`
- `legacy_audio_vector_present`
- `audio_vector_absent`
- `audio_vector_skipped`
- `audio_vector_error`

Avoid using unqualified `audio_vector_exists` as a current-run success claim.
If compatibility requires it, pair it with an explicit provenance field.

## `temporal_index.json`

Location:

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video_name>/temporal_index.json
```

Primary contract:

- canonical per-video multimodal rollup
- built from the persisted scene bundle
- used by timeline, scene read models, API projections, and recurrence health checks

### Top-Level Fields

| Field Family | Representative Fields | Status | Notes |
| --- | --- | --- | --- |
| Identity and duration | `version`, `video_id`, `video_hash`, `video_path`, `total_scenes`, `total_duration` | authoritative | `video_path` is local-only; counts and ids are UI-safe. |
| Segments | `segments` | authoritative | Canonical timeline segment array. |
| Entity rollups | `total_entities`, `unique_entities`, `top_entities`, `top_scene_present_entities`, `top_dialogue_mentioned_entities` | authoritative derived rollups, ui_safe | Rollups summarize persisted segment truth. |
| Presence and interaction counts | `segments_with_visible_people`, `segments_with_candidate_visible_people`, `segments_with_interaction_dominance`, `segments_with_conversation_owner`, `segments_with_speaker_aligned_mentions` | authoritative derived rollups, ui_safe | UI-safe aggregate counts. |
| Perception counts | `segments_with_music_events`, `segments_with_time_hints`, `segments_with_audio_emotion`, `segments_with_speaker_voice_signatures` | authoritative derived rollups, ui_safe | Optional enrichment coverage. |
| Context counts | `segments_with_scene_context_llm`, `segments_with_scene_context_epistemic`, `segments_with_scene_context_arbitration`, `segments_with_scene_context_arbitration_conflicts` | authoritative derived rollups, ui_safe | Counts of additive context surfaces. |
| Top rollups | `top_visible_people`, `top_mentioned_people`, `top_candidate_visible_people`, `top_interaction_dominance`, `top_conversation_owners`, `top_speaker_aligned_mentions`, `top_music_events`, `top_time_hints`, `top_audio_emotions`, `top_scene_context_tags` | authoritative derived rollups, ui_safe | Operator/UI summary rows. |
| Transcript disagreement rollups | `transcript_entity_disagreement_*`, `top_transcript_*_families` | derived/operator, ui_safe | Operator visibility over scene truth disagreements. |
| Modality summary | `has_visual_embeddings`, `has_audio`, `has_transcripts`, `committed_modalities`, `content_summary` | authoritative derived rollups, ui_safe | Health and coverage summary. |
| Phase status | `phase5_complete`, `phase6_complete`, `phase6_harmonized`, `phase6_warning`, `harmonization_status` | authoritative, ui_safe/operator | Warning/status fields should remain visible to operators. |

### Segment Fields

Temporal segments mirror harmonized scene truth. Common fields include:

- `scene_id`
- `start`, `end`, `duration`
- `content_state`
- `clip_id`, `dino_id`
- `representative_frame`, `frame_count`
- `audio_chunks`
- `speaker_ids`, `speaker_count`, `dominant_speaker_id`
- `keywords`, `entities`
- `scene_present_entities`, `dialogue_mentioned_entities`
- `visible_people`, `mentioned_people`, `candidate_visible_people`
- `speaker_aligned_mentions`
- `scene_locations`, `dialogue_topics`
- `transcript_segments`, `full_transcript`
- `has_visual_embeddings`, `has_audio`, `has_transcript`, `has_speakers`
- `visible_face_count`, `visible_person_object_count`
- `speaker_voice_signature_count`, `speaker_voice_signature_meta`
- `diarization_status`, `diarization_error`, `diarization_note`
- `music_events`, `time_hints`, `metadata_time_hints`
- `audio_emotion`, `audio_emotion_scores`
- `emotion_status`, `emotion_error`
- `scene_context_llm`, `scene_context_epistemic`, `scene_context_arbitration`
- `interaction_dominance`, `conversation_owner`
- `continuity_key`

Use segment fields for timeline and comparison views. Use the manifest scene
entry when a per-scene artifact path, raw payload, or exact persistence state is
needed.

## `scene_ingest_results.json`

Default location:

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/outputs/scene_ingest_results.json
```

Primary contract:

- canonical output summary written by `cli/run_ingestion.py`
- JSON array, one result object per processed video
- authoritative for final ingestion outcome at the run output boundary

### Video Result Fields

| Field Family | Representative Fields | Status | Notes |
| --- | --- | --- | --- |
| Video identity | `video_path`, `video_hash`, `video_id`, `video_name` | authoritative | `video_path` is local-only; ids/names are UI-safe. |
| Scene payload | `scenes` | authoritative output copy | Rehydrated from manifest after harmonization when available. |
| Scene summary | `phase5_complete`, `total_scenes`, `content_summary` | authoritative at output boundary, ui_safe | Must align with manifest and temporal index after harmonization. |
| Audio backend | `audio_artifact_dir`, `audio_backend_selected`, `audio_backend_effective`, `audio_backend_downgraded`, `audio_backend_events`, `audio_runtime_contract` | authoritative/operator | Paths and detailed events are local/operator-only. |
| Vector/storage health | `qdrant_ok`, `faiss_ok`, `phase6_qdrant_ok`, `modality_status` | authoritative/operator, ui_safe summary | Use for health summaries; inspect scene/temporal for detail. |
| Control and KG status | `control_agent_status`, `control_agent_reason`, `knowledge_graph_status` | operator, ui_safe | ControlAgent disabled state is explicit runtime truth. |
| Orchestration | `orchestration`, `segmentation_shadow`, `phase6_audio_overlay` | operator | Read-only contract evidence; not UI product truth by default. |
| Phase 6 | `phase6_complete`, `phase6_error`, `phase6_skipped`, `phase6_skip_reason`, `temporal_index`, `temporal_index_path` | authoritative/operator | Embedded `temporal_index` is a copy; path is local-only. |
| Optional summaries | `video_summary`, `video_summary_method` | derived/feature-gated | Present only when summarization is enabled. |

## Run Summary Projection

Module:

```text
lib/run_summary.py
```

Primary contract:

- read-only projection over wrapper-style run roots
- reads `experiment_log.json` and per-episode records
- not a canonical replacement for scene artifacts

### Top-Level Fields

| Field | Status | Notes |
| --- | --- | --- |
| `run_header` | derived, ui_safe | Run id, epoch, status, source, start/end, duration, trigger source. |
| `file_job_overview` | derived, ui_safe | Input files, episode counts, scenes processed, step count placeholder. |
| `audio_wsl2_summary` | derived/operator | Summary surface, may be `unknown` or `not observed`. |
| `agent_activity` | derived/operator | Currently an activity list, not execution authority. |
| `errors_warnings` | derived/operator | Summarized wrapper/episode warnings and errors. |
| `outcome_classification` | derived, ui_safe | `running`, `success`, `partial_success`, `failed`, or `unknown`. |
| `evidence` | operator, local_only | Files read and canonical artifacts; sanitize before UI display. |
| `latest_episode` | derived, ui_safe | Latest episode record or active/pending lane. |
| `episodes` | derived, ui_safe/operator | Per-episode records. |

## Control Recurrence Reports

Default durable location:

```text
reports/control_recurrence/<report_id>.json
```

Primary contract:

- read-only recurrence intelligence from persisted truth surfaces
- no ControlAgent activation
- no healing
- no config mutation
- no ingestion or report generation from the API

### Single-Run Report Fields

| Field | Status | Notes |
| --- | --- | --- |
| `report` | authoritative for report metadata | Includes name, timestamp, mode, disabled control/healing boundary, and truth surfaces. |
| `scope` | derived/operator | Run roots, episodes, runtime ids, videos, signal counts, step-run files. |
| `recurrence_summary` | derived/operator, ui_safe | Grouped recurrence signals. |
| `top_repeated_failure_families` | derived/operator, ui_safe | Family rows with category/hints when available. |
| `optional_enrichment_skips` | derived/operator, ui_safe | Skips such as no text, silent audio, or expected optional conditions. |
| `recovered_vs_unrecovered_failures` | derived/operator, ui_safe | Recovery outcome counts. |
| `scenes_affected` | derived/operator, ui_safe | Affected scene grouping. |
| `phase6_qdrant_truth` | derived from canonical artifacts, ui_safe | Final Phase 6/Qdrant health summary. |
| `recurrence_classification` | derived/operator, ui_safe | Category counts and highest category. |
| `recommendation` | derived/operator, ui_safe | Pass/warn/fail recommendation, not an action plan. |
| `operator_hints` | derived/operator, ui_safe | Deterministic inspection hints. |
| `inspection_targets` | derived/operator, ui_safe | Read-only places to inspect. |
| `evidence` | operator, local_only | Files read and warnings; path hygiene required. |

### Comparison Report Fields

| Field | Status | Notes |
| --- | --- | --- |
| `report` | authoritative for report metadata | Name is `control_recurrence_comparison`. |
| `baseline` | derived/operator | Baseline run summary. |
| `candidate` | derived/operator | Candidate run summary. |
| `delta` | derived/operator, ui_safe | Signal, family, step, episode, Phase 6, and Qdrant deltas. |
| `recommendation` | derived/operator, ui_safe | Pass/warn/fail comparison recommendation. |
| `operator_hints` | derived/operator, ui_safe | Candidate-focused deterministic hints. |
| `inspection_targets` | derived/operator, ui_safe | Read-only inspection targets. |
| `evidence` | operator, local_only | Combined files read and warnings. |

## Control Recurrence Index

Default location:

```text
reports/control_recurrence/index.json
```

Primary contract:

- discoverable index over durable recurrence artifacts
- generated/updated only by explicit CLI export/listing behavior
- read by the control recurrence API

### Index Entry Fields

| Field | Status | Notes |
| --- | --- | --- |
| `report_type` | derived, ui_safe | `single_run` or `comparison`. |
| `report_id` | derived, ui_safe | Stable report artifact id. |
| `run_id` | derived, ui_safe | Single-run report id. |
| `baseline_run_id`, `candidate_run_id` | derived, ui_safe | Comparison report ids. |
| `markdown_path`, `json_path` | derived/operator | Must be relative or sanitized. |
| `artifact_status` | derived/operator, ui_safe | Examples: `complete`, `json_only`, `markdown_only`. |
| `recommendation_status` | derived, ui_safe | Indexed recommendation status. |
| `highest_category` | derived, ui_safe | Highest recurrence category. |
| `total_signals` | derived, ui_safe | Total recurrence signals. |
| `blocking_signal_count` | derived, ui_safe | Blocking signal count. |
| `phase6_health_summary`, `qdrant_health_summary` | derived, ui_safe | Indexed health summaries. |
| `created_or_updated_at` | derived/operator | Report metadata timestamp or artifact mtime. |

Local untracked `reports/control_recurrence/index.json` state is workspace
artifact hygiene unless explicitly tracked.

## Recommendation Drafts

CLI/API surfaces:

```text
python -m cli.control_recurrence_report --recommendations-for <report_id>
GET /api/control-recurrence/reports/{report_id}/recommendations
```

Primary contract:

- deterministic inspection draft from an existing durable recurrence JSON report
- no LLMs
- no commands
- no healing
- no config mutation
- no ingestion
- no report generation

### Draft Fields

| Field | Status | Notes |
| --- | --- | --- |
| `status` | derived, ui_safe | `ok` or structured error state. |
| `report_id` | derived, ui_safe | Indexed recurrence report id. |
| `report_type` | derived, ui_safe | Single-run or comparison context. |
| `recommendation_status` | derived, ui_safe | Inherited from report recommendation. |
| `highest_category` | derived, ui_safe | Inherited or computed from report classification. |
| `blocking_summary` | derived/operator, ui_safe | Blocking count, families, Phase 6 health, Qdrant health. |
| `top_operator_priorities` | derived/operator, ui_safe | Deterministic inspection priorities. |
| `inspection_plan` | derived/operator, ui_safe | Read-only steps only. |
| `defer_mutation_reason` | derived/operator, ui_safe | Plain reason mutation is not taken. |
| `safety_boundary` | authoritative for draft boundary | States no ControlAgent, healing, config mutation, command execution, report generation, ingestion, or LLM usage. |

## API Previews and Read Models

Primary API discovery:

```text
GET /docs
GET /openapi.json
```

Supported read-model examples:

- `GET /api/runs/latest/preview`
- `GET /api/control-recurrence/reports`
- `GET /api/control-recurrence/reports/latest`
- `GET /api/control-recurrence/reports/{report_id}`
- `GET /api/control-recurrence/reports/{report_id}/markdown`
- `GET /api/control-recurrence/reports/{report_id}/recommendations`
- `GET /api/timeline/full`
- `GET /api/videos/{video_id}/scenes/{scene_id}/similar`

### `/api/runs/latest/preview`

| Field | Status | Notes |
| --- | --- | --- |
| `available` | derived, ui_safe | False when no structured run root is available. |
| `run_id`, `status`, `epoch`, `source_dir` | derived, ui_safe/operator | `source_dir` may need path hygiene depending on deployment. |
| `start_time`, `end_time`, `total_duration_seconds` | derived, ui_safe | Runtime timing projection. |
| `episodes_total`, `episodes_completed`, `episodes_failed`, `episodes_running`, `episodes_pending` | derived, ui_safe | Wrapper-run status counts. |
| `scenes_processed` | derived, ui_safe | Sum from episode records. |
| `latest_episode` | derived, ui_safe/operator | Latest or active episode projection. |

API previews are local read-only conveniences. They are not canonical artifact
owners and must not introduce ingestion, report generation, or healing behavior.

## UI Consumption Rules

1. Prefer `temporal_index.json` for timeline and aggregate views.
2. Prefer `scene_manifest.json` for per-scene persisted truth and modality payload detail.
3. Use `scene_ingest_results.json` for run/video output status, not as the only scene truth.
4. Use run summary/API preview surfaces for dashboards, not as persistence authority.
5. Use control recurrence reports for recurrence intelligence, not for execution.
6. Use recommendation drafts as inspection plans only.
7. Treat local paths, raw errors, files-read lists, stderr/stdout tails, and machine-specific evidence as `local_only`.
8. Do not expose raw absolute drive roots or machine-specific paths in forward-facing UI.
9. Do not convert read-only recommendations into buttons that mutate config, trigger ingestion, or invoke healing.

## Known Inventory Limits

- This is an authoritative inventory, not a machine-enforced JSON Schema set.
- Some optional enrichment fields are sparse by design.
- Compatibility fields may exist in older artifacts; current write contracts should prefer the active fields listed above.
- Archived reports may contain obsolete paths or field names and should not be treated as active schema authority.
