<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-25 -->

# Season 1 vs Season 2 Forensic Comparison Memo

## Scope

- Season 1 witness roots:
  - `reports/fresh_ingest_runs/20260424_003250_season1_recompare_witness/`
  - `reports/fresh_ingest_runs/20260424_065027_season1_remaining_witness/`
- Season 2 witness root:
  - `reports/fresh_ingest_runs/20260424_182406_season2_fresh_witness/`
- Branch: `main`
- Comparison target:
  - `docs/testing/SEASON1_RECOMPARE_WITNESS_MEMO_2026-04-24.md`
  - `docs/testing/SEASON2_FIRST_CHECKPOINT_MEMO_2026-04-25.md`
- Inputs:
  - Season 1: `01x01` through `01x05`
  - Season 2: `02x01` through `02x12`
- Feature under witness: `scene_context_llm`

This memo is a forensic comparison, not a new baseline definition. The goal is
to compare the first fully re-witnessed Season 1 batch against the first fully
witnessed Season 2 batch so we can identify which seams are scaling, which
behaviors are staying stable, and where the next surgical upstream pass should
focus.

## Canonical Artifacts Reviewed

- root `experiment_log.json` for all three witness roots
- per-episode witness ledgers under each `*_scene_context_llm/` directory
- canonical `temporal_index.json`
- canonical `scene_manifest.json`

This comparison uses canonical structured artifacts only. It does not depend on
raw stdout/stderr logs except for the contained optional-failure ledger.

## Executive Verdict

The runtime shape is holding.

What scaled up from Season 1 to Season 2:

- total scene volume
- total `scene_context_llm` coverage
- total speaker-aligned mention evidence
- total transcript/entity disagreement visibility
- total interaction evidence

What stayed meaningfully stable:

- `conversation_owner` remained sparse relative to batch size
- disagreement did not cause identity or ownership inflation
- optional failures remained contained and non-fatal
- the dominant disagreement seam stayed the same:
  `transcript_full_name_reduced_to_partial_entity`

The comparison does **not** point toward threshold loosening. It points toward
an upstream normalization seam that is now visible at larger scale.

## Operational Comparison

Season-level witness result:

| Measure | Season 1 | Season 2 |
| --- | ---: | ---: |
| Episodes passed | `5 / 5` | `12 / 12` |
| Final witness state | `completed` | `completed` |
| Total scenes | `185` | `466` |
| `scene_context_llm` segments | `179` | `461` |
| Coverage rate | `96.8%` | `98.9%` |
| Phase 6 complete | `5 / 5` | `12 / 12` |
| Qdrant OK | `5 / 5` | `12 / 12` |
| Generic-context regressions | `0` | `0` |

Contained optional failures:

- Season 1:
  - `audio_embed_clap`: `01x01`, `01x04`, `01x05`
  - `image_caption`: `01x03`, `01x04`
  - `image_embed_dino`: `01x04`
- Season 2:
  - `audio_embed_clap`: `02x03`
  - `image_caption`: `02x03`
  - `image_embed_dino`: `02x03`, `02x11`
  - `object_detect`: `02x12` via contained `cpu_fallback`

Interpretation:

- both seasons completed cleanly despite optional subsystem faults
- Season 2 introduced one contained `object_detect` fallback event, but the
  witness still landed fully clean
- there is no evidence here of systemic instability increasing with batch size

## Absolute Visibility Totals

| Metric | Season 1 | Season 2 | Delta |
| --- | ---: | ---: | ---: |
| `scene_count` | `185` | `466` | `+281` |
| `segments_with_scene_context_llm` | `179` | `461` | `+282` |
| `segments_with_candidate_visible_people` | `47` | `84` | `+37` |
| `segments_with_interaction_dominance` | `23` | `47` | `+24` |
| `segments_with_conversation_owner` | `3` | `7` | `+4` |
| `segments_with_speaker_aligned_mentions` | `70` | `131` | `+61` |
| `segments_with_transcript_entity_disagreements` | `27` | `51` | `+24` |

Absolute totals rose in every additive lane, which is expected because Season 2
is materially larger than Season 1.

## Normalized Density Comparison

To compare the seasons fairly, the same signals were normalized per `100`
scenes.

| Metric per 100 scenes | Season 1 | Season 2 |
| --- | ---: | ---: |
| candidate-visible segments | `25.4` | `18.0` |
| interaction-dominance segments | `12.4` | `10.1` |
| conversation-owner segments | `1.6` | `1.5` |
| speaker-aligned-mention segments | `37.8` | `28.1` |
| transcript/entity disagreement segments | `14.6` | `10.9` |

This matters.

Season 2 is larger in total but somewhat **less dense per 100 scenes** in the
same visibility lanes. That does **not** read like a regression. It reads like:

- Season 1 had a tighter early-season interaction profile
- Season 2 scaled the same conservative behavior across a broader narrative
  spread
- the ladder stayed disciplined instead of inflating with batch size

The most important stability signal is `conversation_owner`:

- Season 1: `3 / 185 = 1.6 per 100 scenes`
- Season 2: `7 / 466 = 1.5 per 100 scenes`

That is effectively flat.

## Transcript / Entity Disagreement Comparison

Unique disagreement-bearing segments:

- Season 1: `27`
- Season 2: `51`

Category incidence totals:

| Category | Season 1 | Season 2 |
| --- | ---: | ---: |
| `transcript_full_name_reduced_to_partial_entity` | `28` | `43` |
| `title_elision_in_entity_projection` | `3` | `9` |
| `title_bearing_transcript_name_not_resolved` | `2` | `6` |

Important note:

- category counts are **incidences**, not unique segments
- one segment may contribute more than one disagreement category

The dominant seam is clear in both seasons:

- `transcript_full_name_reduced_to_partial_entity`

That means the same underlying behavior is repeating:

- transcript surface carries a richer full name
- canonical entity truth keeps a shorter person form

Examples from the two seasons:

- Season 1:
  - `Elaine Bennis -> Elaine`
  - `Jerry Seinfeld -> Jerry`
- Season 2:
  - the same class continues and broadens across a larger cast

This is the strongest evidence in the whole comparison. The disagreement layer
is not random noise; it is exposing one repeated upstream normalization pattern.

## Top Disagreement Families

Most repeated families observed:

Season 1:

- `partial::elaine` -> `3`
- `partial::jerry` -> `3`
- `partial::art` -> `2`
- `partial::mac` -> `2`
- `partial::joel` -> `2`
- `partial::lenny` -> `2`

Season 2:

- `partial::leo` -> `4`
- `partial::elaine` -> `4`
- `partial::george` -> `4`
- `partial::jerry` -> `4`
- `title::cohen` -> `3`
- `title::costanza` -> `2`
- `partial::sharon` -> `2`
- `title_unresolved::mrs hudwalker` -> `2`
- `partial::rick` -> `2`

Interpretation:

- the repeat offenders are not exotic tails
- they are common cast-name reductions and title-handling seams
- the same family classes recur across both seasons, which strengthens the case
  that the next pass should be upstream and surgical rather than downstream and
  aggressive

## Interaction and Ownership Shape

High-level season shape:

- Season 1:
  - `speaker_aligned_mentions = 70`
  - `conversation_owner = 3`
- Season 2:
  - `speaker_aligned_mentions = 131`
  - `conversation_owner = 7`

Owner-to-aligned ratio:

- Season 1: `4.3%`
- Season 2: `5.3%`

That ratio stayed low in both seasons.

Why this matters:

- the system is collecting much more interaction evidence than it promotes into
  final ownership
- the owner ladder is still conservative even after the visibility work and the
  chain-local canonicalization seam
- nothing in this comparison argues for loosening owner thresholds

Season 2 highest owner-bearing episodes:

- `02x10 - The Baby Shower`: `3`
- `02x04 - The Phone Message`: `2`
- `02x11 - The Chinese Restaurant`: `2`

Season 1 highest owner-bearing episode:

- `01x02 - The Stakeout`: `3`

So the strong owner cases remain episodic and local, not season-wide inflation.

## Forensic Read

The cleanest interpretation is:

1. The runtime is stable across both seasons.
2. The additive visibility lanes are functioning as intended.
3. The disagreement layer is now strong enough to identify one dominant
   upstream seam repeatedly.
4. The interaction ladder is remaining disciplined under scale.

The comparison does **not** say:

- loosen `conversation_owner`
- loosen identity promotion
- treat disagreement as implicit truth

The comparison **does** say:

- the next high-value seam is upstream normalization around transcript full-name
  to partial-entity reduction
- title handling remains the next secondary hotspot

## Recommended Next Step

The next surgical pass should target the dominant repeated seam, but it should
still begin with observability discipline.

Priority order:

1. Rank the repeated `full_name -> partial_entity` families by frequency and
   semantic importance.
2. Confirm whether the most repeated families are safe canonicalization targets
   or should remain read-only disagreement surfaces.
3. Only then choose between:
   - a read-only upstream extractor/normalization observability pass, or
   - a very narrow normalization fix for the highest-confidence repeated family
     class

Do **not** use this memo as justification for:

- threshold tuning
- broader canonicalization expansion
- owner inflation
- KG write changes
- retrieval ranking changes

## Bottom Line

Season 2 did exactly what we hoped it would do for the forensic picture.

It did not reveal a collapsing ladder. It revealed a stable ladder operating at
larger scale, while confirming that the main remaining precision seam is
upstream name normalization, not downstream ownership logic.
