<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-08 -->

# Season 1 Main Benchmark Memo

## Scope
- Benchmark witness: `reports/fresh_ingest_runs/20260408_070502_season1_main_benchmark_witness/`
- Branch: `main`
- Commit: `31fd533`
- Inputs: `01x01` through `01x05`
- Verification sources:
  - `output/scene_ingest_results.json`
  - `processing/01x0*/temporal_index.json`
  - `processing/01x0*/video/scene_manifest.json`

## Operational Result
- Videos processed: `5`
- Phase 6 complete: `5/5`
- Qdrant OK: `5/5`
- FAISS OK: `5/5`
- Scene counts:
  - `01x01`: `33`
  - `01x02`: `39`
  - `01x03`: `36`
  - `01x04`: `38`
  - `01x05`: `39`

Contained issues remained within the expected envelope:
- isolated `object_detect` native crashes recovered via CPU fallback
- isolated `image_embed_dino` native crashes recovered via AMP-disabled retry
- occasional non-fatal entity-empty scenes on weak caption/object-only material
- optional `audio_embed_clap` failures without pipeline halt

## What This Benchmark Unlocked
Compared with the prior ingestion state, the main change is not throughput. The change is that perception context is now surfaced as first-class temporal memory instead of remaining stranded inside raw scene payloads.

The benchmark now exposes, season-wide:
- who is physically grounded in a scene
- who is being mentioned in dialogue
- whether anonymous visible human presence exists
- what the scene sounds like emotionally
- whether music or laughter is part of the moment
- whether time is being referenced
- whether speaker voice signatures are present
- whether a conversation appears to revolve around a person without claiming visual presence

## Season Totals
- `segments_with_scene_present_entities`: `72`
- `segments_with_dialogue_mentioned_entities`: `118`
- `segments_with_mentioned_people`: `100`
- `segments_with_candidate_visible_people`: `5`
- `segments_with_conversation_owner`: `2`
- `segments_with_music_events`: `7`
- `segments_with_time_hints`: `51`
- `segments_with_audio_emotion`: `185`
- `segments_with_speaker_voice_signatures`: `175`

Episode-level highlights:
- `01x01`
  - `time_hints`: `15`
  - `audio_emotion`: `33`
  - `speaker_voice_signatures`: `32`
- `01x02`
  - `music_events`: `5`
  - `time_hints`: `9`
  - `audio_emotion`: `39`
  - `speaker_voice_signatures`: `38`
- `01x03`
  - `candidate_visible_people`: `1`
  - `music_events`: `2`
- `01x04`
  - `candidate_visible_people`: `2`
- `01x05`
  - `candidate_visible_people`: `2`
  - `conversation_owner`: `2`

## Sample A: Dialogue-Heavy Interaction
- Source: `processing/01x05 - The Stock Tip/temporal_index.json`
- Segment window: `811.92s` to `842.24s`

Observed memory surfaces:
- `scene_present_entities`: `Kitchen`
- `dialogue_mentioned_entities`: `Elaine`, `George`
- `visible_person_object_count = 1`
- `visible_face_count = 1`
- `speaker_voice_signature_count = 3`
- `audio_emotion = "disgust"`
- `continuity_key = "conversation:SPEAKER_00|SPEAKER_01"`
- `dominant_speaker_id = "SPEAKER_00"`
- `candidate_visible_people`: `George`
- `conversation_owner`: `George`

Why this matters:
- the system is not only storing mentions
- it is preserving a scene-grounded interaction chain
- it can now say that the exchange is about George without collapsing that into a generic transcript fact

This reads like a memory of an interaction, not just an index of tokens.

## Sample B: Quieter / More Visual Scene
- Source: `processing/01x01 - Good News, Bad News/temporal_index.json`
- Segment window: `858.92s` to `902.88s`

Observed memory surfaces:
- `scene_present_entities`: `Street`
- `dialogue_mentioned_entities`: none
- `visible_person_object_count = 4`
- `visible_anonymous_people_count = 4`
- `speaker_voice_signature_count = 1`
- `audio_emotion = "disgust"`
- `candidate_visible_people`: none
- `conversation_owner`: none

Why this matters:
- the system preserves environmental truth without inventing identity
- it recognizes populated visible human presence
- it still carries emotional and speaker context
- it does not force a named person into the scene when the evidence is not there

This is the desired restraint: richer perception without overclaiming.

## Interpretation
The benchmark establishes a stronger memory model than the previous ingestion state.

Before, the system primarily exposed:
- entities
- objects
- likely scene locations

Now it also exposes:
- emotional tone
- time-oriented cues
- music and laughter events
- speaker-signature presence
- early interaction ownership

The practical result is a move from plain indexing toward situational awareness.

## Cautions
- `candidate_visible_people` remains intentionally sparse and should stay that way
- `conversation_owner` is emerging but not yet dense
- sparse interaction ownership is currently a feature, not a defect
- the benchmark should be treated as the canonical comparison point for any laptop-side summary

## Recommended Comparison Questions
When comparing another system against this benchmark, check:
- are the season totals for `audio_emotion`, `time_hints`, `music_events`, and `speaker_voice_signatures` materially similar?
- do the same scenes produce comparable interaction and environmental memory?
- does the other system preserve the same restraint around visible presence?
- do `candidate_visible_people` and `conversation_owner` stay sparse and believable?
