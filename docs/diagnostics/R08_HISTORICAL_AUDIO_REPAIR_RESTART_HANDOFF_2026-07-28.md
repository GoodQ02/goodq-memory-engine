<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: RESTART_HANDOFF -->
<!-- DOC_LAST_VERIFIED: 2026-07-28 -->

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

## Still Unproven Or Intentionally Unchanged

1. **Historical signature debt:** after the one-scene promotion, 1,327 scenes
   are eligible for signature-only backfill. The serial batch planner exists,
   but no batch executor or batch run exists.
2. **Separate human-quality queues:** 17 pre-existing temporal mismatches, 29
   empty-transcript scenes, and 5 processing-content errors remain review
   queues. They are not part of the zero-track or signature repair lanes.

## Exact Resume Seam

Build and inspect the serial signature-backfill executor for the 1,327 eligible
scenes. It remains a separate token-bound batch gate; do not execute a batch
until its disposable-fixture and one-batch dry-run contracts pass.

## Do Not Repeat

- Do not rerun the 46-scene audio recovery or its temporal reconciliation.
- Do not treat the 80 zero-track scenes as eligible for signature backfill.
- Do not launch the 1,327-scene signature batch. Build and inspect a separate
  serial executor only after the metadata lane has a verified receipt.
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

## Approval Boundary

The metadata reconciliation was explicitly approved and completed. A future
signature batch remains a separate approval and verification gate.
