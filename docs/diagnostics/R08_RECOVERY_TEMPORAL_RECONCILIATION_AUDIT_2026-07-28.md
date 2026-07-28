<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-28 -->

# R-08 Recovery Temporal Reconciliation Audit — 2026-07-28

## Scope

This is a read-only comparison of the committed July recovery addendum against
the temporal-index projections for its affected videos. It does not modify the
active epoch, manifests, temporal indexes, vectors, knowledge graph, or audio
artifacts.

## Governing invariant

The temporal index is a derived projection of canonical scene truth. A committed
audio recovery addendum must therefore appear in the matching temporal segments,
but the addendum's provenance remains audit-only and must not alter retrieval,
ranking, or confidence.

## Evidence compared

- Active epoch: `epoch_2026_07_05_home_memory_clean_01`.
- Addendum: `recovery_addendum_20260728T154754Z_0d48779d8b45`.
- Changed canonical scenes: 46 across 10 videos.
- Compared fields: full transcript, transcript segments, diarization status,
  speaker IDs, and speaker-signature count.

## Result

All 46 scene IDs already exist in their respective temporal indexes. None is
missing or structurally ambiguous. However, every compared temporal segment
still contains the pre-recovery audio projection:

| Field | Matching | Stale |
| --- | ---: | ---: |
| Full transcript | 0 | 46 |
| Transcript segments | 0 | 46 |
| Diarization status | 0 | 46 |
| Speaker IDs | 3 | 43 |
| Speaker-signature count | 6 | 40 |

Each of the 10 temporal indexes predates its corresponding updated scene
manifest. This is a stale derived projection, not missing corpus data and not a
failed recovery.

## Why the generic harmonizer is not the executor

`run_cross_modal_harmonization` writes a complete temporal index and persists a
broad set of derived fields back to every scene in a manifest. Its normal path
also permits entity extraction and configured scene-context LLM work. Reusing it
for this correction could refresh unrelated visual, entity, or context fields,
which violates the recovery addendum's scene-scoped, audio-only boundary.

## Required next write gate

Implement and test a dedicated temporal-audio reconciler before any live write.
It must:

1. accept only the committed addendum receipt and its exact 46 scene IDs;
2. preflight exact scene/video identity plus manifest and temporal-index
   checksums;
3. update only the five stale audio-derived temporal fields for those IDs;
4. write a backup, scope-bound confirmation, and before/after receipt;
5. preserve all non-target temporal segments and all manifest fields; and
6. retain `recovery_addendum` as neutral provenance only.

After fixture tests and a one-video disposable proof, the separate live
confirmation may reconcile the 10 affected temporal indexes. It is not a corpus
re-ingestion or a broad Phase 6b rerun.

## Explicit non-actions

- No July corpus data changed during this audit.
- No temporal index was refreshed.
- No vector, SQLite, knowledge-graph, or API mutation occurred.
- No proof-epoch collection was promoted.
