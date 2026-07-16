<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-15 -->

# R-07 Protected-Boundary Observer Contract Decision

## Outcome

Implement one separate Windows protected-boundary observer after this decision
is checkpointed. The exact implementation seam is only:

- `cli/clean_memory_protected_boundary.py`; and
- `tests/unit/test_clean_memory_protected_boundary.py`.

The observer consumes the exact completed protected-membership and external-pin
evidence types, observes every protected parent and member through the shared
held-handle backend, rejects physical aliases and collisions with all five
direct pin-chain identities, and atomically returns the existing candidate-plan
`ProtectedBoundaryEvidence` tuple.

It does not read a pin or manifest, resolve ProgramData, load configuration,
observe cleanup targets or Qdrant, compose authenticated authority, build or
persist a plan, issue approval, create a job or token, or execute cleanup.

## No-Repeat Result

Three independent read-only ownership, lifecycle, and contract traces agree
that no production protected-member physical observer exists. Keep these
completed authorities closed:

- `cli.clean_memory_filesystem` owns epoch-root and cleanup-target pre-state;
- `cli.clean_memory_protected_membership` owns the structural 18-role membership
  projection and digest without filesystem authority;
- `cli.clean_memory_external_pin` owns fixed trust-root reading, security policy,
  and the five path-free pin-chain identities;
- `cli.clean_memory_protected_manifest` owns authenticated fixed-child manifest
  reading and mismatch-before-parser behavior;
- `steps.common.clean_memory_windows_program_data_locator` owns only the actual
  ProgramData Known Folder acquisition and fixed lexical route;
- `steps.common.windows_held_handle` owns the projection-neutral no-follow,
  open-by-ID, snapshot, enumeration, and handle-lifecycle mechanics; and
- `steps.common.clean_memory.ProtectedBoundaryEvidence` and candidate-plan
  validation remain the selected output carrier and defense-in-depth boundary.

Do not add protected roles to `observe_filesystem()`, import or copy private
reader/observer helpers, widen either reader or locator API, or create another
identity renderer, locator, wrapper evidence type, or candidate-plan schema.

## Governing Invariant

Authenticated membership proves logical protected scope, not physical state.
The observer must retain every accepted parent and member handle until one
global final fence, reject every cross-path physical alias and every collision
with the direct pin chain, and return no partial evidence.

Lexical pin/member separation remains composition-owned and occurs before this
observer. Physical exclusion remains observer-owned. Neither check substitutes
for the other.

The selected canonical path-free parent/object identity envelopes are internal
planning evidence and are permitted in `ProtectedBoundaryEvidence.identity_json`.
No path, raw name, native handle, pointer, descriptor, SID, operating-system
error detail, unselected identity detail, or raw member content may enter an
error, log, representation, API/display projection, or durable record outside
the selected candidate-plan authority.

## Exact Public Surface

The module exports exactly:

```python
__all__ = (
    "PROTECTED_BOUNDARY_IDENTITY_SCHEMA",
    "ProtectedBoundaryObservationError",
    "observe_protected_boundaries",
)

PROTECTED_BOUNDARY_IDENTITY_SCHEMA = (
    "goodq.clean-memory-protected-boundary-identity.v1"
)

def observe_protected_boundaries(
    protected_membership: ProtectedMembershipProjection,
    *,
    external_pin_evidence: ExternalPinEvidence,
) -> tuple[ProtectedBoundaryEvidence, ...]:
    ...
```

The function requires exact direct types, not subclasses. It accepts no path,
configuration, manifest evidence or bytes, locator, digest, raw identity,
backend, override, or cleanup-target evidence. Passing exact
`ExternalPinEvidence` rather than a caller-built identity tuple lets the
observer authenticate and recheck the direct output while deriving the five
physical exclusions internally.

The module is import-pure and standard-library-only apart from the four exact
project dependencies named by the signature and shared backend. Native
capability construction occurs only inside the public call after both inputs
pass preflight.

## Closed Error Contract

`ProtectedBoundaryObservationError` is an immutable, path-free `RuntimeError`
with only these codes and messages:

| Code | Exact message |
| --- | --- |
| `invalid_protected_membership` | `Clean-memory protected membership is invalid` |
| `invalid_external_pin_evidence` | `Clean-memory protected-boundary external pin evidence is invalid` |
| `unsupported_platform` | `Clean-memory protected-boundary observation is unsupported` |
| `unsupported_filesystem` | `Clean-memory protected-boundary storage is unsupported` |
| `member_missing` | `Clean-memory protected-boundary member is missing` |
| `redirected_boundary` | `Clean-memory protected boundary is redirected` |
| `unexpected_entry_type` | `Clean-memory protected-boundary entry type is unsupported` |
| `duplicate_identity` | `Clean-memory protected-boundary identity is ambiguous` |
| `pin_chain_collision` | `Clean-memory protected boundary collides with the external pin chain` |
| `sharing_conflict` | `Clean-memory protected boundary is not quiescent` |
| `observation_raced` | `Clean-memory protected boundary changed during observation` |
| `observation_failed` | `Clean-memory protected-boundary observation failed` |

Unknown codes are rejected. Public causes and contexts contain only closed
observer errors. Native messages, paths, member IDs, comparison values, file
identities, and operating-system codes never escape.

## Direct-Input Preflight

Before constructing a backend or making any filesystem call, the observer:

1. requires the exact `ProtectedMembershipProjection` type;
2. snapshots its exact canonical private JSON and detached digest;
3. verifies canonical bytes and digest plus the exact top-level membership keys,
   schema, Windows flavor, lowercase configuration digest, fixed manifest child,
   lowercase embedded manifest digest, complete 18-role order, exact role/member
   shapes, member-ID ordering, object kinds, presence values, and canonical
   Windows path spelling consumed by traversal;
4. requires the exact `ExternalPinEvidence` type;
5. snapshots its exact canonical private bytes and detached digest;
6. verifies its exact ten-key shape, schema, source ID/source schema, Windows
   platform, outer digest, lowercase manifest digest, lowercase enrolled-reader
   identity digest, lowercase security-policy digest, and five-identity census;
7. verifies the exact canonical object shape and kind of every pin identity; and
8. requires one directory anchor, three ordered directory identities, and one
   regular-file pin identity, all on one volume, valid for NTFS or ReFS, nonzero,
   and pairwise distinct.

Malformed or changed membership maps to `invalid_protected_membership`.
Malformed or changed pin evidence maps to `invalid_external_pin_evidence` until
physical observation begins. The observer does not import private validation
helpers from either reader.

The preflight rejects forged exact instances even when a caller recomputes the
outer canonical digest after changing an embedded authority field. Comparing
the membership manifest digest with the external pin manifest digest remains a
composition-owned authentication gate and is not duplicated here.

## Windows Observation Lifecycle

Windows is the only enabled v1 platform. POSIX remains closed until a separate
descriptor-relative filesystem and identity audit.

1. Create one `WindowsHeldHandleBackend(access_profile="observation")` for the
   complete call and enter one context.
2. Process roles in the immutable membership order and members in member-ID
   order.
3. For each distinct drive, open only its root by pathname, verify fixed
   NTFS/ReFS and open-by-ID support, snapshot it, and retain the handle.
4. Traverse every descendant by complete enumeration of the held parent,
   canonical NFC/casefold comparison, `open_by_id()` through the retained volume
   root, and a same-handle snapshot against the selected entry.
5. Reject ambiguous comparison names, missing ancestors, reparses, devices,
   wrong kinds, cross-volume state, zero identities, unsupported storage,
   delete-pending state, invalid stream shape, or multiply linked regular files.
6. Cache each canonical path and its held handle/snapshot. Reuse one exact
   canonical prefix; never reopen the same path by name.
7. For each final member, retain the immediate parent identity, complete parent
   membership, and the SHA-256 of the NFC-casefolded final-component bytes.
8. For a present member, retain and snapshot the exact held object. For an
   absent final member, fail if presence is `required`; otherwise retain the
   held parent and the initial complete membership proof. A missing ancestor is
   always failure, never structural absence.
9. Apply the initial global alias and pin-chain exclusions below.
10. Recheck both exact direct inputs.
11. Resnapshot every held drive root, ancestor, immediate parent, and present
    member; re-enumerate every retained parent completely; require exact initial
    snapshot and membership equality; require absent children to remain absent;
    and rerun every alias and pin-chain exclusion.
12. Recheck both direct inputs once more after the physical fence.
13. Construct all 18 composite envelopes in memory, in role order, without
    exposing a partial tuple.
14. Exit the backend context. Only after every handle closes cleanly may the
    complete tuple return.

Failure precedence is phase-specific:

| Phase | Condition | Outward code |
| --- | --- | --- |
| input preflight | malformed or changed membership | `invalid_protected_membership` |
| input preflight | malformed or changed pin evidence | `invalid_external_pin_evidence` |
| startup/initial traversal | known held-handle code | same selected observer code |
| startup/initial traversal | unknown ordinary failure | `observation_failed` |
| final physical fence | explicit input, snapshot, membership, absence, replacement, disappearance, alias-set, or pin-set mismatch | `observation_raced` |
| final physical fence | held-handle `observation_raced`, `redirected_boundary`, `unexpected_entry_type`, `duplicate_identity`, `sharing_conflict`, or `unsupported_filesystem` after the corresponding object was initially accepted | `observation_raced` |
| final physical fence | held-handle `observation_failed` without positive change evidence | `observation_failed` |
| backend context exit | any normalized close failure with no operation primary | `observation_failed` |

The observer never converts a final-fence failure merely because it occurs late:
positive state/change evidence is required for `observation_raced`, while an
unclassified native/query failure remains `observation_failed`.

An ancestor missing during initial traversal and a required final child absent
at its first complete parent enumeration both map to `member_missing`. A member
or ancestor accepted initially and missing at the final fence maps to
`observation_raced`.

## Physical Identity And Exclusion Rules

Windows physical identity is the canonical
`(volume_serial, file_id_kind, file_id)` tuple. Object kind remains bound in the
selected `goodq.windows-file-identity.v1` projection.

- The same canonical path must retain the same identity through the final
  fence.
- Different canonical paths resolving to the same physical identity fail
  `duplicate_identity`.
- Reuse of one exact canonical prefix is allowed. This preserves intentional
  containment such as a protected member serving as another member's ancestor.
- One present member object identity cannot identify two logical members.
- The pair `(immediate_parent_identity, child_comparison_sha256)` is unique
  across all present and absent members. The same parent with different child
  hashes is valid.
- A regular-file member with a link count other than one fails
  `duplicate_identity`.
- Every retained drive root, traversed ancestor, immediate parent, and present
  member identity is compared with all five external-pin identities. Equality
  fails `pin_chain_collision`.
- Redirects, junctions, devices, and mount aliases fail at boundary validation;
  they are never accepted as alias evidence.

The observer reruns these sets from final held snapshots before return.
Candidate-plan duplicate composite-envelope validation remains defense in depth
and never replaces member-level physical exclusion.

## Stable Absence And Composite Evidence

Each role returns one existing `ProtectedBoundaryEvidence`:

```text
role = <role>
logical_id = protected:<role>
identity_json = <canonical role envelope>
```

The canonical role envelope uses the already-selected
`goodq.clean-memory-protected-boundary-identity.v1` schema, binds the exact
`protected_membership_scope_sha256`, and contains members ordered by member ID.
Each member has exactly:

- `absence`;
- `child_comparison_sha256`;
- `logical_id` as `protected:<role>:<member_id>`;
- `member_id`;
- `object_identity`;
- `object_kind`;
- `parent_identity`; and
- `state`.

Present members have `state="present"`, a canonical object identity, and null
`absence`. Absent members have `state="absent"`, null `object_identity`, and an
exact `goodq.clean-memory-stable-absence.v1` object containing equal
`before_membership_sha256` and `after_membership_sha256`.

Each complete parent membership snapshot contains only the selected
`goodq.clean-memory-parent-membership.v1` schema and sorted entries with:

- `comparison_name_sha256`;
- `entry_identity` using
  `goodq.clean-memory-directory-entry-identity.v1`; and
- `entry_kind` as `directory`, `regular_file`, `redirect`, `device`, or `other`.

Comparison hashes use NFC-casefolded UTF-8 final-component bytes. Entry identity
contains platform, volume serial, file-ID kind, and file ID but no object kind.
Duplicate comparison-name hashes fail. The before and final canonical membership
bytes must be equal before their equal digests may be emitted. No raw path or
name enters the envelope.

## Cleanup And Control-Flow Precedence

The shared backend owns reservation-before-open, reverse in-place close,
attempt-all cleanup, and primary-exception preservation. The observer translates
and sanitizes the complete backend graph and does not return until context exit
succeeds.

- Cleanup-only failure is normalized by the frozen shared backend to ordinary
  `observation_failed` and prevents evidence, including a close callback that
  originally raised a control-flow exception.
- An ordinary operation failure remains primary over ordinary cleanup failures.
- Operation `KeyboardInterrupt`, `SystemExit`, or `GeneratorExit` preserves
  exact identity and traceback over every backend-normalized cleanup failure.
- Unknown `BaseException` values fail closed without raw linked state.

All cleanup attempts still run. Error-graph handling is bounded, cycle-aware,
path-free, and allocation-independent at the terminal fallback.

## Exact RED Matrix

Before production code, focused tests must witness failure for:

1. absent module, exact three exports, exact signature, and import purity;
2. wrong/subclass/detached inputs, malformed canonical bytes or digests, exact
   top-level and nested key censuses, malformed embedded configuration/manifest/
   reader/security digests, self-consistent forged instances with recomputed
   outer digests, input mutation at every fence, and backend construction before
   complete preflight;
3. exact Windows schema/source/five-identity pin census, NTFS/ReFS forms,
   pairwise pin duplicates, wrong kinds, zero IDs, and cross-volume pin state;
4. exact 18-role/member ordering and rejected caller path, identity, locator,
   configuration, manifest, backend, digest, or override authority;
5. drive-root-only pathname opens, held enumeration, open-by-ID descendants,
   common-prefix reuse, multi-drive routes, and no private/dynamic imports;
6. required/present and allow-absent quadrants, initial ancestor and required
   child absence mapping to `member_missing`, two complete absence snapshots,
   and post-acceptance appearance/disappearance or same-count replacement
   mapping to `observation_raced`;
7. casefold ambiguity, wrong kind, redirect, device, cross-volume state, zero
   identity, delete-pending state, stream violation, and regular-file hardlink;
8. different-path same-identity aliases, duplicate present member identities,
   duplicate present/absent parent-child keys, accepted shared-parent prefixes,
   and intentional exact-path containment;
9. every retained route/member identity against each of the five pin identities;
10. every snapshot and parent-membership field at the final race fence;
11. exactly 18 canonical `ProtectedBoundaryEvidence` values, exact present and
    absent key sets, independently calculated hashes, membership-digest binding,
    immutable path-free output, and unchanged candidate-plan compatibility;
12. first/middle/final traversal or construction failure returning no partial
    evidence;
13. all twelve exact error code/message pairs, unknown-code rejection, code
    immutability, and bounded cause/context sanitization against paths, names,
    member IDs, comparison values, identities, native messages, and OS codes at
    startup, operation, and final-fence phases;
14. cleanup-only normalization, ordinary-primary precedence, all three
    operation control-flow primaries, multiple cleanup failures, cycles, depth
    bounds, allocation failure, reverse close, and attempt-all behavior; and
15. absence of pin/manifest/locator rereads, cleanup-target observation, Qdrant,
    planning, persistence, approval, jobs/tokens, MiniAgent, or cleanup mutation.

Negative-mutant tests must fail if production adds descendant pathname opens,
normalization/search/fallback, reparse following, partial enumeration, omitted
pin or final fences, path/name serialization, private reader/locator imports,
caller-built identity authority, partial return, or swallowed control flow.
They must also fail if any raw exception node survives public sanitization or if
a final-fence state mismatch is downgraded to `observation_failed`.

## Verification Gate

Run sequentially with the explicit `goodq_core` interpreter:

- the focused protected-boundary observer suite;
- the unchanged protected-membership, external-pin, protected-manifest,
  held-handle, filesystem-observer, candidate-plan, ProgramData-locator,
  reader-identity, manifest-validator, and security-mechanics suites;
- a zero-drop union against the last 1,623-test expanded authority gate, with
  the new exact total recorded;
- exact two-file compilation, public API/import/dependency containment, staged
  source census, staged diff, and whitespace checks;
- documentation authority, semantic drift, banned-token, dependency-drift, and
  generated-index gates; and
- at least two independent current-byte contract, lifecycle, and test-oracle
  reviews after all corrections.

Implementation and documentation are checkpointed separately. Only after the
two-file source checkpoint passes may R-07 advance to authenticated composition.
Qdrant observation, runnable planning, approval, and cleanup remain closed.

## Evidence Boundary

This decision read repository source, tests, contracts, and checkpoint evidence
only. It did not resolve or inspect live ProgramData, a production pin or
manifest, token, ACL, descriptor, configured or protected root, service, GoodQ
data, Qdrant, evidence store, job, MiniAgent, approval, or cleanup target.
