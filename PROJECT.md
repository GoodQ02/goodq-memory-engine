<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# Active bounded mission

Roadmap item: R-07 — add label-aware held-handle descriptor transport.

## Outcome

Use RED/GREEN/refactor to add one opt-in `security_read_label` profile to the
shared Windows held-handle backend. Preserve the existing `observation` and
`security_read` profiles exactly. Prove the new profile requests owner, group,
DACL, and mandatory-label information (`0x17`) from the same held descendant
handle and returns one detached self-relative descriptor.

This mission changes exactly two files:

- `steps/common/windows_held_handle.py`; and
- `tests/unit/test_windows_held_handle.py`.

## Completed work — do not repeat

- Configuration, filesystem observation, structural membership, held-handle
  traversal, bounded reads, and owner/group/DACL transport are checkpointed.
- The no-argument external-pin reader and its lifecycle hardening are
  checkpointed and remain unchanged.
- `41e56c74` checkpoints the pure canonical protected-manifest validator and
  membership delegation with 437 approved authority tests.
- `docs/diagnostics/R07_PROTECTED_MANIFEST_SECURITY_POLICY_DECISION_2026-07-14.md`
  selects the exact manifest policy and received two adversarial `READY`
  reviews. It explicitly treats `0x17` as filtered transport, detached
  `AccessCheck` as mutation-denial-only, and native opens/reads as positive
  access evidence.
- Candidate-plan authority and storage are completed injected cores. Their
  positive ACL compatibility is a later test-owned integration witness, not
  this transport seam.

## Governing invariant

The new profile may expand only the security-information request carried by the
existing held-handle descriptor-read capability. It may not reinterpret the
descriptor, token, route, manifest, pin, or policy. Existing callers must retain
their exact profile acceptance, open rights, request mask `0x7`, errors,
cleanup, and public surface.

## Exact TDD seam

RED must first prove:

- `security_read_label` is absent;
- the selected profile must request exact `GetSecurityInfo` mask `0x17` rather
  than the existing `0x7`; and
- the existing Windows-native temporary-file descriptor witness does not yet
  exercise the label-aware profile.

GREEN may then make only these behavioral additions:

- accept exact opt-in profile `security_read_label`;
- load the same existing security native surface for either security profile;
- add `READ_CONTROL` only to descendant opens for either security profile;
- permit `read_security_descriptor()` only on a security-readable descendant
  handle owned by the same backend;
- request exact mask `0x17` for `security_read_label` and preserve exact mask
  `0x7` for `security_read`;
- retain the existing detached-copy validation, self-relative control check,
  size bound, allocation cleanup, failure precedence, close behavior, and error
  vocabulary; and
- add a Windows-only pytest-owned temporary-file witness that executes the real
  held-handle `GetSecurityInfo(..., 0x17)` path and proves detached valid
  self-relative transport without reading or changing configured/production
  ACLs.

Refactor only after RED and GREEN evidence is captured. Keep the public class,
method signatures, exception type, and module import surface exact.

## Boundaries

- Do not add token inspection, descriptor parsing, DACL policy, generic mapping,
  `AccessCheck`, manifest-reader logic, or evidence schemas.
- Do not implement or exercise enrollment, publication, rotation, recovery,
  candidate-plan persistence, approval, or cleanup.
- Do not inspect or mutate any live token, ACL, configured/protected root,
  manifest, pin, service, GoodQ data, Qdrant, evidence store, job, MiniAgent, or
  cleanup target.
- Do not query a full SACL or request `ACCESS_SYSTEM_SECURITY`.
- Do not modify the external-pin reader or copy any of its private symbols.
- Do not change dependencies, services, firewall, environment, or runtime state.

## Completion gate

Checkpoint only after the focused held-handle suite passes on Windows, including
the native temporary-file witness; existing `observation` and `security_read`
behavior is frozen by exact parity tests; the external-pin regression suite and
shared-source boundary pass; compilation and diff gates are clean; and an
independent current-byte review returns `READY`. The exact `0xb014` policy form,
CandidatePlanStore ACL compatibility, security mechanics, and physical manifest
reader remain closed after this checkpoint.
