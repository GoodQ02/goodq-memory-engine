<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-10 -->

# Season 1-2 Baseline Memo

## Scope
- Benchmark witness: `reports/fresh_ingest_runs/20260409_072106_two_season_benchmark_witness/`
- Branch: `main`
- Inputs: `01x01` through `02x12`
- Episodes processed: `17`
- Verification sources:
  - `output/scene_ingest_results.json`
  - `processing/01x*/temporal_index.json`
  - `processing/02x*/temporal_index.json`

## Operational Result
- Videos processed: `17`
- Total scenes: `651`
- Average scenes per episode: `38.29`
- Final witness status: `completed`
- Phase 6: completed across all benchmark episodes

Contained issues stayed inside the expected envelope:
- per-scene entity-empty warnings on weaker caption/object-only material
- contained `object_detect` retries through CPU fallback
- contained `image_embed_dino` retries through AMP-disabled fallback
- a small number of optional `audio_embed_clap` misses without pipeline halt

## Best Telling Metrics
- `381` dialogue-entity scenes
- `316` mentioned-people scenes
- `131` candidate-visible scenes
- `70` interaction-dominance scenes
- `10` conversation-owner scenes
- `651` audio-emotion scenes
- `167` time-hint scenes
- `14` music-event scenes

These are the strongest baseline signals because they show the system is now carrying:
- who is being talked about
- who is visibly present without overclaiming identity
- who is driving the exchange
- when scenes carry time cues
- how scenes feel emotionally
- whether music/laughter-style context is present

## Late Season 2 Readout
- `02x10 - The Baby Shower`: `28` dialogue-entity, `27` mentioned-people, `8` candidate-visible, `5` interaction-dominance, `3` conversation-owner
- `02x11 - The Chinese Restaurant`: `22`, `17`, `1`, `5`, `2`
- `02x12 - The Busboy`: `18`, `9`, `9`, `4`, `0`

This is a good summary slice because it shows the system staying sparse and believable rather than over-promoting ownership.

## Sample A: Conversation Ownership
- Episode: `01x02 - The Stakeout`
- `conversation_owner = Jerry`
- `interaction_dominance.speaker_id = SPEAKER_00`
- `dominant_share = 0.6869`
- `mention_dominance_ratio = 0.6`
- evidence: `3` speaker-aligned mentions across `2` involved segments
- supporting scene truth:
  - `visible_person_object_count = 4`
  - `visible_face_count = 1`
  - `speaker_voice_signature_count = 3`
  - `audio_emotion = surprise`

Why it matters:
- the system is not just indexing that Jerry was mentioned
- it is preserving who the exchange is about without collapsing that into visual identity

## Sample B: Another Ownership Case
- Episode: `02x10 - The Baby Shower`
- `conversation_owner = Barr`
- `interaction_dominance` is stable across `3` segments with `dominant_share = 0.6691`
- `mention_dominance_ratio = 1.0`
- `audio_emotion = angry`
- supporting scene truth:
  - `visible_person_object_count = 4`
  - `visible_face_count = 1`
  - `speaker_voice_signature_count = 1`

Why it matters:
- this is a clean example of “who the scene is about” emerging from interaction evidence instead of co-presence

## Sample C: Anonymous Visual Truth
- Episode: `02x12 - The Busboy`
- `candidate_visible_people = anonymous_person_1`
- evidence source: `object_detect + face_embed`
- `visible_person_object_count = 1`
- `visible_face_count = 1`
- `crowd_risk = low`
- `interaction_dominance` exists, but `conversation_owner = null`

Why it matters:
- the system can now state that a person is present without forcing a name
- visible truth, interaction behavior, and semantic ownership remain separated

## Interpretation
This is the baseline to compare against any Season 3 treatment run.

What is already proven here:
- long-running multi-episode ingestion is stable
- canonical Phase 6 perception surfaces hold at larger scale
- `candidate_visible_people` is useful but still anonymous-first
- `interaction_dominance` is real and name-free
- `conversation_owner` is sparse, emerging, and believable

What is not covered by this baseline:
- `audio.metadata_time_hints`
- the modernized `scene_summarizer`
- `scene_context_llm`

Those landed after this witness started, so they should be treated as Season 3 treatment features rather than baseline capabilities.

## Comparison Questions
When comparing a treatment run against this baseline, check:
- do `candidate_visible_people` and `interaction_dominance` remain stable?
- does the new feature add useful signal without changing scene counts or Phase 6 completion?
- does the new signal stay additive and provenance-safe?
- do any ownership or identity surfaces become noisier than this baseline?
