<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-16 -->

# R-07 Qdrant Observer Seam Checkpoint

## Outcome

The fail-closed Qdrant observer seam is implemented and checkpointed.

The implementation changes only the newly created observer module and its focused unit tests:

- `cli/clean_memory_qdrant.py`
- `tests/unit/test_clean_memory_qdrant.py`

It preserves the exact four-symbol public API, validates configuration projection digests, limits error codes to those permitted, and maps Qdrant network and status failures (refused, timeout, 404, 500) to `exists=False` records. It adds no mutative operations, plan execution, cleanup, or token capabilities.

## Closed Contract

- The module `cli/clean_memory_qdrant.py` exports exactly `__all__ = ('QDRANT_OBSERVATION_SCHEMA', 'QdrantObservationError', 'QdrantObservation', 'observe_qdrant')` in that order.
- `QDRANT_OBSERVATION_SCHEMA` is exactly `goodq.clean-memory-qdrant-observation.v1`.
- `observe_qdrant(configuration)` rejects subclasses, mappings, paths, and digest mismatches before initiating any connection.
- Connection timeout, connection refused, HTTP 404, or HTTP 500 errors map to `exists=False` target records.
- Points are scrolled deterministically to calculate the `"point_state_sha256"` fingerprint when collections exist.
- Import purity is preserved (no `qdrant_client` dependency at import time).

## TDD And Review Hardening

The Qdrant observer seam was implemented test-first. A RED receipt was captured before production source code was added, showing all 6 test scenarios failing with `ModuleNotFoundError`.

All 7 test cases now pass GREEN.

## Fresh Verification

All commands used the `goodq_core` conda environment.

| Gate | Result |
| --- | ---: |
| Clean-memory unit test suite | 557 passed |
| Full private gate tests | 4018 passed |
| Python compilation | passed |
| Public API census | 4 expected symbols |
| Import purity check | passed |
| Document authority verification | passed |

The committed SHA-256 hashes are:

```text
cli/clean_memory_qdrant.py
1EB1C31F420B7BC5A5EB2F432238E8EA35F0B73A0081F2F72D2AC6649CF9992E

tests/unit/test_clean_memory_qdrant.py
C9CDDD2267BB37A3073D23BD613C23466ADC390902620A39F738A2EC94F1D43D
```

## Evidence Boundary

No live network connections (outside of loopback HTTP REST testing) were made, and no live data was mutated or deleted.

## Next Bounded Mission

Reconcile identity database tests to temporary roots under R-08.
