<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-28 -->

# R-08 Human-Perceived Quality Audit — 2026-07-28

## Purpose

This read-only audit asks a stricter question than “did the pipeline run?”:
whether each canonical scene has inspectable evidence, explainable outcomes, and
coherent derived projections suitable for human review. It does not claim that a
heuristic can judge the meaning or quality of a personal memory.

## Reusable formula

For every canonical scene, check:

1. **Inspectable evidence:** representative frame and audio artifact exist.
2. **Explainable outcome:** empty transcript, signature absence, and processing
   errors state why they occurred.
3. **Projection coherence:** manifest transcript, segments, and speakers agree
   with the temporal index.
4. **Temporal plausibility:** transcript segment timestamps do not materially
   exceed the scene boundary.
5. **Human queue:** emit a small deterministic evidence packet for every finding
   class, without embedding source dialogue or ranking a memory by recovery
   provenance.

The reusable read-only tool is
`scripts/diagnostics/audit_human_perceived_quality.py`. Its report contains
scene IDs and local evidence locations, not transcript contents.

## July corpus result

The active July manifest authority has 12 videos and 1,457 canonical scenes.

| Surface | Result | Interpretation |
| --- | ---: | --- |
| Representative frames available | 1,457 / 1,457 | Human visual inspection is possible for every canonical scene. |
| Audio artifacts available | 1,454 / 1,457 | Three preserved-artifact restores have transcript truth but no current audio chunk. |
| Non-empty transcripts | 1,428 / 1,457 | 29 empty transcripts require an explicit outcome reason before being treated as intentional silence. |
| Signature successes | 37 | Valid speaker-signature evidence exists but coverage is incomplete. |
| Signature errors | 1,408 | Historical Wav2Vec cache-miss debt; not evidence that the current locked runtime is unhealthy. |
| Signature skips | 9 | Six insufficient-diverse-speech and three diarization-unavailable skips are already explained. |
| Content processing errors | 5 | Requires scene-level classification, not a corpus rerun. |
| Segment boundary excess above 5 seconds | 14 | Requires a timestamp-contract review; padding is not automatically a failure. |

## Projection findings

- The 46 recovery-addendum projections have been reconciled into their 10
  matching temporal indexes through a scope-bound, backup-backed operation.
  The recovery provenance is neutral audit context; it does not alter ranking,
  retrieval, or confidence.
- There are 17 additional pre-existing temporal mismatches: 4 transcript-text
  mismatches and 17 segment-count mismatches, with overlap. These must be
  classified separately from the addendum rather than silently swept into its
  repair.
- All 1,457 canonical scene IDs are present in a temporal index; there are no
  missing temporal segments.

## What this proves and what it does not

It proves that the corpus is richly inspectable and that the historic quality
debt is now visible as discrete, bounded finding classes. It does not establish
that any transcript, diarization label, or visual caption is semantically
correct. The generated review queue is the next human evidence surface for that
question.

## Field-path contract

The audit reads each claim from its named authority rather than inferring one
status from another:

| Claim | Authority field |
| --- | --- |
| Transcript | `scene.audio.full_text`, fallback `scene.audio.transcript` |
| Transcript segments | `scene.audio.segments` |
| Runtime diarization | `scene.audio.diarization_status` |
| Derived diarization | `scene.diarization_status` |
| Speaker IDs | scene and nested audio speaker payloads, in precedence order |
| Signature metadata | `scene.audio.speaker_voice_signature_meta` |
| Temporal projection | matching `temporal_index.segments[scene_id]` |

This prevents a derived-field lag from being reported as a failed runtime
diarization operation.

## Ordered next seams

1. Build a reviewed, signature-only historical backfill plan for the 1,408
   failed Wav2Vec records. The scene-first proof has passed using the locked
   model authority while preserving transcript, diarization, and CLAP outputs;
   no batch backfill has run. The inspect-only plan classifies 1,328 scenes as
   eligible and 80 as blocked because their manifests retain no diarization
   segments despite a `success` status. Those 80 must not be silently retried.
2. Review the five content-error packets, 29 unexplained empty transcripts, and
   14 boundary-excess packets. Only then define any historical metadata or
   timestamp repair; do not infer “silence” from an empty field.

## Non-actions

- No source media, corpus manifest, temporal index, vector collection, or
  knowledge graph was changed by this audit.
- No historical Wav2Vec backfill has run.
- No broad re-ingestion is justified by these findings.
