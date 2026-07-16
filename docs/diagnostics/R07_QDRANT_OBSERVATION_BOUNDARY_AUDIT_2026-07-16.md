<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-16 -->

# R-07 Qdrant Observation Boundary Audit

## Decision

Keep the completed configuration projection at checkpoint `a12ceb18` and the authenticated protected-membership composition at checkpoint `d20a74ba` closed. Repository and platform traces determined that no existing helper satisfies the passive, fail-closed, four-collection observer contract.

The next implementation seam is exactly one import-pure observer and its focused test oracle:

- `cli/clean_memory_qdrant.py`;
- `tests/unit/test_clean_memory_qdrant.py`.

The observer accepts only an exact `ResolvedPlanConfiguration` instance, revalidates its canonical projection digest before service access, and returns one frozen `QdrantObservation`. It does not load configuration, accept an endpoint override, contact live Qdrant during import, persist evidence, build or persist a plan, create a job or token, call MiniAgent, or perform cleanup.

If the Qdrant service is down, unreachable, timeouts, or a collection is missing, the observation fails closed by returning valid collection evidence records with `exists=False` rather than raising a connection exception. This ensures downstream plan assembly receives explicit passive evidence of the target state.

## Governing Invariant

The observer is passive target evidence collection, not cleanup, execution, or configuration authority. It may inspect only the exact loopback endpoint and four collection targets already bound by the configuration projection. It must never mutate collection state, delete points, index new vectors, or bypass configuration digest validation.

An accepted observation proves a deterministic, complete pre-state for the four configured Qdrant collections. Connection refused, connection timeout, HTTP 404, or HTTP 500 errors must be mapped cleanly to `exists=False` target records.

## No-Repeat Result

The following work is complete and is not reopened by this seam:

- strict configuration projection and its three-symbol public API;
- exact target filesystem observer and no-follow Win32 OpenFileById traversal;
- authenticated protected-membership composition and its 18-role boundary;
- immutable candidate-plan authority and first-writer evidence store;
- cleanup-only action-job, approval, and MiniAgent request foundations;
- the passive plan-orchestration audit and its no-Qdrant/no-executor boundary.

The observer reuses the existing downstream `QdrantCollectionEvidence` record from `steps/common/clean_memory.py`. It does not modify `cli/clean_memory.py`, `steps/common/clean_memory.py`, or any prior seam's source or test files.

## Current Source Findings

### Reusable contracts and patterns

- `steps/common/clean_memory.py` defines `QdrantCollectionEvidence` (lines 125-136), `ResolvedCleanupScope` (lines 148-158), and canonical target ordering.
- `cli/clean_memory.py` (lines 480-501) defines `_resolve_qdrant` which projects `qdrant.host` and the four collection names.
- `cli/clean_memory_filesystem.py` defines the standard public API pattern, import-purity checks, and configuration digest revalidation.

### Helpers rejected for direct reuse

| Surface | Reason it cannot implement this observer |
| --- | --- |
| `scripts/qdrant/prepare_clean_slate.py` | Line 111-122 implements a `get_qdrant_collections(host)` function using `urllib.request.urlopen`, but it is an execution script containing DELETE collection calls, lacks import purity (lines 11-16), and does not map failures to fail-closed structures. |
| `steps/common/qdrant_client.py` | The client implements a single-collection instance, contains mutation/creation methods (`ensure_collection`, `upsert`, `set_payload`), and does not return the combined four-collection evidence structure. |
| `tests/unit/test_qdrant_query_authority.py` | Tests single-collection `QdrantClient` queries and stubs network calls (lines 20-53), but is not a passive, multi-collection observer. |

## Sibling Pattern Comparison

| Sibling Observer | Public API Surface | Import-Purity Pattern | Fail-closed Pattern | RED Coverage / Test Pattern |
| --- | --- | --- | --- | --- |
| **Filesystem** (`cli/clean_memory_filesystem.py`) | `FILESYSTEM_OBSERVATION_SCHEMA`<br>`FilesystemObservationError`<br>`FilesystemObservation`<br>`observe_filesystem` | Pure; imports only `ResolvedPlanConfiguration` and `FilesystemTargetEvidence`. OS checks at call time. | Raises `FilesystemObservationError` for critical OS/boundary errors. Target absence (`exists=False`) is returned in records, not thrown. | Synthesizes temporary directories/canaries, runs negative-mutant validations. |
| **Protected Boundary** (`cli/clean_memory_protected_boundary.py`) | `PROTECTED_BOUNDARY_IDENTITY_SCHEMA`<br>`ProtectedBoundaryObservationError`<br>`observe_protected_boundaries` | Pure; imports only other local projection/evidence types. | Raises `ProtectedBoundaryObservationError` for boundary redirections, missing required members, races, or sharing violations. | Mocks pin/membership projections, simulates races/mutations. |
| **External Pin** (`cli/clean_memory_external_pin.py`) | `EXTERNAL_PIN_EVIDENCE_SCHEMA`<br>`ExternalPinReaderError`<br>`ExternalPinEvidence`<br>`read_external_pin` | Pure; imports program locator and reader identity from `steps.common`. | Raises `ExternalPinReaderError` for platform/security/pin mismatch, missing pin, or races. | Simulates native platform calls, checks security descriptor validations. |

The filesystem observer (`cli/clean_memory_filesystem.py`) is the closest analogue for the Qdrant seam because it takes `ResolvedPlanConfiguration` as its sole input, validates the configuration digest before performing observation, and returns a structured custom observation object wrapping a tuple of target evidences.

## Selected Public Contract

`cli/clean_memory_qdrant.py` exposes exactly:

```text
QDRANT_OBSERVATION_SCHEMA
QdrantObservationError
QdrantObservation
observe_qdrant
```

Its `__all__` tuple contains those four names in that order and no others.

`QDRANT_OBSERVATION_SCHEMA` is exactly `goodq.clean-memory-qdrant-observation.v1`. The module imports only `ResolvedPlanConfiguration` from `cli.clean_memory` and `QdrantCollectionEvidence` from `steps.common.clean_memory`.

`observe_qdrant(configuration)` accepts only an instance whose exact type is `cli.clean_memory.ResolvedPlanConfiguration`. It rejects subclasses, mappings, paths, endpoint overrides, noncanonical or tampered projection bytes, and digest mismatch before contacting loopback.

`QdrantObservation` is frozen and contains only:

```text
schema
configuration_scope_sha256
qdrant_endpoint
qdrant_collections
```

`qdrant_collections` is an immutable tuple of the existing frozen `QdrantCollectionEvidence` type. The result contains no timestamp, status narrative, partial flag, or raw exception.

`QdrantObservationError` is a `RuntimeError` with one read-only `.code` attribute. Its code is limited to `invalid_configuration` or `observation_failed`. Service-level unreachable states, timeouts, and missing collections do not raise exceptions, but are instead returned as `exists=False` records.

## Exact Evidence Semantics

The four collection names are derived from the configuration projection:
- `goodq_text_{epoch_id}` (role: `text`)
- `goodq_clip_{epoch_id}` (role: `clip`)
- `goodq_dino_{epoch_id}` (role: `dino`)
- `goodq_audio_{epoch_id}` (role: `audio`)

Transport is strictly loopback HTTP REST on the port projected by `qdrant.port` (default `6333`).
The pinned `qdrant-client` version in `requirements-baseline-lock.txt` is `1.17.1` (and `environment-baseline-lock.yml` line 29). The active installed version in `goodq_core` conda environment is `1.18.0`.

## Do-Not-Repeat Confirmation

| Rule | Verdict | Justification |
| --- | --- | --- |
| Do not fold Qdrant observation into the existing composition helper in `cli/clean_memory.py` | **SAFE** | The Qdrant observer will reside in a new isolated module `cli/clean_memory_qdrant.py` (ROADMAP line 1423). |
| Do not create a second composition module | **SAFE** | The observer only collects passive evidence and does not compose or authenticate protected boundaries (ROADMAP line 1424). |
| Do not export any helper or error from a prior seam's module | **SAFE** | Only the four new symbols are exported via `__all__` from `cli/clean_memory_qdrant.py` (ROADMAP line 1424). |
| Do not add command, approval, job, token, or cleanup capability | **SAFE** | The seam is strictly read-only and passive, performing no operations outside of count/config queries (ROADMAP line 1425). |
| Do not contact live Qdrant, ProgramData, a real pin/manifest, or any configured data | **SAFE** | This is a read-only audit checkpoint. No live Qdrant or data access is performed during the audit, and the implementation tests will use mock connections (ROADMAP line 1426). |

## Next Bounded Mission

Implement the fail-closed Qdrant observer seam in `cli/clean_memory_qdrant.py` and `tests/unit/test_clean_memory_qdrant.py` under the approved v1 contract. Do not implement scope assembly, planning/persistence, command parsing, approval, jobs/tokens, process control, or cleanup.
