<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-28 -->

# R-08 Pipeline Recovery and Witness Closeout — 2026-07-28

## Purpose

This record closes the July audio-recovery and runtime-proof lane. It preserves
what was proven, what changed in the active corpus, and the exact next checks so
future work does not repeat a successful recovery or treat isolated proof data as
production authority.

## Verified complete

### Active July corpus

The active authority remains `epoch_2026_07_05_home_memory_clean_01`. The fresh
current-state evidence records 12 media sources, 1,648 materialized scenes,
75,094 promoted UCF context frames, and four configured green Qdrant collections.
The epoch is complete and fully promoted; it is not an ingestion target.

### Scene-scoped audio recovery

Recovery addendum `recovery_addendum_20260728T154754Z_0d48779d8b45` committed
verified transcript and diarization projections to exactly 46 existing July scene
records. It includes a backup root, a plan digest, a post-write `memory.db`
checksum, per-manifest checksums, and the complete changed-scene list.

Its provenance policy is intentionally neutral:

- kind: `recovery_addendum`;
- retrieval effect: `none`;
- ranking effect: `none`; and
- confidence effect: `none`.

The addendum is durable audit context. It must not bias retrieval, ranking, or
identity confidence merely because it was recovered later.

### Strict WSL audio proof

The isolated witness `epoch_2026_07_28_wav2vec_lock_proof_05` completed with
strict WSL audio, no downgrade, transcript success, diarization success,
Wav2Vec embedding success, and two emitted speaker signatures for its selected
scene. The proof validates the repaired canonical cache authority, worker
coherence gate, offline Pyannote adapter, and strict-failure behavior. It is
proof-epoch evidence, not active July authority.

### Full two-scene pipeline witness

The isolated two-scene witness report at
`<data_root>/reports/pipeline_witnesses/20260728_seinfeld_01x01_two_scene_v3/`
passed with no failed assertions. It proves scene detection, visual stages,
strict WSL audio, CLAP/text/vector persistence, temporal fusion, UCF provenance,
and explicit isolation semantics. Its QA sheet contains the actual counts,
timings, vector IDs, and store receipts; it does not reproduce source dialogue.

## Current operational truth

- API and Qdrant are loopback authorities; the active epoch remains July.
- WSL may be stopped between jobs. That is a cold-runtime state, not a failed
  historical audio run.
- Isolated proof and recovery collections are not active authority. The
  current-state generator now records their count and continues to verify the
  configured four collections independently.

## Do not repeat

1. Do not re-ingest the July corpus to rediscover the 46 repaired scenes.
2. Do not re-run a broad audio recovery: the committed addendum is the recovery
   authority for this incident.
3. Do not merge proof-epoch vectors or use proof collections for normal retrieval.
4. Do not delete non-authority Qdrant collections without a separate retention
   manifest and explicit cleanup decision.
5. Do not treat this runtime/provenance closeout as a substitute for human
   identity curation or an identity-promotion decision.

## Remaining, in order

1. **Read-only temporal reconciliation audit.** Compare the 46 changed scene
   records with the temporal indexes for their affected videos. Determine whether
   each index already reflects recovered transcript/diarization evidence or
   requires a bounded re-harmonization.
2. **Operator-status freshness seam.** The API should distinguish a completed
   last-step receipt from an active pipeline job, so an idle system cannot appear
   to be processing stale CLAP work.
3. **Proof-collection retention audit.** Classify non-authority Qdrant
   collections and write a deletion/retention manifest before any cleanup.
4. **Selective development integration.** Reconcile the reviewed clean branch
   against private `dev`; do not wholesale-merge a long-lived feature branch.

## Verification surfaces

- `docs/diagnostics/evidence/CURRENT_STATE_EVIDENCE_2026-07-28.json`
- `docs/agent/CURRENT_STATE.md`
- `docs/agent/current_state.json`
- `docs/GOODQ_RAG_CONTEXT_PACK.md`
- `docs/diagnostics/R08_WSL_AUDIO_OFFLINE_WITNESS_2026-07-28.md`
- `<data_root>/epochs/epoch_2026_07_05_home_memory_clean_01/recovery_addenda/recovery_addendum_20260728T154754Z_0d48779d8b45/receipt.json`
- `<data_root>/reports/pipeline_witnesses/20260728_seinfeld_01x01_two_scene_v3/PIPELINE_WITNESS_ONE_SHEET.md`
