<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-28 -->

# R-08 WSL Audio Offline Witness — 2026-07-28

## Scope

This checkpoint closes the current WSL audio runtime repair with one isolated,
strict witness. It is a runtime proof only: it does **not** reconcile recovery
audio into the July corpus and it does not establish whole-corpus coverage.

## Witness

| Field | Evidence |
|---|---|
| Proof epoch | `epoch_2026_07_28_wav2vec_lock_proof_05` |
| Run ID | `f89981f0-155d-4ed4-b0a1-b42f310ac9d5` |
| Source identity | SHA-256 `e6dac04aab6001b6beee8cd3cc799e199db72c31f119b2c6a1f4a8abbd0166e2` |
| Selected scene | index `27`, ID `b8ac4c8bd7b5dde1a193826ca4b5786d9effdb6c88f5e1732ff733f416d9d419` |
| Isolation | dedicated epoch and Qdrant collections; July was excluded from the run |

The receipt at `<data_root>/epochs/epoch_2026_07_28_wav2vec_lock_proof_05/outputs/scene_ingest_results.json` records:

- `audio_backend_selected=wsl` and `audio_backend_effective=wsl` with no downgrade;
- `transcript_outcome=transcript_available`, with nine transcript segments;
- successful diarization with three observed speaker labels;
- `speaker_voice_signature_meta.status=ok`, two emitted signatures, and
  768-dimensional Wav2Vec speaker embeddings;
- successful CLAP persistence to FAISS, SQLite, and its proof-epoch Qdrant
  collection; and
- successful vision, text, and cross-modal portions of the same scene run.

## Runtime repairs covered

The witness exercises the changes through `9c9edfb6`:

1. canonical model-cache authority is injected into managed WSL execution;
2. deployed WSL worker files are checked for coherence before strict audio work;
3. Pyannote cache validation recognizes the config-only pipeline and snapshot
   symlinks; and
4. the shared Pyannote adapter preserves offline execution for the installed
   API while strict WSL failures no longer silently fall back to local audio.

## Protected authority observation

Immediately after the witness, the July epoch authorities were observed as:

| Authority | SHA-256 |
|---|---|
| `memory.db` | `639D73121A07E2744500D6E59BE55684D880C7E36DA879D43A1B71339F622E81` |
| `knowledge_graph.db` | `6A2D088782FD7637E342CFAE28A6D4D7DD3BF8626245962F286EAC16241B6DC9` |

Those hashes are an observation at this checkpoint, not a substitute for the
before/after receipt required by a later reconciliation write.

## Remaining gates

1. Build and verify the scene-scoped, cross-epoch audio reconciliation for the
   46 recovered July scenes. It must rehydrate only verified transcript and
   diarization projections into the existing canonical July scene records,
   preserve visual/vector evidence, produce an addendum receipt, and support
   rollback.
2. Repair the API runtime-status projection separately: a cold WSL state after
   the witness must be presented as stopped/cold rather than as a contradictory
   audio failure.
3. Audit existing temporal-index structures before designing the next witness.

## Signature-only historical proof

After this witness, the historic July signature failures were separated from
the runtime question. The isolated proof
`epoch_2026_07_28_signature_only_proof_01` consumed one existing July audio
chunk plus its persisted diarization input and emitted exactly two
768-dimensional speaker signatures on CUDA with the pinned
`facebook/wav2vec2-base-960h` revision.

It did not invoke transcription or diarization and did not write the July
manifest, temporal index, SQLite stores, vectors, or graph. The proof output
contains signature evidence only. This establishes the scene-first executor
shape for the separate historic backfill lane; it is not a batch backfill.
