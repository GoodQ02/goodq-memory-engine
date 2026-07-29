<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: RESTART_HANDOFF -->
<!-- DOC_LAST_VERIFIED: 2026-07-29 -->

# R-08 Historical Audio Repair Restart Handoff

## Objective

Make historical audio evidence truthful and repairable without re-ingesting the
July home-memory corpus or conflating independent evidence lanes.

## Authority Surfaces Checked

- Active epoch artifacts for `epoch_2026_07_05_home_memory_clean_01`.
- Canonical scene manifests and their matching temporal projections.
- The signature-only proof envelope and one-scene backfill receipt.
- WSL worker contract tests and the fresh zero-track diarization proof.
- Repository branch `codex/r08-identity-integration-20260727`, through commit
  `af3ad83a` before this reconciliation.

## Verified Complete

1. **Recovery temporal reconciliation:** the 46 recovered scenes were
   reconciled into 10 temporal indexes. The receipt has a backup and proves no
   manifest, SQLite, vector, or graph changes.
2. **Signature-only capability proof:** WSL consumed existing waveform and
   persisted diarization only, emitted two 768-dimensional Wav2Vec signatures
   on CUDA, and did not re-transcribe or re-diarize.
3. **One-scene historical signature backfill:** one canonical July scene and its
   matching temporal projection were promoted with a digest-bound receipt,
   backup, rollback boundary, and unchanged transcript/diarization evidence.
4. **Forward zero-track truthfulness:** the WSL audio worker now emits
   `completed_no_speakers` with an explanatory note when diarization completes
   but produces zero tracks. A fresh isolated CUDA proof confirmed that outcome.
5. **Historical zero-track metadata reconciliation:** exactly 80 legacy
   signature-failure zero-track scenes were normalized in their canonical and
   temporal projections. The operation checked 10 manifest/temporal pairs,
   created 20 file backups, and emitted a digest-bound receipt. The 3
   `skipped:diarization_unavailable` scenes were excluded.
   Operation: `diarization_outcome_reconciliation_20260729T050409Z_3d4aa1022bbc`.
   Independent post-audit found 80 runtime and 80 derived normalized outcomes,
   with zero status-path disagreements.
6. **First serial signature batch:** the first 10 inspected eligible scenes
   completed with CUDA signature proofs and independent per-scene backup audits.
   Each signature count matches its temporal projection; transcript,
   diarization, CLAP, visual, and all other non-signature fields are unchanged.
   The eligible debt moved from 1,327 to 1,317, while Qdrant audio remained
   green at 1,453 points. Batch operation:
   `signature_backfill_batch_20260729T065638Z_73f62119ca3d`.

## Still Unproven Or Intentionally Unchanged

1. **Historical signature debt:** 1,317 scenes remain eligible for
   signature-only backfill. The serial executor is now fixture-proven and one
   ten-scene live batch has passed its independent audit.
2. **Separate human-quality queues:** 17 pre-existing temporal mismatches, 29
   empty-transcript scenes, and 5 processing-content errors remain review
   queues. They are not part of the zero-track or signature repair lanes.

## Exact Resume Seam

Inspect the next fresh ten-scene signature-only CUDA plan and explicitly
approve or reject it. It remains a separate token-bound write gate; no digest
or approval carries forward from the completed first batch.

## Do Not Repeat

- Do not rerun the 46-scene audio recovery or its temporal reconciliation.
- Do not treat the 80 zero-track scenes as eligible for signature backfill.
- Do not launch another signature batch until its fresh inspected digest and
  separate approval exist.
- Do not hand-edit `docs/agent/CURRENT_STATE.md` or
  `docs/agent/current_state.json`; both are generated corpus/runtime snapshots.

## Targeted Validation Already Passed

- 16 focused reconciliation, quality-audit, WSL diarization, and
  signature-planner tests.
- Python compilation and documentation drift lint.
- Fresh isolated zero-track proof: CUDA active, transcript and embeddings
  successful, zero tracks, explicit `completed_no_speakers` status.
- A no-repeat probe that correctly found no remaining legacy zero-track
  metadata targets.
- Ten focused batch-executor, one-scene-promotion, and planner tests, plus the
  live first-batch execution and independent backup-versus-canonical audit.
- Managed WSL executor activation check: the executor now sources the existing
  CUDA setup script; live runtime reports the configured GPU and all 10 proofs
  were CUDA successes.

## Approval Boundary

The metadata reconciliation and first signature batch were explicitly approved
and completed. Every later batch remains a separate explicit approval and
verification gate.
