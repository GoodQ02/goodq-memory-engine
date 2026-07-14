<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# Active bounded mission

Roadmap item: R-07 — extract one pure canonical protected-manifest validator.

## Outcome

Implement only the reviewed four-file extraction/parity seam selected by the
validator decision checkpoint. Add one standard-library-only shared manifest
validator and focused test, adapt structural membership and its existing test,
and preserve all completed public bytes, digests, failures, import purity, and
configuration behavior. Do not begin physical reader or security-policy code.

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
- `617cd32a` and
  `docs/diagnostics/R07_WINDOWS_BOUNDED_READ_CAPACITY_EXTENSION_CHECKPOINT_2026-07-14.md`
  extend only the shared bounded-read ceiling to `4_194_305`, preserve the
  external-pin reader's exact 66-byte request, and close the transport-capacity
  blocker with 664 focused regression tests.
- `docs/diagnostics/R07_PROTECTED_MANIFEST_VALIDATOR_EXTRACTION_DECISION_2026-07-14.md`
  proves no equivalent shared validator exists, selects the exact public API,
  preserves membership failure order, and limits implementation to four files.
- Candidate-plan authority and immutable storage are complete injected cores;
  they are not production reader or orchestration authority.

## Governing evidence

- `docs/diagnostics/R07_PROTECTED_AUTHORITY_SOURCE_DECISION_2026-07-13.md`;
- `docs/diagnostics/R07_PROTECTED_AUTHORITY_SEMANTICS_DECISION_2026-07-13.md`;
- `docs/diagnostics/R07_PROTECTED_MEMBERSHIP_PROJECTION_CHECKPOINT_2026-07-13.md`;
- `docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_READER_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_AUTHENTICATED_PROTECTED_MEMBERSHIP_COMPOSITION_AUDIT_2026-07-14.md`;
- `docs/diagnostics/R07_PROTECTED_MANIFEST_READER_CAPABILITY_GAP_AUDIT_2026-07-14.md`;
- `docs/diagnostics/R07_WINDOWS_BOUNDED_READ_CAPACITY_EXTENSION_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_PROTECTED_MANIFEST_VALIDATOR_EXTRACTION_DECISION_2026-07-14.md`;
- `docs/releases/ROADMAP.md`.

## Governing invariant

One exact canonical byte/schema validator owns protected-manifest meaning. The
membership adapter may retain only its pre-configuration bytes/size compatibility
fence and configuration/projection validation; it may not retain or copy
manifest parsing. Generic configuration helpers stay contract-local under the
completed membership no-repeat rule.

## Exact implementation seam

Modify only:

- new `steps/common/clean_memory_protected_manifest.py`;
- new `tests/unit/test_clean_memory_protected_manifest_validator.py`;
- `cli/clean_memory_protected_membership.py`; and
- `tests/unit/test_clean_memory_protected_membership.py`.

Use focused RED before production movement. The shared module owns the exact
six-symbol API, frozen detached result, manifest constants, canonical parser,
schema/member/path validation, and digest. Membership retains its exact public
API, configuration validation, combined-scope rules, projection, and final
mutation fence.

## Boundaries

- Do not implement the manifest reader, security policy or mechanics, locator,
  protected observer, or composition.
- Do not add a generic canonical helper module or modify completed configuration,
  filesystem observer, shared held-handle backend, pin reader, or candidate plan.
- Do not add enrollment, publication, rotation, recovery, Qdrant observation,
  runnable planning, approval, or cleanup execution.
- Do not expose or log ProgramData, member paths, physical identities, SIDs,
  tokens, descriptors, ACL material, or raw operating-system errors.
- Do not inspect or alter live ProgramData, a pin, token, ACL, configured root,
  manifest, protected member, service, GoodQ data, Qdrant, evidence store, job,
  MiniAgent, or cleanup target.
- Do not change dependency, service, firewall, environment, or runtime state.

## Completion gate

Focused RED must fail for the absent validator/API and then for the unadapted
membership ownership seam. Direct validator, existing 98-test membership,
focused pair, and the approved authority union plus new tests must pass through
`goodq_core`, along with compilation, exact imports/exports, capability-free
execution, and diff gates. Independent current-byte review must confirm exact
API/error/output parity. Checkpoint before selecting the next prerequisite;
manifest security policy remains a separate blocker before reader code.
