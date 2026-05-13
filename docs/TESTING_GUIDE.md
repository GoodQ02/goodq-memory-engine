<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-20 -->

# Current Testing Guide

This guide is the active testing and verification entry point for GoodQ4All.

Use it to choose the right level of proof without mixing historical setup notes
with the current runtime contract.

## Testing Tiers

### 1. Fast machine readiness

Use this first when validating a machine or a fresh pull.

```powershell
conda run -n goodq_core python scripts/system_readiness_check.py
conda run -n goodq_core python scripts/cache_readiness_check.py
```

What this proves:

- host runtime imports and config load
- local cache presence
- service-level readiness surfaces

### 2. Targeted contract checks

Use these after a surgical fix or when validating one seam.

```powershell
conda run -n goodq_core python -m pytest tests/unit/test_wsl_audio_preflight.py
conda run -n goodq_core python -m pytest tests/unit/test_phase6_audio_artifact_path_unified.py
conda run -n goodq_core python scripts/test_wsl2_bridge_integrity.py
```

What this proves:

- WSL readiness means real offline diarization loadability
- Phase 6 persists the expected audio truth fields
- the WSL bridge preserves diarization and emotion status on the success path

### 3. Short witness smokes

Use a one- or two-episode witness when you need end-to-end proof on fresh
material without committing to a season-scale run.

Best current examples:

- Season 5 transition smoke:
  `reports/fresh_ingest_runs/20260419_144732_season5_transition_smoke/`
- Season 5 projection smoke:
  `reports/fresh_ingest_runs/20260419_191136_season5_projection_smoke/`

What this proves:

- orchestration health across episode boundaries
- Phase 6 completion on new material
- persisted speaker continuity and audio truth surfaces

### 4. Long-haul witnesses

Use these when validating stability, throughput, and sustained partial-failure
resilience.

Best current example:

- Season 4 release witness:
  `reports/fresh_ingest_runs/20260418_060329_season4_release_witness/`

What this proves:

- sustained ingestion under real load
- non-fatal optional-step failures staying contained
- durable scene-context quality over a full season

## Current Proven State

These claims are now banked, not speculative:

- Season 4 long-haul witness passed all staged entries with clean Phase 6 and
  Qdrant persistence.
- Season 5 transition smoke proved episode-to-episode continuity on fresh
  material.
- Season 5 projection smoke proved that `scene_ingest_results.json`,
  `scene_manifest.json`, and `temporal_index.json` now align on:
  - `speaker_count`
  - `speaker_voice_signature_meta`
  - `diarization_status`
  - `emotion_status`
  - `dominant_speaker_id`

The current smoke totals across `05x01` and `05x02` are:

- `83 / 84` scenes with `speaker_count > 0`
- `80 / 84` scenes with `speaker_voice_signature_count > 0`
- `84 / 84` scenes with `diarization_status`
- `84 / 84` scenes with `emotion_status`

## What To Inspect After A Run

For any serious witness, inspect these in order:

1. Run ledger

```text
reports/fresh_ingest_runs/<run_root>/experiment_log.json
```

2. Episode summary surface

```text
reports/fresh_ingest_runs/<run_root>/<episode>_scene_context_llm/output/scene_ingest_results.json
```

3. Canonical persisted scene bundle

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<episode>/video/scene_manifest.json
```

4. Canonical temporal rollup

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<episode>/temporal_index.json
```

5. Knowledge graph state when continuity or identity is part of the question

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/knowledge_graph.db
```

## What Counts As A Pass

For a healthy modern witness, expect most or all of the following:

- `phase6_complete = true`
- `qdrant_ok = true`
- `generic_context_detected = false`
- `speaker_count > 0` on voiced scenes
- `diarization_status` present on persisted scene outputs
- `emotion_status` present on persisted scene outputs
- `speaker_voice_signature_meta` present even when emission is skipped

Important nuance:

- a scene can still be healthy if `speaker_voice_signature_meta.status` is
  `skipped` for a truthful reason such as `insufficient_diverse_speech`
- optional vision-step native faults may still occur occasionally without
  invalidating the whole witness if the run finishes cleanly and the failing
  step is surfaced truthfully

## What Is Still Maturing

These are active quality/maturity lanes, not system-blocking failures:

- `conversation_owner` is still sparse on current short smokes
- `interaction_dominance` is real but not yet dense enough to treat as a
  required output lane
- `speaker_aligned_mentions` is now visible in scene/timeline read surfaces,
  but it remains an additive evidence lane rather than identity truth
- transcript/entity disagreement reporting is now available as a read-only
  audit surface and should be used to study extractor/normalization seams
  before widening inference rules
- transcript-fragment cleanup still has some quality tails in older Season 4
  outputs
- identity stitching is active, but `identity_evidence` remains conservative on
  short smokes

## Recommended Verification Order

When making or reviewing a change:

1. run fast machine readiness
2. run targeted contract tests
3. run a short smoke on fresh material
4. inspect persisted artifacts
5. only then widen to a long-haul witness

## Related Docs

- `README.md`
- `docs/README.md`
- `docs/SCENE_MANIFEST_SPECIFICATION.md`
- `docs/PHASE6_MULTIMODAL_FUSION.md`
- `docs/reference/WSL_AUDIO_RUNTIME.md`
- `docs/releases/RELEASE_0.1.1.md`
- `reports/README.md`
