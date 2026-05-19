# Pipeline Surface Audit - 2026-05-19

Purpose: verify that high-value pipeline intelligence moves from durable artifacts into API/read-model surfaces and the operator console without being hidden or mislabeled.

## Baseline

- Fresh scene probe run: `e5bb2140-008b-4a7a-89dc-11a8aee4d89e`
- Fresh scene probe video: `family_2002_school_music_probe_sentiment`
- Fresh scene count: `1`
- Private API base for fresh probe validation: `http://127.0.0.1:30000`
- Current public/demo browser API base: `http://127.0.0.1:30003`
- Scope note: `30000` sees the fresh scratch probe; `30003` is a public witness/demo surface and is not expected to show the fresh scratch probe.

## Audit Matrix

| Feature | Artifact Truth | API Projection | UI Surface | Status | Evidence | Next Action |
|---|---|---|---|---|---|---|
| Sentiment | Present in `scene.audio.sentiment` and top-level scene after fix | Present in `/timeline/full` and `/scenes` | Existing UI can consume API sentiment fields | Cleared | `sentiment=POSITIVE`, `sentiment_score=1.0` | Keep regression tests |
| Visual vectors | CLIP and DINO committed in Phase 6 | Present as `clip_id` and `dino_id` | Proof panel can show vector proof state | Cleared for IDs | `phase6_vector_commit.clip_committed=true`, `dino_committed=true` | Later: current-run vector proof wording |
| Keyframe caption | Present in `scene.keyframe.caption` and harmonized `visual_caption` | Present in `/timeline/full` and `/scenes` as `visual_caption` | Public operator Scene Inspector renders visual caption evidence | Cleared | Artifact/API/UI guard use `a girl playing a trumpet in a room` | Keep regression tests |
| OCR text | Present in `scene.keyframe.ocr_text` and harmonized `ocr_text` | Present in `/timeline/full` and `/scenes` as `ocr_text` plus `ocr_date_candidates` | Public operator Scene Inspector renders OCR text and OCR date candidates | Cleared | Artifact/API/UI guard use `DEC 16 2002` | Keep regression tests |
| Time hints | Present in scene and temporal index | Present in `/timeline/full` and `/scenes` | Visible in evidence/proof surfaces where wired | Cleared | `explicit_dates=["2002-12-16"]`, `months=["december"]` | Keep scope labels clear |
| Transcript | Present in scene audio payload and temporal segment | Present in `/timeline/full` and `/scenes` | Visible in raw/scene surfaces where wired | Cleared | Transcript begins `Thank you. Thank you very much.` | Later: transcript quality label |
| Audio emotion scores | Present as low-confidence candidate score distribution | Present in `/timeline/full` and `/scenes` as `audio_emotion_scores` | Public operator Scene Inspector renders review-oriented candidate detail | Cleared | Regression guard uses `{"neutral": 0.48, "calm": 0.31, "sad": 0.21}` | Keep review wording separate from hard labels |
| Hard audio emotion label | Strictly absent because score is below promotion threshold | `audio_emotion=null` | Should read as low-confidence candidates, not failure | Cleared semantics | `emotion_status=success`, `audio_emotion=null` | UI wording pass |
| CLAP audio commit | Present in `scene.audio.clap_meta` | Present in `/timeline/full` and `/scenes` as `clap_meta` | Public operator Scene Inspector renders commit metadata with strict proof wording | Cleared as commit metadata | `clap_meta.status=ok`, `faiss_id=2602` | Keep current-run Qdrant proof separate from scene `clap_meta` |
| Scene-present entities | Present in manifest and temporal segment | Present in `/timeline/full` and `/scenes` as `tags`, `tag_details`, and `scene_present_entities` | Public operator Scene Inspector renders memory tags, tag provenance, and scene-present entities | Cleared | `Indoor`, `Music`, `Performance`, `Trumpet`, `December`; regression guard uses `trumpet` and `music` rows | Keep provenance labels distinct from canonical KG truth |
| Scene context LLM | Optional; present only when the feature produces `scene_context_llm` | Present in `/timeline/full` and `/scenes` when persisted, with context rollups in timeline metadata | Public operator Scene Inspector renders scene context summary when exposed | Cleared for projection | Regression guard uses `narrative_summary`, `scene_context_epistemic`, and `scene_context_arbitration` | Runtime remains optional; absence still means not present for that run |
| Recurrence/control | Existing witness/demo report available on public/demo API | `/api/runs/latest/preview` available on `30003` | Existing console surfaces recurrence/read-only status | Pending | Season 2 fresh witness preview returns 466 scenes | Audit after scene-level truth pass |

## Current Finding

## Visual/Keyframe Evidence Pass

Status: cleared for the first pass.

What changed:

- Harmonized temporal segments now carry `visual_caption`, `ocr_text`, and `ocr_date_candidates`.
- Scene and timeline API response models now expose the same fields.
- The public operator Scene Inspector renders visual caption, OCR text, and OCR date candidates in scene memory evidence, modality coverage, and schema projection.

Validation:

- Private: `39 passed` for `test_phase6_audio_artifact_path_unified.py`, `test_api_surface_truth.py`, and `test_runtime_run_preview.py`.
- Public: `45 passed` for the same API/runtime scope plus the operator console static guard.

## Audio Evidence Pass

Status: cleared for candidate scores and CLAP commit metadata.

What changed:

- Scene and timeline API response models now expose `audio_emotion_scores`.
- Harmonized temporal segments and persisted scene records now carry `clap_meta` from the durable audio artifact payload.
- Scene and timeline API response models now expose `clap_meta`.
- The public operator Scene Inspector renders `CLAP commit status` and explicitly labels it as commit metadata only, not current-run Qdrant proof.

Validation:

- Private: `39 passed` for `test_phase6_audio_artifact_path_unified.py`, `test_api_surface_truth.py`, and `test_runtime_run_preview.py`.
- Public: `45 passed` for the same API/runtime scope plus the operator console static guard.

Next candidate investigated: direct scene-present entity projection parity. This is resolved in the Entity Evidence Pass below.

## Entity Evidence Pass

Status: cleared for direct tag and scene-present entity projection.

What changed:

- Private scene and timeline API response models now expose `tags`, `tag_details`, and `scene_present_entities`.
- Private scene and timeline routes now project those durable temporal fields.
- Public already exposed and rendered those fields in the Scene Inspector, so no public UI change was needed for this pass.

Validation:

- Private RED guard failed on missing `SceneResponse.tags` and `TimelineSegment.tags`.
- Private GREEN guard passed for both scene and timeline projections.

Next candidate investigated: `scene_context_llm` direct projection. This is resolved in the Scene Context Evidence Pass below.

## Scene Context Evidence Pass

Status: cleared for optional scene context projection.

What changed:

- Scene and timeline API response models now expose `scene_context_llm`, `scene_context_epistemic`, and `scene_context_arbitration` when the harmonizer persists them.
- Timeline metadata now carries scene-context rollups such as `segments_with_scene_context_llm`, `top_scene_context_tags`, epistemic state counts, and arbitration rollups.
- The public operator Scene Inspector now renders a `Scene context summary` evidence row and includes context fields in schema projection.

Validation:

- Private RED guard failed on missing `SceneResponse.scene_context_llm` and missing timeline context metadata.
- Public RED guard failed on missing scene context API fields and missing `Scene context summary` UI copy.
- Private: `39 passed` for `test_phase6_audio_artifact_path_unified.py`, `test_api_surface_truth.py`, and `test_runtime_run_preview.py`.
- Public: `45 passed` for the same API/runtime scope plus the operator console static guard.

Remaining high-value trail: recurrence/control reports are already visible through the run preview/console path, but a separate read-only recurrence drilldown audit should verify recommendation draft, trend, and empty-state wording without mixing it into this scene evidence pass.
