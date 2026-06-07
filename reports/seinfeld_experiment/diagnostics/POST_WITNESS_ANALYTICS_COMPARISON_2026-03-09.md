# Post-Witness Analytics Comparison Pack

Date: 2026-03-09

## Scope

This pack compares the original Season 1 diagnostics baseline from 2026-03-06 against the formal clean-state witness run completed on 2026-03-09.

Baseline sources:

- `diagnostics/scene_segmentation_report.md`
- `diagnostics/embedding_health_report.md`
- `diagnostics/kg_structure_report.md`
- `diagnostics/entity_analysis_report.md`
- `diagnostics/semantic_pattern_report.md`

Witness sources:

- `diagnostics/SEASON1_WITNESS_RUN_2026-03-09.md`
- `releases/season1_witness_run_2026-03-09/witness_metrics.json`
- `releases/season1_witness_run_2026-03-09/retrieval_anchor_checks.json`

Structured metrics snapshot:

- `diagnostics/post_witness_analytics_metrics_2026-03-09.json`

## Executive Delta

| Area | 2026-03-06 baseline | 2026-03-09 witness | Delta |
| --- | --- | --- | --- |
| Scenes processed | 185 | 185 | stable |
| Transcript-bearing scenes | 181 | 182 | +1 |
| Transcript coverage | 97.8% | 98.4% | +0.6 pts |
| Empty scenes | 3 | 3 | stable |
| Processing-error scenes | 1 | 0 | improved |
| Qdrant clip/dino/text/audio | 185 / 185 / 182 / 184 | 185 / 185 / 182 / 184 | stable |
| KG nodes | 481 | 310 | -171 noisy nodes |
| KG edges | 313 | 315 | +2 total, much richer typing |
| KG edge types | `co_occurs` only | `appears_in`, `interacts_with`, `located_in`, `co_occurs` | improved |
| Generic `entity` nodes | 279 | 10 | -269 |
| Non-`ok` step visibility | effectively opaque at scene level | 3 explicit optional-failure rows | improved |

## Segmentation And Coverage

The witness run did not disturb structural segmentation. Episode counts remained the same across the full control set, which is exactly what we wanted after the runtime and semantic hardening work.

The material change is coverage quality:

- the baseline had four transcript gaps, including one real processing failure on `01x02` scene `25`
- the witness run reduced that to three empty end-cap style scenes and removed the processing-error case entirely
- WSL audio remained effective on `185/185` scenes in the witness run

Per-episode witness coverage:

| Episode | Scenes | Transcript Scenes | Empty Scenes | Processing Error Scenes |
| --- | --- | --- | --- | --- |
| `01x01 - Good News, Bad News` | 33 | 32 | 1 | 0 |
| `01x02 - The Stakeout` | 39 | 38 | 1 | 0 |
| `01x03 - The Robbery` | 36 | 36 | 0 | 0 |
| `01x04 - Male Unbonding` | 38 | 38 | 0 | 0 |
| `01x05 - The Stock Tip` | 39 | 38 | 1 | 0 |

## Vector And Embedding Stability

One of the strongest results here is what did **not** change. Vector persistence held steady across the witness run:

- `clip=185`
- `dino=185`
- `text=182`
- `audio=184`

That means the runtime/path cleanup, WSL contract migration, host asset warmup, and semantic normalization work did not cost us modality coverage at season scale. The existing embedding-health story from the first-pass diagnostics still holds: no systemic collapse, high multimodal coverage, and stable season-wide retrieval support.

## Knowledge Graph Quality

This is the largest semantic win.

The 2026-03-06 KG was dominated by generic entities and undifferentiated co-occurrence:

- `481` nodes total
- `279` generic `entity` nodes
- `313` edges, all `co_occurs`
- top “entities” included filler like `I'm`, `You`, `What`, and `It's`

The witness graph is materially cleaner and more useful:

- `310` nodes total
- `scene=185`
- `person=76`
- `location=22`
- `temporal_context=15`
- `entity=10`
- `audio_event=1`
- `concept=1`

Witness edge profile:

- `appears_in=169`
- `interacts_with=86`
- `located_in=25`
- `co_occurs=35`

In plain terms: the graph lost a large amount of filler while gaining typed scene semantics. That is the core evidence that the normalization, gating, and canonical KG-path fixes landed successfully.

## Retrieval Anchor Check

The witness store was spot-checked against the tuned control prompts after the full-season run.

| Query | Witness top result | Interpretation |
| --- | --- | --- |
| `coffee shop conversation` | `01x01` scene `3` | correct episode-1 anchor held |
| `laundry day clothes joke` | `01x01` scene `10` | correct episode-1 anchor held |
| `George complaining` | `01x03` scene `23` | season-wide George complaint scene now outranks the earlier episode-1 anchor, which is semantically reasonable |
| `awkward Laura greeting` | `01x01` scene `24` | correct episode-1 anchor held |

This is a healthy outcome. The witness run preserved the episode-1 anchors we cared about, while `George complaining` now resolves to a stronger season-level complaint scene rather than being trapped on the original episode-1 control slice.

## Operational Visibility

The witness run had three non-`ok` step rows, all optional failures:

1. `sentiment` on `01x01` scene `27`
2. `audio_embed_clap` on `01x05` scene `7`
3. `sentiment` on `01x05` scene `33`

The important change is not that optional failures disappeared. It is that they are now visible and attributable:

- scene payloads preserve the warning metadata
- canonical `step_runs.jsonl` records explicit error rows
- the CLAP miss includes `embedding_emitted=false` instead of disappearing into an implied shortfall

That is a meaningful release-quality improvement in operator trust.

## Witness Comparison Verdict

The witness run improved the control benchmark in the ways that matter most:

- no segmentation drift
- better transcript coverage
- elimination of the prior processing-error scene
- stable vector counts
- dramatically cleaner KG topology
- explicit optional-failure observability

The witness run did **not** magically solve everything:

- optional `sentiment` and `CLAP` misses still exist
- speaker-aware relations are still limited because `speaker_count` remains weak in this slice
- live retrieval remains primarily text/KG-driven because CLIP query encoding is still blocked in the current runtime by the Torch 2.6 security requirement

Even with those constraints, the release baseline is stronger, cleaner, and easier to trust than the original Season 1 analytics pass.
