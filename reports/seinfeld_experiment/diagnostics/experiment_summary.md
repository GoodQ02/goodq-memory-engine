# Seinfeld Experiment Summary

## Pipeline Metrics

| Metric | Value |
| --- | --- |
| Episodes processed | 5 |
| Scenes processed | 185 |
| Transcript-bearing scenes | 182 |
| Transcript coverage | 98.4% |
| Qdrant clip vectors | 185 |
| Qdrant dino vectors | 185 |
| Qdrant text vectors | 182 |
| Qdrant audio vectors | 184 |
| KG nodes | 310 |
| KG edges | 315 |
| Primary run step failures | 0 |

## Formal Witness Run (2026-03-09)

The current release baseline is the formal Season 1 witness run recorded in `SEASON1_WITNESS_RUN_2026-03-09.md`.

Witness baseline highlights:

- full clean-state rebuild of the five-episode control set
- `185` scenes processed with `182/185` transcript coverage
- `0` processing-error scenes
- WSL audio effective on `185/185` scenes
- Qdrant counts: `clip=185`, `dino=185`, `text=182`, `audio=184`
- KG counts: `310` nodes and `315` edges
- only `3` non-`ok` step rows, all optional-step failures

This run supersedes the earlier episode-only control reruns as the formal witness record for release tagging.

Supporting release artifacts:

- post-witness comparison pack: `POST_WITNESS_ANALYTICS_COMPARISON_2026-03-09.md`
- permanent release bundle: `../releases/season1_witness_run_2026-03-09/`

## Milestone: Clean Reset Control Rerun (2026-03-08)

The Episode 1 control rerun from `reruns/20260308_episode1_clean_reset_rerun_v2/` was executed after wiping the active epoch runtime state:

- `memory.db`
- `knowledge_graph.db`
- `processing/`
- `logs/`
- `faiss/`
- the four epoch Qdrant collections

This rerun is the current apples-to-apples control checkpoint because it rebuilt the episode from a genuinely empty epoch and reproduced the expected semantic profile without relying on accumulated vector state.

### Clean Reset Results

| Metric | Value |
| --- | --- |
| Scenes processed | 33 |
| Transcript-bearing scenes | 32 |
| Processing-error scenes | 0 |
| WSL audio scenes | 33 / 33 |
| Qdrant clip vectors | 33 |
| Qdrant dino vectors | 33 |
| Qdrant text vectors | 32 |
| Qdrant audio vectors | 32 |
| KG node profile | scene=33, person=11, temporal_context=7, location=5, concept=1, entity=1 |
| KG edge profile | appears_in=22, co_occurs=12, interacts_with=6, located_in=5 |

### Why This Matters

- The clean rebuild matched the warmed-cache control structurally: scene count, transcript coverage, and WSL audio routing all held.
- The semantic cleanup survived a full state wipe: typed KG edges remained present and filler-node noise stayed low.
- Retrieval anchors still landed on the expected scenes:
  - `coffee shop conversation` -> scene 3
  - `laundry day clothes joke` -> scene 10
  - `George complaining` -> scene 18
  - `awkward Laura greeting` -> scene 24

### Remaining Constraint

- `audio_embed_clap` still failed as an optional step on one scene during the clean reset run, which kept audio vectors at 32 instead of 33 without causing a processing failure.
- `speaker_count` remained 0 across scenes, so `speaks_in` relations are still not being emitted in this control slice.

## Semantic Strengths

- Strongest nearest-neighbor semantic cohesion: **clip**.
- Multimodal coverage is high and supports cross-episode retrieval patterns.

## Weak Areas

- Character identity normalization is still inconsistent across transcript/KG surfaces.
- Typed relation density in KG depends on stronger person/location signals.
- Small residual set of transcript-missing scenes reduces downstream semantic recall.

## Recommendations

1. Improve canonical character identity stitching (speaker + transcript + KG name normalization).
2. Increase typed relation yield (`appears_in`, `located_in`, `interacts_with`) via stronger person/location extraction paths.
3. Add regression checks for semantic prompts to measure cross-episode clustering stability over time.

## What the system learned

- A dense, queryable multimodal memory of Season 1 scenes with active cross-scene and cross-episode semantic structure.
- Reliable scene-level embeddings and KG accumulation, with remaining headroom in character-level semantic precision.
