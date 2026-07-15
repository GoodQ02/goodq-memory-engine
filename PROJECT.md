<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-15 -->

# Active bounded mission

Roadmap item: R-07 — re-audit authenticated protected-membership composition
after the protected-boundary observer checkpoint.

## Outcome

Run one read-only no-repeat ownership and contract re-audit of authenticated
protected-membership composition. Reconcile the now-complete direct outputs,
final rechecks, failure precedence, and exact future implementation allowlist.
Do not implement composition during this mission.

## Completed work — do not repeat

- Configuration projection, immutable candidate planning, cleanup-target
  filesystem observation, protected-manifest validation, protected-membership
  projection, shared held-handle traversal, Windows security mechanics, reader
  identity, external-pin reading, authenticated protected-manifest reading, and
  the shared ProgramData locator are checkpointed.
- `9e225655` adds the selected Windows protected-boundary observer and exact
  synthetic regression authority.
- `636f4bfd` closes the final observer error-code deletion/rebinding bypass
  without changing its public API or authority.
- The final observer source has exactly three exports, accepts only direct
  membership and external-pin evidence, derives five pin identities internally,
  retains all physical evidence through one final fence, and returns the
  existing 18-role `ProtectedBoundaryEvidence` tuple.
- Fresh verification passed 184 focused tests, a 1,155-test bounded union, and
  the expanded 1,807-test zero-drop gate on an unchanged retry. Independent
  final review returned specification compliant with no remaining finding.
- The pre-existing external-pin module-reload test-isolation defect has a
  separate roadmap owner. Do not weaken production exact-type checks or repair
  that test inside this mission.

## Governing invariant

Authenticated protected authority must compose only from exact direct outputs
whose canonical bytes, digests, physical evidence, and final rechecks remain
mutually consistent through return. Cleanup-target filesystem evidence is later
candidate-plan pre-state and may not authenticate protected membership.

The composition boundary may bind existing selected evidence; it may not create
a second locator, reader, observer, identity wrapper, manifest parser, path
authority, or physical-discovery fallback.

## Exact audit seam

1. reread the existing authenticated-composition audit against current public
   source and tests;
2. trace every proposed direct input and final recheck to one completed owner;
3. reconcile digest binding, exact-type checks, lifecycle/control precedence,
   cleanup, privacy, and no-partial-return behavior;
4. select one exact future source/test allowlist and RED matrix; and
5. obtain independent current-byte ownership and contract reviews before any
   implementation is authorized.

## Governing evidence

- `docs/diagnostics/R07_AUTHENTICATED_PROTECTED_MEMBERSHIP_COMPOSITION_AUDIT_2026-07-14.md`;
- `docs/diagnostics/R07_PROTECTED_BOUNDARY_OBSERVER_CHECKPOINT_2026-07-15.md`;
- `docs/diagnostics/R07_PROTECTED_BOUNDARY_OBSERVER_CONTRACT_DECISION_2026-07-15.md`;
- `docs/diagnostics/R07_WINDOWS_PROGRAM_DATA_LOCATOR_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_PROTECTED_MANIFEST_READER_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_READER_CHECKPOINT_2026-07-14.md`;
- their closed source/tests; and
- `docs/releases/ROADMAP.md`.

## Boundaries

- Work only in `.worktrees/r05-api-authority` on
  `codex/r05-api-authority`.
- This mission is read-only except for its bounded diagnostic/mission/roadmap
  documentation checkpoint.
- Do not modify completed production modules or focused tests.
- Do not inspect or mutate live ProgramData, a token, ACL, descriptor,
  configured or protected root, manifest, pin, service, GoodQ data, Qdrant,
  evidence store, job, MiniAgent, approval, or cleanup target.
- Do not implement or contact Qdrant, build runnable planning, persist evidence,
  issue approval, create jobs/tokens, or execute cleanup.

## Completion gate

1. current source traces name every direct output and owner without duplicate
   authority;
2. the selected composition lifecycle is non-circular and closes every input,
   digest, final-recheck, failure-precedence, privacy, and cleanup seam;
3. one exact future implementation allowlist and direct RED matrix are frozen;
4. at least two independent current-byte reviews return clean; and
5. the audit and roadmap are checkpointed before composition code begins.
