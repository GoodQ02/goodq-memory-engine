<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-20 -->

# GoodQ4All User Guide

This is the current user-facing guide for running GoodQ4All without having to
read the deeper architecture set first.

If you want the shortest project overview, start with `README.md`. If you want
the current testing or troubleshooting flow, use:

- `docs/TESTING_GUIDE.md`
- `docs/TROUBLESHOOTING.md`

## What GoodQ4All Does

GoodQ4All ingests local video, breaks it into scenes, and persists scene-level
memory across:

- transcripts
- scene summaries
- OCR and captions
- objects and faces
- text, image, and audio embeddings
- knowledge-graph events and relationships
- temporal continuity across scenes and episodes

On the current shipping line, the persisted scene truth now also includes:

- `speaker_count`
- `speaker_voice_signature_meta`
- `diarization_status`
- `emotion_status`
- `dominant_speaker_id`
- `continuity_key`

## What Is Proven Today

The current line is not just “intended to work.” It is already proven on:

- a full Season 4 long-haul witness
- a fresh Season 5 two-episode transition smoke
- a fresh Season 5 projection smoke that validates speaker continuity and
  aligned persisted outputs

That means the core system is already banked on real multi-episode material,
not only on synthetic or tiny smoke inputs.

## Quick Start

### 1. Verify local readiness

```powershell
conda run -n goodq_core python scripts/system_readiness_check.py
conda run -n goodq_core python scripts/cache_readiness_check.py
```

Both checks should exit cleanly before you start a serious run.

### 2. Use the canonical launcher

```powershell
.\LAUNCH_GOODQ.ps1
```

To begin ingestion explicitly:

```powershell
.\LAUNCH_GOODQ.ps1 -StartIngestion
```

For direct CLI-driven ingestion:

```powershell
conda run -n goodq_core python -m cli.run_ingestion --input-dir "<your_input_dir>" --verbose
```

## Where To Put Input

For a normal operator flow, use the configured import inbox under your active
data root.

If you are just running a narrow local smoke, a small dedicated folder is fine
as long as you pass it explicitly to the CLI.

## What To Inspect After A Run

Use these in order:

1. Run ledger

```text
reports/fresh_ingest_runs/<run_root>/experiment_log.json
```

2. Episode output

```text
reports/fresh_ingest_runs/<run_root>/<episode>_scene_context_llm/output/scene_ingest_results.json
```

3. Canonical persisted scene data

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<episode>/video/scene_manifest.json
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<episode>/temporal_index.json
```

## What Healthy Output Looks Like

For a healthy current witness, expect most or all of the following:

- `phase6_complete = true`
- `qdrant_ok = true`
- `generic_context_detected = false`
- `speaker_count > 0` on voiced scenes
- `diarization_status` and `emotion_status` on persisted outputs
- meaningful `narrative_summary`, `primary_tags`, or `dialogue_topics`

## What Is Especially Useful To Look At

If you are trying to understand what the system “knows,” start with:

- `narrative_summary`
- `dialogue_topics`
- `mentioned_people`
- `scene_present_entities`
- `dominant_speaker_id`
- `continuity_key`

Those are currently the highest-signal user-facing fields.

## What Is Still Maturing

A few surfaces are real but still conservative:

- `conversation_owner`
- `interaction_dominance`
- `candidate_visible_people`
- cross-episode identity promotion to stronger person evidence

These should be treated as additive context, not guaranteed primary truth.

## Monitoring And Status

Current supported status surfaces:

```powershell
conda run -n goodq_core python -m cli.system_status
conda run -n goodq_core python scripts/system_readiness_check.py
conda run -n goodq_core python scripts/utils/check_watchdog_status.py
```

## Querying And Retrieval

For the current CLI and operator surfaces, use:

- `docs/CLI-REFERENCE.md`
- `README.md`

The API path exists as an adjacent helper surface, but it is not the canonical
bootstrap/runtime entrypoint.

## If Something Looks Wrong

Start here:

- `docs/TROUBLESHOOTING.md`

Use the testing ladder here:

- `docs/TESTING_GUIDE.md`

And if the issue is specifically WSL audio or diarization:

- `docs/reference/WSL_AUDIO_RUNTIME.md`

## Related Docs

- `README.md`
- `docs/README.md`
- `docs/TESTING_GUIDE.md`
- `docs/TROUBLESHOOTING.md`
- `docs/reference/WSL_AUDIO_RUNTIME.md`
- `docs/SCENE_MANIFEST_SPECIFICATION.md`
- `docs/PHASE6_MULTIMODAL_FUSION.md`
