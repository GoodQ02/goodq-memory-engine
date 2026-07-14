<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# Active bounded mission

Roadmap item: R-07 — select the protected-manifest security policy.

## Outcome

Run only a decision-only, read-only no-repeat audit of manifest-chain security
authority. Select the exact governed ancestor/file set, descriptor/DACL and
owner/group/ACE policy, effective reader token state, write/create/replace/delete
authority, and exact object-specific access masks that must succeed or fail.
Identify only the projection-neutral security mechanics the selected policy
proves necessary. Do not implement mechanics or the physical reader during this
mission.

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
- `41e56c74` and
  `docs/diagnostics/R07_PROTECTED_MANIFEST_VALIDATOR_EXTRACTION_CHECKPOINT_2026-07-14.md`
  checkpoint the pure canonical validator and membership delegation with 437
  approved authority tests and an independent `READY` review.
- Candidate-plan authority and immutable storage are complete injected cores;
  they are not production reader or orchestration authority.

## Governing evidence

- `docs/diagnostics/R07_PROTECTED_AUTHORITY_SOURCE_DECISION_2026-07-13.md`;
- `docs/diagnostics/R07_PROTECTED_AUTHORITY_SEMANTICS_DECISION_2026-07-13.md`;
- `docs/diagnostics/R07_WINDOWS_SECURITY_CAPABILITY_DECISION_2026-07-13.md`;
- `docs/diagnostics/R07_WINDOWS_SECURITY_DESCRIPTOR_CHECKPOINT_2026-07-13.md`;
- `docs/diagnostics/R07_PROTECTED_MEMBERSHIP_PROJECTION_CHECKPOINT_2026-07-13.md`;
- `docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_READER_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_AUTHENTICATED_PROTECTED_MEMBERSHIP_COMPOSITION_AUDIT_2026-07-14.md`;
- `docs/diagnostics/R07_PROTECTED_MANIFEST_READER_CAPABILITY_GAP_AUDIT_2026-07-14.md`;
- `docs/diagnostics/R07_WINDOWS_BOUNDED_READ_CAPACITY_EXTENSION_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_PROTECTED_MANIFEST_VALIDATOR_EXTRACTION_DECISION_2026-07-14.md`;
- `docs/diagnostics/R07_PROTECTED_MANIFEST_VALIDATOR_EXTRACTION_CHECKPOINT_2026-07-14.md`;
- `docs/releases/ROADMAP.md`.

## Governing invariant

The future manifest reader may trust only a selected, path-free policy whose
owner, ACE, effective-token, and write-authority requirements have exact
repository evidence and failure oracles. Pin-specific reader policy cannot be
copied as manifest policy, and projection-neutral held-handle primitives cannot
interpret policy. Current validator and transport checkpoints do not authorize
the physical reader.

## Exact audit seam

The audit may read only repository source, tests, governing contracts, completed
checkpoints, and current official platform documentation needed to validate
security semantics. It must decide:

- which candidate-root ancestors and exact manifest child are policy governed;
- exact owner/group plus self-relative descriptor control, protected/non-null
  DACL, DACL revision, and ordered ACE type/flag/trustee/raw-mask expectations
  at each governed object;
- who may create, write, replace, delete, take ownership of, or change policy;
- accepted ordinary-reader token, elevation, integrity, impersonation, group,
  restriction, and privilege state;
- exact object-specific desired access masks that must succeed or fail after a
  fixed generic mapping, with no generic bits reaching effective-access checks;
  and
- the smallest genuinely projection-neutral token, descriptor-parsing,
  `MapGenericMask`, and `AccessCheck` mechanics needed by that policy.

Record one evidence-backed decision and advance the roadmap only after
independent current-byte review. Do not create tests or production mechanics in
this decision seam.

## Boundaries

- Do not inspect live ProgramData, ACLs, descriptors, tokens, pins, manifests,
  configured roots, or protected members.
- Do not implement or extract security mechanics, manifest policy code, the
  reader, locator, protected observer, or composition.
- Do not copy pin-specific policy or private external-pin reader mechanics.
- Do not modify completed configuration, validator, membership, filesystem
  observer, held-handle backend, pin reader, or candidate plan.
- Do not add enrollment, publication, rotation, recovery, Qdrant observation,
  runnable planning, approval, or cleanup execution.
- Do not expose or log ProgramData, member paths, physical identities, SIDs,
  tokens, descriptors, ACL material, or raw operating-system errors.
- Do not inspect or alter a live pin, token, ACL, configured root, manifest,
  protected member, service, GoodQ data, Qdrant, evidence store, job, MiniAgent,
  or cleanup target.
- Do not change dependency, service, firewall, environment, or runtime state.

## Completion gate

Repository and official-platform evidence must resolve every listed policy
question without borrowing authority from runtime state or the external-pin
reader. The decision must freeze the descriptor envelope, owner/group, ordered
ACE grammar, fixed generic mapping, exact per-object desired masks, and explicit
allow/deny outcomes; distinguish manifest-specific policy from genuinely
projection-neutral mechanics; define exact failure ordering and testable future
oracles; preserve the completed validator, descriptor-backend, and pin-reader
boundaries; and receive independent current-byte review. Checkpoint the decision
before selecting any security-mechanics extraction; the physical reader remains
closed.
