<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# Active bounded mission

Roadmap item: R-07 — extract projection-neutral Windows security mechanics.

## Outcome

Implement only the four-file extraction/parity seam selected by
`docs/diagnostics/R07_WINDOWS_SECURITY_MECHANICS_EXTRACTION_DECISION_2026-07-14.md`.
Move projection-neutral token, descriptor, generic-mapping, and bounded access-
check mechanics into one import-pure shared module while adapting the completed
external-pin reader in the same checkpoint.

Use RED/GREEN/refactor and preserve the external-pin public API, errors,
evidence bytes and digests, operation order, cleanup precedence, and base token
query sequence exactly. Do not create the protected-manifest reader.

## Completed work — do not repeat

- Configuration, filesystem observation, structural membership, held-handle
  traversal, bounded reads, and external-pin reader authority are checkpointed.
- `41e56c74` checkpoints the pure canonical protected-manifest validator and
  membership delegation.
- `25ae5b64` selects the exact manifest security policy: filtered descriptor,
  bounded mutation-denial checking, actual-kernel positive access, frozen v1
  pin identity digest, and explicit publication-provenance limits.
- `6b40d8e8` checkpoints exact opt-in `security_read_label` transport with
  request mask `0x17`, native Windows evidence, 644 focused regressions, and two
  independent `READY` reviews.
- `1084f8d8` checkpoints that transport evidence and advances only to the
  mechanics ownership audit.
- The read-only mechanics audit selected one four-file shared extraction. It
  rejected parser-only and token-only staging because both would reopen the
  same opaque descriptor/token/access lifetime boundary.
- Existing `security_read` remains exact owner/group/DACL transport (`0x7`).
- Candidate-plan authority and storage are completed injected cores and are not
  part of this mechanics audit.

## Governing evidence

- `docs/diagnostics/R07_PROTECTED_MANIFEST_SECURITY_POLICY_DECISION_2026-07-14.md`;
- `docs/diagnostics/R07_WINDOWS_LABEL_SECURITY_TRANSPORT_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_WINDOWS_SECURITY_MECHANICS_EXTRACTION_DECISION_2026-07-14.md`;
- `docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_READER_CHECKPOINT_2026-07-14.md`;
- `cli/clean_memory_external_pin.py`;
- `tests/unit/test_clean_memory_external_pin.py`;
- `steps/common/windows_held_handle.py`;
- `tests/unit/test_windows_held_handle.py`; and
- `docs/releases/ROADMAP.md`.

## Governing invariant

The extraction may share mechanics, never authority. The external-pin reader's
private policy, five-object grammar, v1 identity projection/digest, evidence,
errors, failure order, and no-argument API remain exact. Manifest policy belongs
only to the future manifest reader. The shared layer may own bounded native
mechanics but may not know candidate roles, fixed names, trusted SIDs, accepted
token policy, DACL sequences, expected access outcomes, or consumer errors.

## Exact implementation seam

Touch exactly:

1. add `steps/common/windows_security_mechanics.py`;
2. add `tests/unit/test_windows_security_mechanics.py`;
3. adapt `cli/clean_memory_external_pin.py`; and
4. adapt `tests/unit/test_clean_memory_external_pin.py`.

The shared module owns:

- exact Win64 token/mapping/access ABI and immutable observations;
- base and mandatory-policy token profiles, with class 27 absent from base;
- retained process-token and private duplicate ownership;
- bounded self-relative SID/ACL/ACE/DACL/mandatory-label parsing;
- one private stable descriptor allocation used for both parsing and access;
- exact file generic mapping and the closed one-mask mutation-check envelope;
- one opaque access scope per descriptor and validated denial-only results
  without accepted-outcome policy; and
- fixed path-free mechanics errors and cleanup.

The external-pin adapter retains:

- DLL load order, the exact pre-load `_GUID` size guard, Known Folder support,
  and binder invocation order;
- token acceptance, enrolled-reader and DACL policies;
- route, role, rights, expected-denial, race, and failure-order authority;
- the frozen v1 reader-identity projection and digest; and
- every outward error, evidence byte, digest, and no-argument contract.

Keep both held-handle files unchanged. Keep the frozen identity projection
private during this checkpoint; sharing that policy is a later separate seam.

## Boundaries

- Do not inspect or mutate any live token or configured/production ACL or root,
  manifest, pin, service, GoodQ data, Qdrant, evidence store, job, MiniAgent, or
  cleanup target.
- Use fake native adapters only for token, duplication, mapping, and access
  mechanics. The already-checkpointed pytest-owned temporary-file descriptor-
  transport witness is sufficient; do not add a live-token witness, query a
  full SACL, or request `ACCESS_SYSTEM_SECURITY`.
- Do not copy private external-pin policy into a shared module or manifest
  reader.
- Do not modify the held-handle backend, manifest validator, membership,
  configuration, candidate plan, or any unrelated runtime code/test.
- Do not add enrollment, publication, rotation, recovery, planning, approval,
  cleanup, dependency, service, firewall, environment, or runtime changes.

## Completion gate

Checkpoint only after the exact RED oracles fail for absent shared authority,
the selected four-file implementation passes the full decision matrix, all
existing held-handle and external-pin behavior remains exact, class 27 is proven
absent from the external-pin base profile, source containment and documentation
gates pass, and at least two independent current-byte reviews return `READY`.

The protected-manifest reader remains closed.
