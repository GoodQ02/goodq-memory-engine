<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-29 -->

# R-08 Qdrant Retention Manifest — 2026-07-29

## Scope and decision

This is a read-only retention manifest for the Qdrant census observed after the
July quality-reconciliation closeout. It is not a cleanup plan, authorization,
or deletion command.

The active epoch owns exactly four configured collections. They are excluded
from this manifest. The other collections are isolated recovery, proof, or
witness evidence. All remain **retained pending an explicit cleanup decision**.

## Observed census

| Class | Collections | Points | Retention disposition |
| --- | ---: | ---: | --- |
| Active July authority | 4 | 11,571 | Excluded; never a cleanup candidate here |
| 2026-07-26 audio recovery | 3 | 322 | Retain; recovery provenance |
| 2026-07-27 CLAP recovery and proofs | 12 | 367 | Retain; recovery/proof provenance |
| 2026-07-28 two-scene witnesses | 12 | 48 | Retain; pipeline witness provenance |
| 2026-07-28 Wav2Vec lock proofs | 16 | 29 | Retain; runtime proof provenance |
| R24 witness family | 13 | 22 | Retain; historical witness provenance |
| **Non-authority total** | **56** | **788** | **Retain pending explicit decision** |

The configured active collections were green and exactly matched the active
epoch authority. No non-authority collection claimed the active epoch through
the inspected payload provenance.

## Provenance caveat

The current audio-vector writer does not consistently persist `epoch_id` in its
point payload. This applies to all 1,453 active audio points and 56
non-authority audio points in the observed set. The collection name remains the
epoch routing authority for those records.

Therefore a future retention or cleanup operation must require all of the
following before acting on any collection:

1. a fresh resolved active-epoch projection;
2. an exact collection-name allowlist that excludes those four active names;
3. a fresh collection point-state fingerprint and count;
4. this collection's receipt or witness linkage; and
5. a separately approved, token-bound cleanup action with a durable result
   manifest.

Do not use payload `epoch_id` absence as evidence that an audio collection is
unowned or safe to remove.

## Do not repeat

- Do not merge retained proof or recovery vectors into active July retrieval.
- Do not delete the 56 non-authority collections from this manifest alone.
- Do not use collection naming as a substitute for a fresh pre-action
  fingerprint.

## Exact next seam

The retention classification is complete. Any cleanup is a distinct destructive
operation requiring an explicit decision and a fresh, collection-scoped cleanup
manifest. No corpus, Qdrant collection, or runtime configuration changed during
this audit.
