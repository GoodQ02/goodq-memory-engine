<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# Active bounded mission

Roadmap item: R-07 — extend only the shared held-handle bounded-read capacity.

## Outcome

Widen only the accepted upper bound of the existing
`WindowsHeldHandleBackend.read_file_bounded()` method from 66 to `4_194_305` so
a future reader can prove EOF for a maximum-size 4,194,304-byte manifest.
Preserve the method, signature, return and EOF semantics, public surface,
adapter parity, lifecycle behavior, and the external-pin reader's exact 66-byte
request. Do not add a second read API or begin manifest-reader code.

## Completed work — do not repeat

- `a12ceb18` checkpointed the pure configuration projection.
- `e8961889` checkpointed cleanup-target filesystem observation.
- `81aafce1` checkpointed the canonical 18-role structural membership
  projection.
- `0f567557`, `73430481`, and `882dc70` checkpointed the shared held-handle,
  bounded-read, and same-handle security primitives.
- `a82cd743` and `017f0f64` checkpointed the no-argument Windows external-pin
  reader and its lifecycle hardening.
- `5c6b93ba` recorded the external-pin reader checkpoint and advanced to the
  composition audit.
- `docs/diagnostics/R07_AUTHENTICATED_PROTECTED_MEMBERSHIP_COMPOSITION_AUDIT_2026-07-14.md`
  proves that a manifest reader, protected observer, and locator handoff are
  still absent, and that target filesystem evidence belongs only to later
  cleanup-scope assembly.
- `docs/diagnostics/R07_PROTECTED_MANIFEST_READER_CAPABILITY_GAP_AUDIT_2026-07-14.md`
  proves that the reader is blocked by held-handle capacity, one canonical-
  parser ownership, and an unselected manifest security policy. It selects only
  the transport-capacity extension as the next executable seam.
- Candidate-plan authority and immutable storage are complete injected cores;
  they are not production reader or orchestration authority.

## Governing evidence

- `docs/diagnostics/R07_PROTECTED_AUTHORITY_SOURCE_DECISION_2026-07-13.md`;
- `docs/diagnostics/R07_PROTECTED_AUTHORITY_SEMANTICS_DECISION_2026-07-13.md`;
- `docs/diagnostics/R07_PROTECTED_MEMBERSHIP_PROJECTION_CHECKPOINT_2026-07-13.md`;
- `docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_READER_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_AUTHENTICATED_PROTECTED_MEMBERSHIP_COMPOSITION_AUDIT_2026-07-14.md`;
- `docs/diagnostics/R07_PROTECTED_MANIFEST_READER_CAPABILITY_GAP_AUDIT_2026-07-14.md`;
- `docs/releases/ROADMAP.md`.

## Governing invariant

The shared backend may transport bytes and detached platform evidence but must
not own manifest meaning or policy. Widening its projection-neutral capacity
must not change the external-pin protocol, and it does not make the future
manifest reader ready. Canonical-validator and manifest security authorities
remain separate blockers.

## Exact implementation seam

Modify only:

- `steps/common/windows_held_handle.py`; and
- `tests/unit/test_windows_held_handle.py`.

Change only the maximum accepted exact integer from 66 to `4_194_305`. Preserve
all existing ownership, rewind, bounded-read, EOF, error, cleanup, export, and
adapter contracts. Add focused RED coverage for exact maximum acceptance,
over-maximum pre-I/O refusal, maximum manifest EOF proof, exact-cap no-probe
behavior, and unchanged 66-byte external-pin use.

## Boundaries

- Do not implement the manifest reader, parser extraction, security policy or
  mechanics, locator, protected observer, or composition.
- Do not modify the completed configuration, filesystem observer, membership,
  pin reader, candidate plan, or their production code/tests.
- Do not add enrollment, publication, rotation, recovery, Qdrant observation,
  runnable planning, approval, or cleanup execution.
- Do not expose or log ProgramData, member paths, physical identities, SIDs,
  tokens, descriptors, ACL material, or raw operating-system errors.
- Do not inspect or alter live ProgramData, a pin, token, ACL, configured root,
  manifest, protected member, service, GoodQ data, Qdrant, evidence store, job,
  MiniAgent, or cleanup target.
- Do not change dependency, service, firewall, environment, or runtime state.

## Completion gate

Focused RED must fail before production change. Then the exact backend suite,
external-pin and filesystem-adapter regression suites, compilation, exact
public-surface checks, documentation authority/drift, banned-token, dependency,
and staged-diff gates must pass. Independent current-byte review must confirm
that only the accepted ceiling changed and the external-pin caller still asks
for exactly 66 bytes. Checkpoint before selecting the next prerequisite.
