# Seinfeld Experiment Summary

## Pipeline Metrics

| Metric | Value |
| --- | --- |
| Episodes processed | 5 |
| Scenes processed | 185 |
| Transcript-bearing scenes | 181 |
| Transcript coverage | 97.8% |
| Qdrant clip vectors | 185 |
| Qdrant dino vectors | 185 |
| Qdrant text vectors | 182 |
| Qdrant audio vectors | 184 |
| KG nodes | 481 |
| KG edges | 313 |
| Primary run step failures | 0 |

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