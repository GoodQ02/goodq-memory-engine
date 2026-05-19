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
| Audio emotion scores | Present as low-confidence candidate score distribution | Scores are not exposed by current scene/timeline response models | UI cannot show candidate distribution through API | Gap | Top candidate around 13 percent; no hard label promoted | Add low-confidence candidate score projection after visual pass |
| Hard audio emotion label | Strictly absent because score is below promotion threshold | `audio_emotion=null` | Should read as low-confidence candidates, not failure | Cleared semantics | `emotion_status=success`, `audio_emotion=null` | UI wording pass |
| CLAP audio commit | Present in `scene.audio.clap_meta` | Not present in `/timeline/full` or `/scenes` | Proof panel has separate runtime proof language, but scene detail lacks commit metadata | Gap | `clap_meta.status=ok`, `faiss_id=2602` | Add scene-level proof projection after visual/audio-score pass |
| Scene-present entities | Present in manifest and temporal segment | Partially visible in temporal rollups, not scene response | UI can show rollups but scene detail lacks direct list | Partial | `Indoor`, `Music`, `Performance`, `Trumpet`, `December` | Add direct scene entity projection after caption/OCR |
| Scene context LLM | Not present for this fresh probe | API correctly reports absence | UI should label optional/not configured or not present for this run | Pending | `segments_with_scene_context_llm=0` | Audit with a witness episode that has `scene_context_llm` |
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

Next concrete unresolved gap: audio emotion candidate score projection. The durable temporal segment can contain `audio_emotion_scores`, and the UI already has review-oriented language, but the stable scene/timeline response model must be audited before this can be marked cleared.
