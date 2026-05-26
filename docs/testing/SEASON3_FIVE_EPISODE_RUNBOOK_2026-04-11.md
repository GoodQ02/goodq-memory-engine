<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-11 -->

# Season 3 Five-Episode Runbook

## Purpose

Run the next five Season 3 treatment episodes using the now-validated `scene_context_llm` logic without changing the locked Season 1-2 control.

This runbook assumes:
- `epoch_2025_12_22` remains locked as the control universe
- `epoch_2025_12_23` remains the treatment universe
- local `vLLM` is available on `http://localhost:38005/v1`
- the validated model remains `Qwen/Qwen2.5-0.5B-Instruct`

## Episodes

The first five-treatment campaign should use:
- `03x03`
- `03x04`
- `03x05`
- `03x06`
- `03x07`

These map to:
- `03x03 - The Pen`
- `03x04 - The Dog`
- `03x05 - The Library`
- `03x06 - The Parking Garage`
- `03x07 - The Cafe`

## Contract

Do not change canonical baseline config.

Use local override only:
- `configs/config.local.yaml`

Do not stack new features.

Run only the already validated additive feature:
- `scene_context_llm`

## Command

From the repo root:

```powershell
conda run -n goodq_core python scripts/season3_feature_ladder.py `
  --epoch epoch_2025_12_23 `
  --single-feature scene_context_llm `
  --episode-prefixes 03x03,03x04,03x05,03x06,03x07
```

If resuming after an interruption:

```powershell
conda run -n goodq_core python scripts/season3_feature_ladder.py `
  --epoch epoch_2025_12_23 `
  --single-feature scene_context_llm `
  --episode-prefixes 03x03,03x04,03x05,03x06,03x07 `
  --start-at-prefix 03x05
```

## Expected Outputs

Each run root will be created under:
- `reports/fresh_ingest_runs/<timestamp>_season3_feature_ladder/`

Authoritative control file:
- `experiment_log.json`

Per-episode canonical outputs:
- `processing/<episode>/temporal_index.json`
- `processing/<episode>/video/scene_manifest.json`

Per-episode run summary:
- `output/scene_ingest_results.json`

## Pass Criteria

For each episode:
- `scene_count > 0`
- `phase6_complete = true`
- `qdrant_ok = true`
- `segments_with_scene_context_llm > 0`
- `generic_context_detected = false`

## Regression Rails

The feature should remain additive. Watch these rails every episode:

- `candidate_visible_people` stays anonymous-first
- `interaction_dominance` stays name-free
- `conversation_owner` stays sparse and evidence-backed
- no change in scene count relative to the episode ingest itself

## Stop Conditions

Stop immediately if any episode shows:
- `phase6_complete = false`
- `qdrant_ok = false`
- `generic_context_detected = true`
- any new identity leakage or unsupported social-role wording

If that happens:
- do not proceed to the next episode
- audit the failing episode directly against `scene_manifest.json`, transcript evidence, and `experiment_log.json`

## Ready State

This campaign is considered ready to launch when:
- `/v1/models` responds locally
- the model id returned includes `Qwen/Qwen2.5-0.5B-Instruct`
- `scripts/season3_feature_ladder.py` supports `--single-feature` and `--episode-prefixes`
- `docs/testing/SEASON3_TREATMENT_LADDER_MEMO_2026-04-11.md` remains the current treatment authority
