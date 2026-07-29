<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-29 -->

# R-08 Quality Queue Reconciliation — 2026-07-29

## Objective

Record the closed July historical-audio repair lanes and the remaining review
queues without conflating their evidence, authority, or approval boundaries.

## Authority Surfaces Checked

- Canonical July scene manifests under the configured processing root.
- Matching temporal-index scene projections.
- The inspect-only signature-backfill planner.
- The read-only human-perceived-quality audit, whose signature reader now
  prefers the canonical `scene.audio.speaker_voice_signature_meta` field over
  the stale legacy top-level projection.

## Verified Complete

1. The 46 recovered scenes were reconciled into their temporal projections.
2. Historical transcript outcomes were explicitly reconciled for 29 legacy
   empty-transcript scenes; none remain without an explicit outcome.
3. Five stale content-state labels were reconciled; no content-processing error
   label remains in the canonical manifest audit.
4. Historical signature-only backfill is closed. The fresh planner reports zero
   eligible scenes. It reports 236 terminally blocked historical signature
   failures: 80 `completed_no_speakers` outcomes and 156
   `insufficient_diverse_speech` outcomes. These are not safe candidates for a
   fallback embedding or media rerun.
5. The quality audit and signature planner now agree on canonical signature
   status: 1,209 scenes are `ok`; the 236 terminal failures are visible rather
   than masked by stale top-level metadata.

## Separate Remaining Review Queues

| Queue | Count | Required next action | Do not do |
| --- | ---: | --- | --- |
| Temporal projection mismatch | 1 | Human review of the canonical-empty versus temporal-text conflict, then a scoped decision. | Do not overwrite either source automatically. |
| Transcript segment boundary | 14 | Read-only evidence review of timestamps and scene boundaries. | Do not treat an overshoot as a transcript failure or re-run audio. |
| Terminal signature outcomes | 236 | Retain as explicit no-signature outcomes; revisit only if a future contract changes the eligibility criteria. | Do not batch backfill, synthesize, or use a fallback signature. |
| Non-error signature statuses | 12 | Retain their explicit status (`missing`, `diarization_unavailable`, or insufficient speech) for operator visibility. | Do not merge them into the historical-failure count. |

## Exact Resume Seam

Start with the 14 transcript-boundary evidence packets in a read-only review.
Each packet must be evaluated as its own scene-to-temporal-boundary question.
Only after that queue is classified should the single temporal mismatch receive
a separate scoped decision.

## Do Not Repeat

- Do not re-run the 46-scene recovery or temporal reconciliation.
- Do not re-run transcript outcome or content-state reconciliation; their
  post-audit queues are zero.
- Do not launch another historical signature batch while the planner reports
  zero eligible scenes.
- Do not use stale top-level signature metadata as a canonical status source.

## Targeted Validation

- Focused quality-audit and signature-planner tests: 8 passed.
- Quality audit Python compilation and Git whitespace check: passed.
- Fresh read-only quality audit and fresh inspect-only signature planner agreed
  on the 236 terminal signature-failure count and zero eligible backfill scope.
