<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-11 -->

# Season 3 Treatment Ladder Memo

## Scope
- Treatment epoch: `epoch_2025_12_23`
- Goal: validate post-baseline additive features one episode at a time
- Control: `docs/testing/SEASON1_2_BASELINE_MEMO_2026-04-10.md`
- Feature discipline:
  - one feature change per run
  - local override only through `configs/config.local.yaml`
  - stop on regression before proceeding

## Ladder Results

### `03x01 - The Note`
- Feature: `audio.metadata_time_hints`
- Result: valid auditable pass
- Run root: `reports/fresh_ingest_runs/20260410_071121_season3_feature_ladder/`
- Outcome:
  - `scene_count = 40`
  - `phase6_complete = true`
  - `qdrant_ok = true`
  - no metadata tag signal was present in the chunked scene-WAV corpus

Interpretation:
- wiring is proven
- no-signal outcome is expected on this corpus shape
- this is not a feature failure

### `03x02 - The Truth`
- Feature: modernized `scene_summarizer`
- Result: passed
- Run root: `reports/fresh_ingest_runs/20260410_164051_season3_feature_ladder/`
- Outcome:
  - `scene_count = 39`
  - `phase6_complete = true`
  - `qdrant_ok = true`
  - `summary_count = 39`
  - `scene_coverage = 39`
  - `visual_nested_proven = true`
  - `audio_nested_proven = true`
  - `unique_ratio = 1.0`

Interpretation:
- the canonical deterministic summarizer now reads the real nested `keyframe` and `audio` scene shape
- the summary surface stayed specific while modernizing safely

### `03x03 - The Pen`
- Feature: `scene_context_llm`
- Result: passed after iterative grounding hardening
- Authoritative run root: `reports/fresh_ingest_runs/20260411_171418_season3_feature_ladder/`
- Endpoint/model:
  - `http://localhost:38005/v1/models`
  - `Qwen/Qwen2.5-0.5B-Instruct`
- Outcome:
  - `scene_count = 39`
  - `phase6_complete = true`
  - `qdrant_ok = true`
  - `segments_with_scene_context_llm = 36`
  - `generic_context_detected = false`

Top tags from the authoritative pass:
- `pen` `10`
- `living room` `7`
- `rental car` `6`
- `kitchen` `6`
- `condo` `4`
- `group conversation` `4`
- `couch` `4`
- `florida` `3`
- `air conditioning` `3`
- `scuba diving` `3`

Interpretation:
- transcript-backed topics now dominate retrieval tags
- unsupported social-role wording and generic filler are suppressed
- the additive interpretation layer is now consistent with the system's evidence-first contract

## What This Proves

The treatment ladder validated three separate classes of post-baseline change without destabilizing the canonical pipeline:

- provenance-safe additive metadata truth
- deterministic canonical summarization against the current scene schema
- local-LLM-backed additive scene interpretation

Across all three treatment runs:
- scene counts stayed stable
- Phase 6 completed
- Qdrant writes remained healthy

## Next Safe Step

The next expansion should not stack new features. It should reuse the validated `scene_context_llm` treatment over multiple additional Season 3 episodes with the same local-override discipline and the same regression rails:

- `candidate_visible_people`
- `interaction_dominance`
- `conversation_owner`
- `phase6_complete`
- `qdrant_ok`
