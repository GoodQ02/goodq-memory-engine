<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-07 — extract the shared Windows held-handle backend with exact
filesystem-observer parity.

## Outcome

Extract only the already-proven Windows held-handle mechanics from the private
filesystem-observer implementation into one projection-neutral shared backend,
then adapt the observer without changing its public contract or behavior.

This mission is extraction parity only. It adds no Known Folder, token, ACL,
external-pin reader, enrollment, publication, rotation, protected observation,
authenticated selection, plan orchestration, or cleanup capability.

## Governing evidence

- candidate-plan checkpoint `c870a1cb`
- configuration projection checkpoint `a12ceb18`
- filesystem observer checkpoint `e8961889`
- protected-boundary authority audit checkpoint `f01e03a7`
- duplicate canonical-envelope guard checkpoint `4230a910`
- source/trust decision checkpoints `8bfa5d27` and `69f4a91e`
- semantics checkpoint `9328e89e`
- membership-projection checkpoint `81aafce1`
- `docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_BOUNDARY_AUDIT_2026-07-13.md`
- `docs/diagnostics/R07_PROTECTED_AUTHORITY_SOURCE_DECISION_2026-07-13.md`
- `docs/diagnostics/R07_PROTECTED_AUTHORITY_SEMANTICS_DECISION_2026-07-13.md`
- `docs/diagnostics/R07_PROTECTED_MEMBERSHIP_PROJECTION_CHECKPOINT_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Governing invariant

One proven held-handle implementation must own Windows no-follow traversal.
Extraction must preserve every current observer invariant before any security-
sensitive reader may consume the shared backend. Private imports, copied ABI
logic, or simultaneous reader behavior would create competing authority.

## Exact implementation scope

- Add `steps/common/windows_held_handle.py` with exactly the four-symbol public
  API selected by the audit.
- Add `tests/unit/test_windows_held_handle.py` and move the low-level Windows
  ABI/handle oracles without duplicating them.
- Adapt `cli/clean_memory_filesystem.py` to the public shared backend while
  retaining configuration projection, role traversal, outward identity JSON,
  evidence, and exact outward errors; the shared snapshot becomes the sole
  canonical physical-identity renderer.
- Adapt `tests/unit/test_clean_memory_filesystem.py` so observer-level behavior,
  import shape, native root-only trace, and public API remain exact.
- Use witnessed RED for the shared API/import boundary, negative volume gates,
  post-open reparse rejection, and adapter parity before GREEN.

## Boundaries

- Touch only the four selected source/test files plus checkpoint documentation
  and generated indexes.
- Do not inspect, create, enroll, publish, rotate, recover, or delete a live
  trust-root location or pin.
- Do not change ProgramData, filesystem permissions, ownership, ACLs, user or
  process tokens, services, manifests, configured roots, Qdrant, or GoodQ data.
- Do not reopen the completed configuration, membership projection, candidate
  plan, action-job, MiniAgent, or approval contracts. The filesystem observer's
  public API, evidence, outward errors, POSIX behavior, and traversal invariants
  remain closed; only private Windows backend ownership is reopened for this
  extraction.
- Do not add Known Folder, token, security-descriptor, reader, manifest
  authentication, protected-member observation, Qdrant observation, runnable
  planning, or execution behavior.

## Completion gate

The exact shared API/import and handle-lifecycle oracles, transferred low-level
tests including canonical identity rendering, retained observer pre-open/public
tests, new negative volume/post-open-reparse RED witnesses, native root-only path
trace, focused pair, full clean-memory authority union,
compilation, import purity, documentation/index/drift, banned-token, dependency,
diff, and three independent current-byte reviews pass. No live trust root,
member, token, ACL, service, or data surface is touched.
