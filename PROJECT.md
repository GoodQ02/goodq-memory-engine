<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# Active bounded mission

Roadmap item: R-07 — audit only canonical protected-manifest validator
ownership and extraction parity.

## Outcome

Select one pure projection-neutral canonical protected-manifest validator so
the completed structural membership projection and future physical manifest
reader cannot become competing parsing authorities. Audit only ownership,
exact API/import direction, extraction/adaptation scope, error parity, and the
focused RED matrix. Do not modify membership, create the shared validator, or
begin manifest-reader code until the decision is independently reviewed and
checkpointed.

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
- `docs/releases/ROADMAP.md`.

## Governing invariant

One exact canonical byte/schema validator must own protected-manifest meaning.
The structural membership projection and future physical reader may compose
that authority but may not copy, privately import, or independently reinterpret
it. Extracting validation must preserve the completed membership public API,
canonical projection bytes, detached digest, accepted/rejected corpus, and
stable outward failures.

## Exact audit seam

Audit the private canonical JSON and `_manifest_members()` responsibilities in
`cli/clean_memory_protected_membership.py`, their focused tests, and repository
import/call sites. Select the smallest shared pure module/API and later source/
test adaptation set that preserves membership parity while allowing the future
reader to validate the same authenticated bytes. Prove no equivalent public
validator already exists. Do not create or move code during this audit.

## Boundaries

- Do not implement the validator extraction, manifest reader, security policy
  or mechanics, locator, protected observer, or composition.
- Do not modify the completed configuration, filesystem observer, membership,
  shared held-handle backend, pin reader, candidate plan, or their tests.
- Do not add enrollment, publication, rotation, recovery, Qdrant observation,
  runnable planning, approval, or cleanup execution.
- Do not expose or log ProgramData, member paths, physical identities, SIDs,
  tokens, descriptors, ACL material, or raw operating-system errors.
- Do not inspect or alter live ProgramData, a pin, token, ACL, configured root,
  manifest, protected member, service, GoodQ data, Qdrant, evidence store, job,
  MiniAgent, or cleanup target.
- Do not change dependency, service, firewall, environment, or runtime state.

## Completion gate

Produce one reviewed decision selecting exact validator ownership, API, input/
output/error contracts, import direction, extraction/adaptation files, parity
oracle, and focused RED matrix. Prove no equivalent shared validator exists and
that the completed membership projection need not change its public output.
Update the sole roadmap and checkpoint the audit before code. Keep manifest
security policy as a separate mandatory blocker before reader implementation.
