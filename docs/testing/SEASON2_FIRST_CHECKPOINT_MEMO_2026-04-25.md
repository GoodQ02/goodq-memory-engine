<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-25 -->

# Season 2 First Checkpoint Witness Memo

## Scope

- Witness root:
  - `reports/fresh_ingest_runs/20260424_182406_season2_fresh_witness/`
- Branch: `public`
- Commit context:
  - read-only visibility layer already shipped
  - read-only operator run projection layer mirrored onto the public branch
- Inputs: `02x01` through `02x12`
- Feature under witness: `scene_context_llm`

This memo is the first Season 2 checkpoint. It records the completed witness
result after the runtime observability and operator surfaces stabilized, and it
anchors the next round of upstream extractor and disagreement analysis.

## Canonical Artifacts Reviewed

- `reports/fresh_ingest_runs/20260424_182406_season2_fresh_witness/experiment_log.json`
- per-episode witness ledgers under
  `reports/fresh_ingest_runs/20260424_182406_season2_fresh_witness/*_scene_context_llm/experiment_log.json`
- canonical `temporal_index.json`
- canonical `scene_manifest.json`
- live operator projection through:
  - `lib/run_index.py`
  - `lib/run_summary.py`
  - `GET /api/runs/latest/preview`

## Operational Result

The full twelve-episode Season 2 witness passed.

- Episodes processed: `12 / 12`
- Final witness state: `completed`
- Total scenes: `466`
- Phase 6 complete: `12 / 12`
- Qdrant OK: `12 / 12`
- Generic-context regressions detected: `0 / 12`
- `scene_context_llm` coverage:
  - `02x01`: `40 / 40`
  - `02x02`: `38 / 38`
  - `02x03`: `37 / 38`
  - `02x04`: `38 / 39`
  - `02x05`: `39 / 40`
  - `02x06`: `37 / 39`
  - `02x07`: `40 / 40`
  - `02x08`: `38 / 38`
  - `02x09`: `39 / 39`
  - `02x10`: `38 / 38`
  - `02x11`: `38 / 38`
  - `02x12`: `39 / 39`

Contained optional failures remained inside the expected witness envelope:

- `02x03`: optional `audio_embed_clap` failure; contained native crashes for
  `image_embed_dino` and `image_caption`, both recovered via retry
- `02x11`: contained `image_embed_dino` native crash recovered via retry
- `02x12`: contained `object_detect` native crash recovered via `cpu_fallback`

These were witness-visible but non-fatal. They did not prevent completion,
Phase 6, or Qdrant persistence.

## Operator Surface Verification

The restored operator package read this finished witness truthfully.

- `run_index` reported:
  - `status = completed`
  - `episodes_total = 12`
  - `episodes_completed = 12`
  - `episodes_running = 0`
  - `episodes_pending = 0`
- `run_summary` reported:
  - `outcome_classification.status = success`
  - `scenes_processed = 466`
  - `latest_episode = 02x12 - The Busboy.mp4`
- `GET /api/runs/latest/preview` matched the same finished-witness state

This is important because it proves the resurfaced operator layer is reading
current structured artifacts correctly without reviving the retired `/runs`
compatibility shell.

## Season Totals

- `segments_with_scene_context_llm`: `461`
- `segments_with_candidate_visible_people`: `84`
- `segments_with_interaction_dominance`: `47`
- `segments_with_conversation_owner`: `7`
- `segments_with_speaker_aligned_mentions`: `131`
- `segments_with_transcript_entity_disagreements`: `51`

Transcript/entity disagreement category totals:

- `transcript_full_name_reduced_to_partial_entity`: `43`
- `title_elision_in_entity_projection`: `9`
- `title_bearing_transcript_name_not_resolved`: `6`

The important shape is the same as Season 1:

- `conversation_owner` stays sparse
- `interaction_dominance` stays present but selective
- speaker-aligned mention evidence is meaningfully denser than final owner
  promotion
- transcript/entity disagreement remains visible without automatically becoming
  identity truth

## Per-Episode Highlights

- Highest `conversation_owner` counts:
  - `02x10 - The Baby Shower`: `3`
  - `02x04 - The Phone Message`: `2`
  - `02x11 - The Chinese Restaurant`: `2`
- Highest `speaker_aligned_mentions` counts:
  - `02x06 - The Statue`: `18`
  - `02x10 - The Baby Shower`: `16`
  - `02x08 - The Heart Attack`: `13`
- Highest transcript/entity disagreement counts:
  - `02x02 - The Pony Remark`: `7`
  - `02x07 - The Revenge`: `7`
  - `02x08 - The Heart Attack`: `7`

## Sample A: Ownership Remains Sparse And Interaction-Backed

- Episodes with non-zero `conversation_owner`: `02x04`, `02x10`, `02x11`
- Season total: `7 / 466` segments

Why it matters:

- the ladder remains conservative on a larger witness than Season 1
- the operator visibility additions did not inflate owner claims
- ownership still appears only where chain evidence is clean enough to justify it

## Sample B: Transcript / Entity Disagreement Scales Without Driving Promotion

- Season disagreement total: `51`
- dominant family:
  - `transcript_full_name_reduced_to_partial_entity = 43`

Why it matters:

- the system is preserving an upstream normalization seam, not hiding it
- disagreement visibility scales with batch size
- disagreement does not automatically convert into stronger identity claims

## Sample C: Operator Layer And Witness Layer Agree

- Finished witness root:
  - `20260424_182406_season2_fresh_witness`
- Read-only operator surfaces:
  - `run_index`
  - `run_summary`
  - `/api/runs/latest/preview`

Why it matters:

- the system now has a truthful read path for completed and in-flight run state
- operator visibility is no longer trapped behind retired run-summary shells
- this lowers audit friction without changing ingestion, KG writes, or inference

## Interpretation

Season 2 is the first witness large enough to say the current shape is holding.

What it proves:

1. The current runtime remains stable over a twelve-episode batch.
2. The interaction ladder stays conservative on a larger season.
3. The transcript/entity disagreement layer is genuinely useful and scales with
   batch size.
4. The resurfaced operator package is stable enough to trust as a read-only
   observability surface.

The most important point is that none of this required loosening identity or
ownership behavior. The gain here is visibility, not semantic aggression.

## Recommended Next Step

Use this checkpoint as the anchor for the next surgical upstream seam pass.

Priority order:

1. compare Season 1 and Season 2 disagreement families directly
2. identify the most repeated high-signal transcript/entity seams
3. only then decide whether the next change should be:
   - read-only extractor/disagreement observability, or
   - a narrowly scoped normalization fix

Do not treat this memo as authorization to loosen ownership thresholds,
identity promotion, KG writes, or retrieval behavior.
