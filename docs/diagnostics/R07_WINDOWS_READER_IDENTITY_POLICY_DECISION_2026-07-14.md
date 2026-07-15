<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# R-07 Windows Reader-Identity Policy Decision

## Outcome

Create one import-pure GoodQ clean-memory Windows reader-identity policy
authority before any protected-manifest reader is implemented.

The exact next implementation/parity seam is four files:

1. add `steps/common/clean_memory_windows_reader_identity.py`;
2. add `tests/unit/test_clean_memory_windows_reader_identity.py`;
3. adapt `cli/clean_memory_external_pin.py`; and
4. adapt `tests/unit/test_clean_memory_external_pin.py`.

The shared policy owns the ordinary-reader acceptance common to both physical
readers and the exact frozen v1 digest. The raw schema, projection, and
canonical preimage remain private. The protected-manifest reader remains
closed.

## Governing Invariant

Projection-neutral Windows mechanics and GoodQ reader-identity policy remain
separate authorities.

`steps.common.windows_security_mechanics` may observe and retain a normalized
`WindowsTokenSnapshot`; it must not know trusted reader values, accepted policy,
evidence schemas, consumer errors, or digest meaning. The new identity module
may interpret only an already-detached public snapshot. It must not acquire a
token, bind native functions, own a session, inspect a DACL or path, read an
environment variable, or grant cleanup authority.

Each physical reader still proves the snapshot came from its own retained
`WindowsSecuritySession`, brackets its work with full snapshot equality, owns
its route and object policy, and translates shared policy failures at its own
boundary. Exact snapshot type alone is not provenance or authorization.

## No-Repeat Result

Keep these completed seams closed:

- projection-neutral token and descriptor mechanics at `0827193a`;
- external-pin routing, held handles, exact DACL/enrollment policy, access
  checks, evidence, thirteen outward errors, and cleanup order;
- held-handle traversal, bounded reads, and `0x7` / `0x17` descriptor transport;
- canonical protected-manifest validation and structural membership;
- the selected protected-manifest security policy;
- configuration, filesystem observation, candidate planning, and storage; and
- enrollment, publication, rotation, recovery, Qdrant observation, approval,
  and cleanup execution.

Do not move identity policy into Windows mechanics. Do not import a private
external-pin helper from a future reader. Do not copy the v1 schema or projector
into another consumer. Do not create a public raw projector or preimage API.

## Current Ownership and Call Graph

The only production owner today is `cli.clean_memory_external_pin`:

1. the shared mechanics session opens the exact base token profile;
2. `_intrinsically_validate_token()` applies ordinary-reader policy before any
   storage traversal;
3. the external reader proves enrolled DACL SID equality, route and object
   policy, access denial, pin content, and all race fences;
4. `_final_authority_recheck()` completes;
5. `_reader_identity_projection()` builds the v1 object from the original
   immutable baseline snapshot;
6. canonical UTF-8 JSON is hashed with SHA-256; and
7. only the lowercase digest enters
   `ExternalPinEvidence.enrolled_reader_identity_sha256`.

No other production source computes or consumes the v1 digest. The planned
second consumer is the future protected-manifest reader. Its selected security
policy requires it to apply the same ordinary-reader policy to its own
mandatory-policy snapshot and compare the exact unchanged v1 digest with the
direct external-pin evidence before manifest decoding or parsing.

## Why Extraction Happens Before Reader RED

Leaving the policy permanently external-pin private would force the future
reader to import a private helper from a physical CLI reader, duplicate the
acceptance and byte grammar, or widen the completed external reader into shared
authority. All three create a second authority or reverse dependency direction.

Deferring extraction into the physical-reader checkpoint would combine a new
reader, a new policy owner, mandatory-profile behavior, external adaptation,
error translation, digest comparison, and reader lifecycle in one rollback
boundary. That would make RED ambiguous and violate the one-seam rule.

The selected four-file checkpoint introduces the shared owner and removes the
private production owner together. It does not begin the protected-manifest
reader.

## Dependency Direction

The dependency direction is one-way:

```text
cli.clean_memory_external_pin
    -> steps.common.clean_memory_windows_reader_identity
        -> steps.common.windows_security_mechanics

future cli.clean_memory_protected_manifest
    -> steps.common.clean_memory_windows_reader_identity
    -> steps.common.clean_memory_protected_manifest
    -> steps.common.windows_security_mechanics
```

No `steps.common` module imports `cli`. The new module imports no held-handle,
filesystem, external-pin, manifest-reader, service, environment, or native
capability owner.

## Exact Public Surface

The new module has exactly three exports:

```python
__all__ = (
    "CleanMemoryWindowsReaderIdentityError",
    "validate_clean_memory_windows_reader_identity",
    "clean_memory_windows_reader_identity_sha256",
)

def validate_clean_memory_windows_reader_identity(
    snapshot: WindowsTokenSnapshot,
    *,
    profile: str,
    change_notify_luid: int,
) -> None:
    ...

def clean_memory_windows_reader_identity_sha256(
    snapshot: WindowsTokenSnapshot,
    *,
    profile: str,
    change_notify_luid: int,
) -> str:
    ...
```

`CleanMemoryWindowsReaderIdentityError` is a `ValueError` subclass with the
exact fixed path-free message
`Clean-memory Windows reader identity is not authorized`. It contains no
snapshot, SID, privilege, path, handle, or native detail.

The argument contract is exact:

- `type(snapshot) is WindowsTokenSnapshot`;
- `type(profile) is str`, equal to the imported mechanics constant
  `WINDOWS_TOKEN_PROFILE_BASE` or
  `WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY`;
- `type(change_notify_luid) is int`, rejecting `bool` and subclasses; and
- `change_notify_luid` is in `0..2**64 - 1`.

Caller-shape errors use closed path-free `TypeError` or `ValueError`. A
structurally valid mechanics observation that fails ordinary-reader policy uses
only `CleanMemoryWindowsReaderIdentityError`.

Validation returns `None`. The digest function always applies the identical
validation before hashing and returns exactly 64 lowercase hexadecimal
characters. It returns no result object, projection, bytes, schema constant, or
detached preimage.

## Shared Ordinary-Reader Policy

The shared module accepts only:

- process-primary token statistics;
- exact Default or Limited elevation type, never Full;
- not elevated;
- exact medium-integrity SID `S-1-16-8192`;
- no restricting SID, AppContainer, or UIAccess state;
- `TokenHasRestrictions` false for Default and true for Limited;
- an Administrators group, when present, that is deny-only and not enabled;
- no enabled privilege except the exact supplied
  `SeChangeNotifyPrivilege` LUID; and
- a mandatory-policy field consistent with the selected profile.

The base profile requires `mandatory_policy is None`. The mandatory-policy
profile requires an exact integer `1` or `3`; `None`, `0`, `2`, booleans, and
subclasses are rejected. The module does not require
`SeChangeNotifyPrivilege` to be present or enabled; it preserves the existing
rule that only another enabled privilege is rejected.

This extraction must not strengthen the accepted domain. Apart from the exact
base/mandatory profile fence, validation applies only the current intrinsic
predicates above. It must not reject an otherwise valid mechanics snapshot
because of token ID, authentication ID, modified ID, expiration time,
`dynamic_charged`, `dynamic_available`, mechanics-owned count consistency,
integrity-record attributes, the particular ordinary user SID, any
non-Administrator group attributes, disabled privilege identities or
attributes, or the presence/absence/enabled state of
`SeChangeNotifyPrivilege`. User-SID enrollment remains consumer-owned.

The module does not own thread/process token acquisition, source provenance,
enrolled-SID equality, DACL/label/access policy, consumer phase, evidence
schema, or outward reader errors.

## Frozen v1 Digest Contract

The private v1 projection remains exactly
`goodq.clean-memory-windows-reader-identity.v1` and contains the existing
fields and fixed values only. Canonicalization remains:

```python
json.dumps(
    projection,
    ensure_ascii=False,
    allow_nan=False,
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")
```

The output is lowercase `hashlib.sha256(...).hexdigest()`.

The projection preserves current binary-SID and unsigned-LUID ordering,
numeric SID text, lowercase 8/16-hex fields, signed-decimal expiration,
decimal record counts, fixed `process` / `primary` / `null` claims, and the
Default versus Limited distinction.

It continues to omit:

- `mandatory_policy`;
- token-statistics `dynamic_charged` and `dynamic_available`;
- integrity-record attributes;
- raw SID/token bytes; and
- every path, handle, DACL, role, manifest, and consumer field.

Otherwise-identical accepted snapshots with mandatory policy `None`, `1`, or
`3` therefore have identical v1 digests even though full snapshot equality
distinguishes them. Mandatory policy and profile are omitted. The
`change_notify_luid` argument is not independently serialized; accepted
snapshot privilege records, including their LUID values, remain part of the
frozen v1 preimage.

## External-Adapter Parity

The external adapter must preserve this order:

1. acquire the exact base-profile snapshot and resolved change-notify LUID;
2. call shared validation before any storage traversal;
3. retain every existing route, descriptor, access, content, race, and cleanup
   operation unchanged;
4. complete `_final_authority_recheck()`;
5. call the shared digest on the same immutable baseline, with the same profile
   and LUID;
6. construct exact existing evidence; and
7. perform existing cleanup in the same order.

`CleanMemoryWindowsReaderIdentityError` from either early validation or late
digest revalidation translates exactly to the existing external
`untrusted_reader`. Caller-shape `TypeError` / `ValueError` and every unexpected
shared failure translate to sanitized external `observation_failed`. No shared
exception escapes, and neither translation changes existing primary/cleanup
precedence. Late digest revalidation is deterministic over the same frozen
snapshot and adds no I/O or native action.

The external source must no longer define `_intrinsically_validate_token`,
`_reader_identity_projection`, the v1 schema literal, or another production
canonicalization path for reader identity. Its public API and evidence remain
unchanged.

## Focused RED Matrix

Before production movement, RED must prove:

1. the new module and three-symbol public API are absent;
2. the external source still contains the two private policy authorities;
3. no public import-pure owner can validate both mechanics profiles and produce
   the exact existing digest;
4. exact function signatures, keyword-only arguments, type/range fences, and
   fixed path-free policy error;
5. no import-time or invocation-time native, filesystem, environment, network,
   subprocess, logging, output, or `sys.path` mutation;
6. no `cli`, held-handle, external-pin, manifest-reader, or capability-owner
   dependency;
7. exact Default and Limited golden digest vectors and every current accepted
   group/privilege variant;
8. every current intrinsic token rejection before a digest is returned;
9. base `None`, mandatory `1` / `3`, equal cross-profile digest, unequal full
   snapshots, and mandatory `None` / `0` / `2` rejection;
10. the projector precondition cannot be bypassed by Full elevation,
    impersonation token type, wrong integrity, or other rejected state;
11. exact private field grammar, canonical JSON options, ordering, formatting,
    and lowercase SHA-256 through independent expected vectors;
12. no raw projection, canonical bytes, schema constant, or constructible
    result escapes the public surface;
13. external validation occurs before storage, digest occurs only after final
    authority recheck, and the same snapshot/profile/LUID are used;
14. exact external evidence bytes/digests, four exports, thirteen errors, base
    17-call token profile, 39/5/19 operation counts, race brackets, failure
    precedence, and cleanup order remain unchanged; and
15. AST containment proves the external source has no private duplicate policy
    and the shared module acquires no native capability.

The 499-test external suite remains a zero-drop integration baseline. Direct
policy tests are additive; do not delete external parity or lifecycle coverage
merely because the same accepted/rejected values gain direct shared-policy
tests.

## Verification Gate

Run sequentially through the explicit `goodq_core` interpreter:

- the direct new policy suite;
- the adapted external suite with a 499-node zero-drop receipt;
- the unchanged 254-test mechanics suite;
- the historical 167-test held-handle suite;
- filesystem, canonical-validator, and membership parity;
- the expanded clean-memory authority union;
- exact four-file compilation and diff containment;
- import/dependency/AST containment;
- semantic-drift, banned-token, and dependency-drift gates; and
- at least two independent current-byte `READY` reviews.

Checkpoint implementation and documentation separately. Only after the policy
checkpoint may the roadmap advance to a read-only protected-manifest reader
public-contract and error/input-fence decision. Reader source, enrollment,
publication, composition, planning, approval, and cleanup remain closed.

## Rejected Alternatives

- **Keep external-private permanently:** forces private CLI import, duplicate
  production policy, or external API widening when the second consumer arrives.
- **Defer until physical reader implementation:** mixes policy extraction,
  external adaptation, reader lifecycle, and digest comparison in one rollback
  boundary.
- **Move into Windows mechanics:** violates projection-neutral ownership.
- **Projection-only helper:** exposes a function whose current output is safe
  only after acceptance and leaves the common acceptance matrix duplicated.
- **Public result/projection/schema:** exposes data neither consumer needs and
  violates the existing digest-only boundary.
- **Import external private helpers:** reverses dependency direction and makes a
  physical CLI reader shared authority.
- **Compatibility aliases:** preserve a second callable production authority.

## Independent Review and Evidence Boundary

Three bounded read-only audits independently traced the current call graph,
exact v1 bytes, mechanics/policy split, future manifest requirements, and
rollback options. All selected the separate import-pure policy seam. Two
follow-up reviews returned `READY` on the exact three-symbol API, profile
fences, early-validation/late-digest timing, and digest-only public boundary.

This audit read only repository source, tests, current checkpoint evidence, and
the sole roadmap. It did not inspect or mutate a live token, ACL, descriptor,
configured or protected root, pin, manifest, service, GoodQ data, Qdrant store,
evidence store, job, MiniAgent, or cleanup target.
