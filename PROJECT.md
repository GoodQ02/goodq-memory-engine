<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# Active bounded mission

Roadmap item: R-07 — audit only the fixed-child protected-manifest reader
boundary.

## Outcome

Select the exact manifest-reader contract before code. The reader must receive
the direct exact `ExternalPinEvidence` obtained by production orchestration,
acquire only `protected-boundaries.json` beneath the projected candidate
evidence root, hash the exact bytes read from the same held handle, compare that
digest with the direct pin evidence before manifest parsing, and validate those
same bytes as canonical before returning them. ProgramData locator/recheck
ownership remains a separate later audit and must not enter this reader seam.

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
- Candidate-plan authority and immutable storage are complete injected cores;
  they are not production reader or orchestration authority.

## Governing evidence

- `docs/diagnostics/R07_PROTECTED_AUTHORITY_SOURCE_DECISION_2026-07-13.md`;
- `docs/diagnostics/R07_PROTECTED_AUTHORITY_SEMANTICS_DECISION_2026-07-13.md`;
- `docs/diagnostics/R07_PROTECTED_MEMBERSHIP_PROJECTION_CHECKPOINT_2026-07-13.md`;
- `docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_READER_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_AUTHENTICATED_PROTECTED_MEMBERSHIP_COMPOSITION_AUDIT_2026-07-14.md`;
- `docs/releases/ROADMAP.md`.

## Governing invariant

The external pin authorizes only the exact canonical manifest bytes matching its
digest. Configuration is routing, not membership authorization. The future
production plan edge must invoke both readers itself, authenticate those exact
bytes before parsing, reject lexical and physical pin/member overlap, and accept
no caller-built evidence. Target filesystem evidence is separate plan pre-state.

## Exact audit seam

Audit only the future pair:

- `cli/clean_memory_protected_manifest.py`; and
- `tests/unit/test_clean_memory_protected_manifest.py`.

The audit must select exact input/output types, direct exact pin-evidence
binding, fixed-child traversal, bounded same-handle byte acquisition, canonical
manifest validation, manifest identity and race fences, reader-owned
digest-mismatch precedence, and closed path-free errors. Do not create either
file until those choices are frozen and independently reviewed.

## Boundaries

- Do not implement the manifest reader, locator, protected observer, or
  composition during this audit.
- Do not modify the completed configuration, filesystem observer, membership,
  pin reader, held-handle backend, candidate plan, or their tests.
- Do not add enrollment, publication, rotation, recovery, Qdrant observation,
  runnable planning, approval, or cleanup execution.
- Do not expose or log ProgramData, member paths, physical identities, SIDs,
  tokens, descriptors, ACL material, or raw operating-system errors.
- Do not inspect or alter live ProgramData, a pin, token, ACL, configured root,
  manifest, protected member, service, GoodQ data, Qdrant, evidence store, job,
  MiniAgent, or cleanup target.
- Do not change dependency, service, firewall, environment, or runtime state.

## Completion gate

Produce one reviewed decision that fixes the manifest-reader API, direct-output
digest bindings, pin-first and reader-owned mismatch-before-parser order, finite
failure precedence, same-handle race fences, import direction, and focused RED
matrix. Prove by source search that no equivalent manifest reader already
exists. Update the sole roadmap and checkpoint the audit before any code. Audit
the ProgramData locator/recheck as a separate later seam.
