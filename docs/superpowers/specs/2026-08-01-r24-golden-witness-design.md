# R-24 Golden Witness Design

## Purpose

Rebuild the missing Golden Witness harness as a dev-native, one-scene proof of
the governed multimodal pipeline. The witness must establish that one known
local clip can be decoded, analyzed, transcribed, and summarized without
altering canonical memory.

## Input and authority

- Input is the local `samples/ingestion/smoke_test/seinfeld_s01e01_clip.mp4`.
- The harness records the input SHA-256 and media stream metadata before work.
- The user provides the final semantic acceptance check from a short factual
  scene summary, candidate names, and scene boundaries.
- The input is private local test material. The harness has no publishing path.

## Lifecycle

1. **Read-only preflight.** Resolve the shared model cache outside the witness
   root; verify FFmpeg/Tesseract bindings and GPU policy. Failure is explicit
   and stops before artifacts are written.
2. **Isolated witness run.** Create a uniquely named temporary witness root and
   run the canonical ingestion entry point under `ingestion_isolation: true`.
   It may write only inside that witness root and staged witness Qdrant scope.
3. **Evidence observation.** Read back scene-manifest, transcript, visual,
   audio, and staged-vector evidence. The harness records objective counts,
   digests, and any failed stage; it never treats an empty result as success.
4. **Summary.** Ask the configured local model for a factual scene summary that
   separates observed evidence from uncertainty. The result is an isolated
   witness artifact, not canonical memory.
5. **Human acceptance.** Present the short summary, candidate names, and scene
   boundaries to the operator. No promotion occurs unless separately approved.

## Boundaries

- No canonical SQLite, knowledge-graph, or active-Qdrant promotion.
- No mutation of source media, shared model cache, firewall, service, model
  configuration, or runtime policy.
- No model download or network dependency.
- No automatic repair, retry-based success claim, or cleanup outside the
  witness root. Retention/deletion of witness artifacts is a later approval.

## Success and failure

Success requires a verified input identity, successful preflight, at least one
scene with parseable multimodal artifacts, staged lifecycle evidence, and a
local factual summary. Every absent artifact, tool/device mismatch, model
failure, or summary failure is reported as a named failed stage with evidence.

## Validation plan

- Unit-test preflight failure cases before implementation.
- Unit-test witness-root containment and no-promotion configuration.
- Run the preflight locally before any witness run.
- Run exactly one isolated witness only after the preflight and focused tests
  pass.
- Require the operator's semantic check before declaring the witness accepted.
