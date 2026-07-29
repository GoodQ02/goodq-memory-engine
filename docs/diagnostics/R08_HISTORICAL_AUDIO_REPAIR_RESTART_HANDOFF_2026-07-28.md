<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
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
  `12761d2d` after the serial closeout.

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
6. **Historical signature closeout:** all 1,134 scenes eligible under the
   corrected diversity contract were processed without re-ingestion: the
   initial audited 10-scene batch, 64 audited batches before the receipt-lock
   stop, and the final 49 audited batches. Every promoted scene has a CUDA
   proof, backup-backed receipt, and matching temporal signature projection.
   The final receipt is
   `<data_root>/GoodQ_Data/epochs/epoch_2026_07_05_home_memory_clean_01/signature_backfill_serial_runs/signature_backfill_serial_20260729T095143Z_b5b67c054858/receipt.json`.
   It records 49 batches, 484 unique scenes, 975 signatures, and no error.
   A fresh planner rebuild returns zero eligible scenes. Qdrant audio remains
   green at 1,453 points because this lane changes canonical derived fields,
   not vector collection membership.
7. **Windows receipt resilience:** a prior serial run stopped after 64 audited
   batches only because a concurrent receipt replacement encountered a transient
   Windows sharing violation. The writer now retries bounded sharing and lock
   violations while preserving atomic replacement; focused regression coverage
   passed before the final run.

## Still Unproven Or Intentionally Unchanged

1. **Terminal no-signature outcomes:** 236 scenes have no safe signature
   computation and are not execution failures: 80 completed-no-speaker/
   zero-segment scenes and 156 `insufficient_diverse_speech` scenes. They
   remain separately visible review outcomes; do not fabricate fallback
   embeddings or rerun media for them.
2. **Separate human-quality queues:** 17 pre-existing temporal mismatches, 29
   empty-transcript scenes, and 5 processing-content errors remain review
   queues. They are not part of the zero-track or signature repair lanes.

## Exact Resume Seam

The signature backfill lane is closed. Resume with the next independent seam:
repair the API/Operator Console WSL authority projection so it reports the
managed worker contract rather than a stale default-shell probe. This is a
visibility repair only; it must not alter the closed corpus lane.

## Do Not Repeat

- Do not rerun the 46-scene audio recovery or its temporal reconciliation.
- Do not treat the 80 zero-track scenes as eligible for signature backfill.
- Do not launch another signature batch unless a new inspect-only plan finds a
  genuinely eligible scene.
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
- Final serial receipt: 49/49 audited batches, 484 unique scenes, 975 emitted
  signatures, zero error, and an empty final stderr log.
- Fresh final planner rebuild: zero eligible and 236 terminally blocked scenes.
- Managed WSL executor activation check: the executor now sources the existing
  CUDA setup script; live runtime reports the configured GPU and all 10 proofs
  were CUDA successes.
- Planner diversity-boundary tests and a live read-only reclassification: 156
  former candidates now correctly block as `insufficient_diverse_speech`, so
  no WSL proof is spent on a deterministic zero-signature outcome.

## Approval Boundary

The historical signature lane is complete. The terminal blocked queues are not
authorized for automatic fallback or media reprocessing. Any repair of the
separate human-quality queues or API WSL visibility requires its own scoped
decision and verification gate.
