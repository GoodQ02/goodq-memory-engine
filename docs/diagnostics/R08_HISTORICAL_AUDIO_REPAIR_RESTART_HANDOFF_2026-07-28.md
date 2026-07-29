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
  `3769d7cb`.

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

## Still Unproven Or Intentionally Unchanged

1. **Historical zero-track labels:** 80 existing canonical scenes still record
   legacy `diarization_status=success` despite zero persisted tracks. Their
   audio exists; no diarization artifact was lost. They are not signature
   inputs and must not be re-diarized merely to change a label.
2. **Historical signature debt:** after the one-scene promotion, 1,327 scenes
   are eligible for signature-only backfill. The serial batch planner exists,
   but no batch executor or batch run exists.
3. **Separate human-quality queues:** 17 pre-existing temporal mismatches, 29
   empty-transcript scenes, and 5 processing-content errors remain review
   queues. They are not part of the zero-track or signature repair lanes.

## Exact Resume Seam

Implement and validate a token-bound, metadata-only reconciliation for the 80
historical zero-track scenes. It must:

- inspect and hash the exact target set before writing;
- back up the affected canonical manifests and temporal indexes;
- change only the diarization status and explanatory note in the existing
  canonical and matching temporal fields;
- perform no WSL work, media processing, transcription, diarization, signature
  calculation, vector write, re-ingestion, SQLite write, or graph write; and
- emit a receipt and independently re-audit the 80 targets.

The intended normalized status is `completed_no_speakers`. It means the
diarization operation completed but emitted no speaker tracks; it is not a
failure, an absent audio claim, or a successful speaker-evidence claim.

## Do Not Repeat

- Do not rerun the 46-scene audio recovery or its temporal reconciliation.
- Do not treat the 80 zero-track scenes as eligible for signature backfill.
- Do not launch the 1,327-scene signature batch. Build and inspect a separate
  serial executor only after the metadata lane has a verified receipt.
- Do not hand-edit `docs/agent/CURRENT_STATE.md` or
  `docs/agent/current_state.json`; both are generated corpus/runtime snapshots.

## Targeted Validation Already Passed

- 13 focused WSL diarization and unified-bridge tests.
- Python compilation and documentation drift lint.
- Fresh isolated zero-track proof: CUDA active, transcript and embeddings
  successful, zero tracks, explicit `completed_no_speakers` status.

## Approval Boundary

The user has approved the bounded metadata reconciliation. A future signature
batch remains a separate approval and verification gate.
