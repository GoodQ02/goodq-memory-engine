<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-15 -->

# R-07 Protected-Boundary Observer Checkpoint

## Outcome

The selected Windows-only protected-boundary physical observer is implemented
and privately checkpointed in two source commits:

```text
9e225655 feat(clean-memory): add protected-boundary observer
636f4bfd fix(clean-memory): protect observer error code deletion
```

The observer accepts only exact authenticated membership and external-pin
evidence, derives the five pin-chain identities internally, observes the full
18-role protected boundary membership through one held-handle context, and
returns the existing `ProtectedBoundaryEvidence` tuple. It adds no new wrapper,
digest, path authority, configuration lookup, persistence, planning, approval,
or cleanup capability.

## Closed Contract

- The module exposes exactly the selected schema constant, closed error type,
  and keyword-only observer function.
- Direct inputs are authenticated before backend construction and rechecked at
  both global fences. Self-consistent forged projections fail closed.
- Only distinct drive roots are opened by pathname. Every descendant is reached
  through complete held-parent enumeration and open-by-ID traversal.
- Exact canonical prefixes reuse one retained physical identity. Distinct paths
  may not alias, and every root, ancestor, parent, and present member is checked
  against all five pin-chain identities.
- Stable absence requires two equal complete parent-membership snapshots. A
  missing initial ancestor or required child is distinct from a post-acceptance
  race.
- Every snapshot and enumeration is rechecked before all 18 envelopes are
  constructed atomically. No partial tuple can return.
- Errors use the selected twelve-code path-free taxonomy. Code/message state,
  linked context, cleanup precedence, and control-flow behavior are immutable
  and sanitized, including deletion and deletion/rebinding attempts.
- Output contains only canonical selected identity evidence. It contains no raw
  path, name, native handle, descriptor, SID, OS error, or pin identity.

## TDD And Review Hardening

The first focused RED failed because the production module did not exist. The
direct matrix then grew before implementation and closed the selected happy,
negative-mutant, race, collision, privacy, and lifecycle contract.

Two later review findings were also corrected test-first:

- an unselected 4,096-byte configured-member path cap was exposed by one RED
  and deleted outright, with no replacement cap; and
- the final root-level review proved `_code` could be deleted and rebound on a
  closed error. Two direct RED mutants reproduced the bypass before deletion
  protection was added.

The implementer-side current-byte review returned `Approved` after five bounded
coverage corrections. The independent root-level final review then found the
error-deletion bypass, re-reviewed the corrected commits, and returned
specification compliant with no critical, important, or minor finding.

## Fresh Verification

All commands used the explicit `goodq_core` interpreter and synthetic or fake
held-handle surfaces only.

| Gate | Result |
| --- | ---: |
| Focused protected-boundary observer suite | 184 passed |
| Protected-membership suite | 102 passed |
| External-pin suite | 499 passed |
| Protected-manifest suite | 148 passed |
| Windows held-handle suite | 167 passed |
| Candidate-plan authority suite | 55 passed |
| Bounded dependency-safe authority union | 1,155 passed |
| Prior expanded authority gate plus observer | 1,807 passed |
| Exact two-file Python compilation | passed |
| Committed source census | exactly 2 files |
| Committed diff and whitespace checks | passed |
| Implementer-side independent review | APPROVED |
| Root-level independent final review | APPROVED |

The first expanded 1,807-test run retained one known synthetic temporary-tree
`observation_raced` receipt: 1,806 passed and one unchanged filesystem-observer
determinism witness failed. The unmodified retry passed all 1,807 tests. This is
the same fail-closed synthetic temporary-filesystem event retained by the prior
locator checkpoint; it was neither suppressed nor patched.

The reviewed committed SHA-256 hashes are:

```text
cli/clean_memory_protected_boundary.py
4F4F58FF44534B4CFEA1C961E62A56BDFFF05C656D74C52B92241B34B38C1F98

tests/unit/test_clean_memory_protected_boundary.py
AE7F69EF28A5F6FD08A9456FF64EB55F6E5519E0D749824121658187DFC05C30
```

## Independent Test-Isolation Debt

The literal external-pin-before-protected-manifest order exposes a pre-existing
test isolation defect. One external-pin import-purity test replaces its module
in `sys.modules` and does not restore the original object, so the later
protected-manifest exact-type check can compare two different class objects.
The minimal reproducer excludes both new observer files, and each affected file
passes independently. The observer did not cause the defect and did not widen
scope to repair it. The sole roadmap tracks it as R-18-F3.

## Evidence Boundary

No test, implementation, or review read or mutated live ProgramData, a
production pin or manifest, token, ACL, descriptor, configured or protected
root, service, GoodQ data, Qdrant store, evidence store, job, MiniAgent,
approval state, cleanup target, or cleanup operation.

## No-Repeat Boundary

Do not recreate the observer, add a second physical-evidence wrapper, accept
caller paths or identities, reopen descendants by pathname, copy private reader
or locator helpers, weaken exact-type or final-fence checks, or fold cleanup
target/Qdrant/planning authority into this module.

## Next Bounded Mission

Run one read-only no-repeat ownership and contract re-audit of authenticated
protected-membership composition now that the manifest reader, shared
ProgramData locator, and protected-boundary observer are checkpointed. Select an
exact implementation allowlist and direct-output/final-recheck/error-precedence
contract before composition code is authorized.

Qdrant observation, runnable planning, approval, jobs/tokens, and cleanup remain
closed.
