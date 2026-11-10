<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_AGENT_WORKFLOW -->
<!-- DOC_LAST_VERIFIED: 2026-11-06 -->
<!-- INSTRUCTION_REVIEW: documentation only; no runtime qualification -->

# Pipeline Troubleshooting Flow: Verifiable Source-Driven Optimization

Use this workflow to diagnose pipeline failures, tune confidence thresholds, or
improve output quality through fresh runs against observed source content. The
[roadmap](../../releases/ROADMAP.md#fresh-current-pipeline-acceptance-2026-10-08)
owns current coverage and acceptance. The current task and `PROJECT.md` define
authorized execution; do not infer a pending reset from historical instructions.

## Purpose

Use [evidence-first repair](EVIDENCE_FIRST_RUNTIME_REPAIR.md) for the common
diagnosis, reporting and stop rules. The guidance here adds ingestion-specific
ground-truth and source-to-consumer checks, not another generic repair loop.

Identify a failing production boundary, repair it, and prove useful current-run
output. Retained artifacts establish their historical output and current
compatibility only; they cannot establish current ingestion behavior. Small
scene probes isolate defects; selected full-source runs are required when
testing segmentation coverage, cross-scene behavior, duration or recovery.

---

## The Troubleshooting Loop

### 1. Identify Ground Truth Alignment
Inspect the approved sample itself and record the expected observable content,
source hash and offsets. Use a human-reviewed transcript/frame/scene annotation
where needed. External cast lists or transcripts can corroborate entertainment
samples, but do not establish who speaks or appears at a particular timestamp.
Do not infer personal identity ground truth from a model's own output.

Cover applicable positives and negatives across complementary samples: speech
and silence, faces and no faces, visible text and no text, music/events, objects,
multiple speakers and scene boundaries. An empty result for an applicable
positive is not success; a justified negative is not a failure. Record which
retained capabilities are enabled, disabled, unavailable or untested.

### 2. Isolate Target Scenes
Start with an exact input and the smallest useful scene range through the
existing production `cli.run_ingestion` options (`--input-file`, `--config`,
`--scene-indices` or `--scene-start-index/--scene-end-index`). Do not inject mock selectors
into production code for acceptance. Use mocks only for focused regressions.
The input-directory option is not recursive; enumerate intended sample files.

Use [Clean Memory Start](CLEAN_MEMORY_START.md) to prove a fresh test root,
epoch, exact collections and writable-path containment before execution.
Preserve sample originals and prior failure receipts. A profile name or a
collection prefix is not isolation proof. Expand to an authorized selected
full movie after useful scene-level proof, or when the failing boundary itself
requires whole-source behavior. Data resets require explicit current approval.

### 3. Apply Single-Variable Tuning
Keep one coherent defect/repair boundary at a time and record changed variables
so the result can be attributed. Model output need not be perfectly deterministic;
declare expected evidence/quality tolerances before judging the result. Preserve
original-failure and repaired-caller evidence rather than tuning until green.
- Examples of single variables:
  - Subprocess file-system check timeout threshold.
  - VRAM allocator safety boundary (`emergency_stop_gb`).
  - Audio overlap/diarization confidence threshold.
  - Visual description similarity index parameters.

### 4. Execute and Inspect Target Output
Run the selected production caller and bind all observations to its source
revision/configuration, input, run and epoch. Reconcile the executed steps with
the full roadmap inventory, not only release capability rows. Inspect actual
payloads/status/provenance in scene manifests, temporal output, UCF, commit
receipts and configured vector stores; demonstrate each output's consumer.

Non-promoting isolated ingestion intentionally suppresses active SQLite/KG
materialization. Inspect those stores after a separate deliberate test-scope
validation/promotion and verify retrieval/UI after reload. Do not call missing
isolated writes a defect or count their intentional absence as integrated proof.
Resolve receipt/status contradictions before accepting a broad run.

### 5. Validate for Regression & Drift
After implementing a fix or change:
- Re-run the isolated scenes to confirm the correction.
- Ensure the fix doesn't introduce side effects on adjacent pipeline steps (e.g., visual features generating successfully but audio falling back).
- Exercise the selected supported backend/profile and relevant fallbacks; do
  not claim another backend passed from a mocked dispatch or one successful lane.
- After authorized sample removal/rejection/supersession, verify exact affected
  evidence, related-store/search consistency, unchanged neighbors, retry/reload
  and recovery semantics. A deleted file is not proof of a product lifecycle action.

### 6. Record the result
Use the repair workflow's task receipt and checkpoint rules. The existing
`.agents/index/corrections.json` is historical correction evidence, not a second
mandatory completion log or backlog. Add a reusable lesson only when it changes
a future decision; do not copy the full receipt into multiple locations.

## Pass Criteria

A pipeline optimization or fix is ready to commit when:
1. **Caller verification:** original failure and repaired production boundary
   are demonstrated; the fresh applicable stage produces meaningful persisted
   output and its downstream consumer uses it.
2. **Truthful outcomes:** required failures/missing outputs are closed; every
   warning, fallback, negative and exclusion is explained. Never suppress a
   diagnostic or fabricate detections to obtain an all-green report.
3. **Preservation and quality:** relevant existing checks and fresh integration
   pass for the claimed scope; unrelated data and supported behavior are preserved.
4. **Current evidence:** the owning checkpoint and receipt record actual
   results, remaining gaps and exact replay evidence. A
   declaration of completion or historical populated corpus is insufficient.
