# Pipeline Surface Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Confirm each high-value pipeline signal is generated, persisted, projected through the API/read model, and surfaced in the operator console without hidden assets or misleading labels.

**Architecture:** Treat persisted artifacts as truth first, then compare API projection and UI rendering against that truth. Fix only one proven projection gap at a time, with a focused regression test before implementation.

**Tech Stack:** Python, pytest, FastAPI read models, static operator console HTML/CSS/JS, local GoodQ runtime artifacts, Qdrant/SQLite proof surfaces where already exposed.

---

## Scope

Audit in this order:

1. Visual/keyframe evidence: caption, OCR text, date candidates, objects, frame paths, CLIP/DINO commit IDs.
2. Audio evidence: transcript, speakers, diarization status, speaker voice signatures, CLAP commit metadata, current-run proof status.
3. Emotional evidence: sentiment, audio-emotion candidate scores, strict promoted audio-emotion labels.
4. Temporal evidence: explicit dates, months, relative phrases, metadata time hints, scene timing.
5. Entity and graph evidence: scene-present entities, dialogue-mentioned entities, visible people, candidate visible people, KG/entity counts.
6. Scene-context evidence: `scene_context_llm`, epistemic state, arbitration, conflicts, fallback/optional states.
7. Retrieval evidence: search hit explanation, matched modalities, missing signals, result provenance.
8. Recurrence/control evidence: read-only trend, recommendations, no-mutation boundary.

## Evidence Sources

- Runtime config: `conda run --no-capture-output -n goodq_core python -m cli.print_config`
- Step ledger: `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/logs/step_runs.jsonl`
- Scene manifest: `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video_id>/video/scene_manifest.json`
- Temporal index: `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video_id>/temporal_index.json`
- Run output: configured scratch/output `scene_ingest_results.json`
- API read model: `/api/system/videos`, `/api/videos/{video_id}/timeline/full`, `/api/videos/{video_id}/scenes`
- Operator console: `/ui/operator_console_v1/?api_base=<local-api-base>`

## Task 1: Build Surface Audit Matrix

**Files:**
- Create: `reports/ui_surface_audits/2026-05-19-pipeline-surface-audit.md`
- No code changes.

- [x] **Step 1: Create the audit report skeleton**

Add a markdown table with these columns:

```markdown
| Feature | Artifact Truth | API Projection | UI Surface | Status | Evidence | Next Action |
|---|---|---|---|---|---|---|
```

- [x] **Step 2: Populate the fresh-scene baseline**

Use the latest single-scene probe and record its `video_id`, run id, scene count, Phase 6 status, and API base. Redact local drive roots and real private paths.

- [x] **Step 3: Validate no assumptions**

Run:

```powershell
conda run --no-capture-output -n goodq_core python -m pytest tests/unit/test_phase6_audio_artifact_path_unified.py -q
```

Expected: all tests pass before beginning feature-by-feature audit.

## Task 2: Audit Visual/Keyframe Evidence

**Files:**
- Modify only if gap proven:
  - `api/utils/response_models.py`
  - `api/routes/scenes.py`
  - `api/routes/timeline.py`
  - `ui/operator_console_v1/static/js/app.js`
  - matching tests under `tests/unit/`

- [x] **Step 1: Extract artifact truth**

Read first scene from `scene_manifest.json` and record:

```text
keyframe.caption
keyframe.ocr_text
keyframe.date_candidates or OCR-derived date text
detected_objects / objects
representative_frame
clip_id
dino_id
phase6_vector_commit
```

- [x] **Step 2: Compare API projection**

Call:

```powershell
Invoke-RestMethod -Uri "<api_base>/api/videos/<video_id>/timeline/full"
Invoke-RestMethod -Uri "<api_base>/api/videos/<video_id>/scenes"
```

Expected: scene responses expose enough visual evidence for UI inspection, or the missing fields are marked as missing in the audit report.

- [x] **Step 3: Compare operator console**

Open the operator console against the same API base and check whether the UI shows caption/OCR/date/object/vector proof in an understandable section.

- [x] **Step 4: Patch only one proven gap**

If API fields are missing, write a failing API unit test first. If API fields exist but UI hides them, write or update the narrow UI renderer/test before changing display code.

## Task 3: Audit Audio and Emotional Evidence

**Files:**
- Modify only if gap proven:
  - `steps/video/cross_modal_harmonizer.py`
  - `api/utils/response_models.py`
  - `api/routes/scenes.py`
  - `api/routes/timeline.py`
  - `api/routes/runtime.py`
  - `ui/operator_console_v1/static/js/app.js`
  - matching tests under `tests/unit/`

- [ ] **Step 1: Confirm artifact truth**

Record transcript, diarization, speakers, speaker voice signature metadata, sentiment, audio-emotion scores, CLAP metadata, and current-run proof status.

- [ ] **Step 2: Preserve strict labels**

Promote a hard `audio_emotion` label only when the pipeline already considers it proven. Otherwise surface candidate scores as low-confidence evidence.

- [ ] **Step 3: Validate API projection**

Expected: `/timeline/full` and `/scenes` expose sentiment, speaker, diarization, CLAP-related proof where the stable API contract supports it.

## Task 4: Audit Temporal, Entity, and Scene Context Evidence

**Files:**
- Modify only if gap proven:
  - `steps/video/cross_modal_harmonizer.py`
  - `api/routes/timeline.py`
  - `api/routes/scenes.py`
  - `ui/operator_console_v1/static/js/app.js`
  - matching tests under `tests/unit/`

- [ ] **Step 1: Compare temporal index rollups to segment fields**

Confirm top-level counts agree with per-segment truth for time hints, audio emotion, scene context, entities, and visibility channels.

- [ ] **Step 2: Check scene-context availability**

Record whether `scene_context_llm`, `scene_context_epistemic`, and arbitration are absent because the feature is disabled, unsupported for this run, or truly missing.

- [ ] **Step 3: Fix wording before functionality when truth exists**

If the backend exposes truthful partial states but the UI calls them failures, patch the UI state grammar rather than changing pipeline semantics.

## Task 5: Commit and Mirror

**Files:**
- Same scoped files changed by the task.

- [ ] **Step 1: Validate private repo**

Run the focused pytest command for the changed feature and any API/UI unit tests affected.

- [ ] **Step 2: Mirror public repo when runtime code or public UI changes**

Apply the same scoped diff to `goodq4all_public` only when public-facing code should match.

- [ ] **Step 3: Commit both repos**

Use a narrow commit message, then verify:

```powershell
git status --short --branch
```

Expected: clean except the branch may be ahead of origin when push is intentionally deferred.
