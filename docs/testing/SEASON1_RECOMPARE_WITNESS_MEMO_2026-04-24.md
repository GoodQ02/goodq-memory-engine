<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-24 -->

# Season 1 Recompare Witness Memo

## Scope

- Witness roots:
  - `reports/fresh_ingest_runs/20260424_003250_season1_recompare_witness/`
  - `reports/fresh_ingest_runs/20260424_065027_season1_remaining_witness/`
- Supporting launcher history:
  - `reports/fresh_ingest_runs/20260424_080533_season1_followon_witness/`
- Branch: `main`
- Commit context:
  - visibility layer already shipped
  - legacy runtime-shell cleanup already shipped
- Inputs: `01x01` through `01x05`
- Feature under witness: `scene_context_llm`
- Comparison target:
  - `docs/testing/SEASON1_MAIN_BENCHMARK_MEMO_2026-04-08.md`
  - prior Season 1 processing under `epoch_2025_12_22`

This memo is a recompare witness, not a new baseline definition. The goal is to
prove that the current pushed runtime preserves the established Season 1 memory
surfaces while adding the newer read-only observability lanes.

## Canonical Artifacts Reviewed

- `reports/fresh_ingest_runs/20260424_003250_season1_recompare_witness/experiment_log.json`
- `reports/fresh_ingest_runs/20260424_065027_season1_remaining_witness/experiment_log.json`
- `reports/fresh_ingest_runs/20260424_080533_season1_followon_witness/experiment_log.json`
- `processing/01x0*/temporal_index.json`
- `processing/01x0*/video/scene_manifest.json`

## Operational Result

The full five-episode Season 1 recompare passed.

- Episodes processed: `5 / 5`
- Final witness state: `completed`
- Total scenes: `185`
- Phase 6 complete: `5 / 5`
- Qdrant OK: `5 / 5`
- Generic-context regressions detected: `0 / 5`
- `scene_context_llm` coverage:
  - `01x01`: `32 / 33`
  - `01x02`: `38 / 39`
  - `01x03`: `36 / 36`
  - `01x04`: `36 / 38`
  - `01x05`: `37 / 39`

Contained issues remained inside the expected witness envelope:

- `01x01`: optional `audio_embed_clap` failure without pipeline halt
- `01x03`: contained `image_caption` native crash recovered through
  `gpu_amp_disabled`
- `01x04`: contained `image_embed_dino` and `image_caption` native crashes
  recovered through retry; optional `audio_embed_clap` failure
- `01x05`: optional `audio_embed_clap` failure without pipeline halt

## Operational Note On Launcher History

One follow-on root should be treated as operational history rather than as the
authoritative Season 1 witness result:

- `reports/fresh_ingest_runs/20260424_080533_season1_followon_witness/`

That root shows:

- `01x03` passed cleanly
- `01x04` failed because canonical `temporal_index.json` or
  `scene_manifest.json` was missing in that particular launcher path

The important point is that the successful authoritative artifacts already
exist for both episodes under the canonical passed roots used by this memo:

- `01x03` is proven by the successful `temporal_index.json` under
  `epoch_2026_04_24_season1_followon_witness`
- `01x04` is proven by the successful `temporal_index.json` under
  `epoch_2026_04_24_season1_remaining_witness`

So the failed follow-on root is a launcher-history seam, not a runtime-truth
regression.

## Comparison To The Published Season 1 Benchmark

Compared with the published benchmark in
`docs/testing/SEASON1_MAIN_BENCHMARK_MEMO_2026-04-08.md`, the core Season 1
memory model is unchanged.

Stable season totals:

- `scene_count`: `185 -> 185`
- `segments_with_scene_present_entities`: `72 -> 72`
- `segments_with_dialogue_mentioned_entities`: `118 -> 118`
- `segments_with_mentioned_people`: `100 -> 100`
- `segments_with_candidate_visible_people`: `47 -> 47`
- `segments_with_interaction_dominance`: `23 -> 23`
- `segments_with_conversation_owner`: `3 -> 3`
- `segments_with_audio_emotion`: `185 -> 185`
- `segments_with_time_hints`: `51 -> 51`
- `segments_with_music_events`: `6 -> 6`
- `segments_with_speaker_voice_signatures`: `175 -> 175`

New additive visibility totals now present in the current witness:

- `segments_with_speaker_aligned_mentions`: `70`
- `segments_with_transcript_entity_disagreements`: `27`

This is the right outcome. The witness shows that the new branch state did not
shift identity, interaction, or perception behavior. It only made two already
existing internal surfaces more visible.

## Season Totals

- `segments_with_scene_present_entities`: `72`
- `segments_with_dialogue_mentioned_entities`: `118`
- `segments_with_mentioned_people`: `100`
- `segments_with_candidate_visible_people`: `47`
- `segments_with_interaction_dominance`: `23`
- `segments_with_conversation_owner`: `3`
- `segments_with_speaker_aligned_mentions`: `70`
- `segments_with_transcript_entity_disagreements`: `27`
- `segments_with_audio_emotion`: `185`
- `segments_with_time_hints`: `51`
- `segments_with_music_events`: `6`
- `segments_with_speaker_voice_signatures`: `175`

Per-episode highlights:

- `01x01`
  - `speaker_aligned_mentions = 8`
  - `transcript_entity_disagreements = 1`
  - disagreement category:
    - `title_bearing_transcript_name_not_resolved`
- `01x02`
  - `candidate_visible_people = 13`
  - `interaction_dominance = 5`
  - `conversation_owner = 3`
  - `speaker_aligned_mentions = 23`
  - `transcript_entity_disagreements = 12`
- `01x03`
  - `scene_present_entities = 19`
  - `candidate_visible_people = 9`
  - `interaction_dominance = 0`
  - contained retry recovery stayed non-fatal
- `01x04`
  - `interaction_dominance = 8`
  - `speaker_aligned_mentions = 13`
  - `transcript_entity_disagreements = 6`
- `01x05`
  - `candidate_visible_people = 12`
  - `speaker_aligned_mentions = 16`
  - `conversation_owner = 0`

## Sample A: Stable Conversation Ownership

- Episode: `01x02 - The Stakeout`
- Scene window:
  - `1120.04s` to `1154.24s`
  - `1154.24s` to `1189.96s`
- `conversation_owner = Jerry`
- `interaction_dominance.speaker_id = SPEAKER_00`
- `dominant_share = 0.6869`
- `chain_length = 3`
- `mention_dominance_ratio = 0.6`
- supporting `speaker_aligned_mentions`:
  - `Jerry`
  - `Lane`

Why it matters:

- the current runtime still preserves the same conservative ownership story as
  the benchmark
- `conversation_owner` stays sparse and interaction-backed
- the visibility additions did not inflate owner claims or change the chain
  thresholds

## Sample B: Transcript / Entity Visibility Without Promotion

- Episode: `01x02 - The Stakeout`
- disagreement family:
  - `transcript_full_name_reduced_to_partial_entity`
- example transcript candidate:
  - `Elaine Bennis`
- local entity truth:
  - `Elaine`
  - `Jerry`
  - `Mac`
- local `speaker_aligned_mentions`:
  - `Mac`
  - `Elaine`

Why it matters:

- the system is not silently losing all person truth
- it is exposing a normalization seam that already existed upstream
- the new surface shows where transcript richness exceeds the projected local
  entity form without turning that disagreement into automatic identity
  promotion

## Sample C: Title-Bearing Transcript Name Still Outside Canonical Person Truth

- Episode: `01x01 - Good News, Bad News`
- disagreement family:
  - `title_bearing_transcript_name_not_resolved`
- transcript candidate:
  - `Mr. Signal`
- local entity names:
  - `George`
- `speaker_aligned_mentions = []`

Why it matters:

- the system now tells the operator that a title-bearing transcript name exists
  outside canonical person truth
- that is precisely the kind of upstream extractor / normalization seam we want
  to audit before touching promotion rules

## Interpretation

This witness proves two things at once.

1. The current runtime preserves the published Season 1 benchmark behavior.
2. The new read-only visibility lanes are genuinely additive.

The strongest takeaway is not that Season 1 became "better" in the sense of
more aggressive inference. The stronger takeaway is that we can now see more of
the already-existing truth boundaries:

- where speaker-aligned person evidence exists
- where transcript person-like surfaces outrun canonical entity projection
- where interaction ownership remains intentionally sparse

This is the desired shape:

- stable memory behavior
- richer observability
- no hidden semantic drift

## Recommended Next Step

Use this Season 1 recompare witness as the comparison anchor for the next fresh
pressure pass on Season 2.

What to check next:

1. whether Season 2 preserves the same stable core totals and conservative
   ownership behavior
2. whether transcript/entity disagreement families scale similarly or expose new
   upstream seams
3. whether the current visibility layer remains readable over a larger batch

Do not treat this memo as extractor authorization. It is an observability proof,
not a license to loosen identity or promotion behavior.
