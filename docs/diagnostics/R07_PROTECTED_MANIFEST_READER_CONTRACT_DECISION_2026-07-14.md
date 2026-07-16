<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# R-07 Protected-Manifest Reader Contract Decision

## Outcome

Authorize one later two-file RED/GREEN seam for the Windows protected-manifest
reader. Every shared prerequisite is already checkpointed; the reader may now
compose those public authorities without copying or widening them.

The later changed-file census is exactly:

1. add `cli/clean_memory_protected_manifest.py`; and
2. add `tests/unit/test_clean_memory_protected_manifest.py`.

No existing production or test file is part of that implementation seam.
Configuration, external-pin evidence, canonical manifest validation, protected
membership, held-handle transport, Windows security mechanics, and shared
reader identity remain unchanged regression authorities.

This decision does not implement the reader, observe a live Windows object, or
authorize enrollment, publication, rotation, recovery, membership composition,
protected-member observation, Qdrant access, planning, approval, or cleanup.

## Governing Invariant

The reader authenticates exactly one complete byte string obtained from one
held, no-follow manifest handle. It accepts those bytes only when all of these
independent bindings agree:

- exact authenticated configuration selects the logical route;
- held identity and complete parent membership prove the physical route;
- direct external-pin evidence authorizes the byte digest and enrolled reader;
- the selected candidate-root and manifest security policies are observed;
- the shared reader-identity policy accepts the retained mandatory-policy token;
- the direct byte digest matches the external pin before decoding or parsing;
  and
- the shared canonical validator accepts the identical bytes exactly once.

The reader observes and returns evidence only. Exact input types do not prove
production provenance. A later production planning edge must invoke
`read_external_pin()` and `read_protected_manifest()` directly and retain both
outputs through authenticated composition.

## No-Repeat Result

Keep these completed authorities closed:

- configuration v1 and candidate-root topology;
- external-pin routing, thirteen-error reader, evidence schema, enrollment
  binding, route policy, race fences, and cleanup;
- canonical protected-manifest parsing and protected-membership projection;
- held no-follow traversal, physical identities, parent enumeration, bounded
  same-handle reads, snapshots, streams, and descriptor transport;
- projection-neutral Windows token, descriptor, mapping, and bounded denial
  mechanics;
- the shared ordinary-reader policy and frozen v1 identity digest; and
- the selected candidate-root and fixed-manifest security policy.

The new module must not import private helpers from another module, add a second
manifest parser or reader-identity projector, inspect opaque handle internals,
reopen a descendant by pathname, call `hash_file()`, read environment variables,
or import protected-membership composition.

## Exact Public Contract

The new module exports exactly:

```python
PROTECTED_MANIFEST_EVIDENCE_SCHEMA = (
    "goodq.clean-memory-protected-manifest-evidence.v1"
)

__all__ = (
    "PROTECTED_MANIFEST_EVIDENCE_SCHEMA",
    "ProtectedManifestReaderError",
    "ProtectedManifestEvidence",
    "read_protected_manifest",
)
```

The reader signature is exactly:

```python
def read_protected_manifest(
    configuration: ResolvedPlanConfiguration,
    *,
    external_pin_evidence: ExternalPinEvidence,
) -> ProtectedManifestEvidence:
    ...
```

There is no caller-supplied path, byte string, digest, backend, policy, token,
descriptor, route list, or dependency-injection argument.

## Direct Input Fence

Input authentication occurs before platform or native work, in this order.

### Configuration

Require `type(configuration) is ResolvedPlanConfiguration`. Snapshot its exact
private canonical JSON and public digest. Reader-local validation must prove:

- private projection is exact `str` and digest is exact lowercase SHA-256;
- recomputed SHA-256 of the exact UTF-8 projection equals the public digest;
- JSON is canonical, duplicate-free, finite, NFC, and the exact configuration
  v1 shape;
- `schema` is `goodq.clean-memory-configuration.v1`;
- `path_flavor` is `windows`;
- the logical storage and data roots are canonical local Windows paths;
- `data_root == storage_root / GoodQ_Data`; and
- `candidate_evidence_root == data_root / control / clean_memory`.

Validate only the fields consumed by this reader. Do not copy the complete
configuration resolver or import another consumer's private validator.

Any initial failure is `invalid_configuration`. Any change to the captured
private projection or digest after initial acceptance is `observation_raced`.

### External pin evidence

Next require `type(external_pin_evidence) is ExternalPinEvidence`. Snapshot its
exact private canonical bytes and public digest. Reader-local validation must
prove:

- private projection is exact `bytes` and digest is exact lowercase SHA-256;
- recomputed SHA-256 equals `external_pin_evidence_sha256`;
- the projection is canonical duplicate-free JSON with the exact ten keys;
- schema, source schema, source identifier, and platform equal the frozen
  external-pin values;
- every physical identity has the frozen Windows identity shape;
- `manifest_sha256`, `enrolled_reader_identity_sha256`, and
  `security_policy_sha256` are exact lowercase SHA-256 values; and
- anchor, three dedicated directories, and pin file have the required object
  kinds and are physically distinct.

Do not import the external reader's private validator. Any initial failure is
`invalid_external_pin_evidence`. Any later private-byte or digest change is
`observation_raced`.

`invalid_configuration` precedes `invalid_external_pin_evidence`; both precede
all platform and capability checks.

## Immutable Evidence Boundary

`ProtectedManifestEvidence` follows the existing projection-object pattern:

```python
@dataclass(frozen=True, init=False)
class ProtectedManifestEvidence:
    _manifest_bytes: bytes = field(repr=False)
    _projection_bytes: bytes = field(repr=False)
    protected_manifest_evidence_sha256: str

    @property
    def manifest_bytes(self) -> bytes:
        ...

    @property
    def projection(self) -> dict[str, Any]:
        ...
```

Direct construction fails. A private classmethod constructs the object only
after the operation and cleanup succeed. `manifest_bytes` returns the retained
immutable exact same-handle bytes needed by the later frozen membership API.
Those bytes can contain protected paths, so they are excluded from `repr`, the
canonical evidence projection, logs, errors, and report serialization. The
property is an in-process composition capability, not a display surface.

`projection` returns a newly detached mapping on every access. The evidence
digest is lowercase SHA-256 of the exact private canonical compact sorted-key
UTF-8 JSON projection and is not embedded inside that projection.

The canonical projection contains exactly these nine keys:

```text
anchor_identity
configuration_scope_sha256
external_pin_evidence_sha256
manifest_file_identity
manifest_sha256
platform
route_directory_identities
schema
security_policy_sha256
```

Their meanings are exact:

- `schema`: `PROTECTED_MANIFEST_EVIDENCE_SCHEMA`;
- `platform`: `windows`;
- `configuration_scope_sha256`: the direct configuration digest;
- `external_pin_evidence_sha256`: the direct pin-evidence digest;
- `manifest_sha256`: SHA-256 of the exact retained manifest bytes;
- `anchor_identity`: the held fixed-volume root identity;
- `route_directory_identities`: every held directory opened after the anchor,
  in traversal order through `candidate_evidence_root`;
- `manifest_file_identity`: the held fixed regular-file child identity; and
- `security_policy_sha256`: the private policy-evidence digest defined below.

Every physical identity is exactly the five-key
`goodq.windows-file-identity.v1` projection. The anchor and all route entries
are directories; the manifest identity is a regular file. Every identity is on
the anchor volume and every physical identity is distinct.

The evidence does not repeat `enrolled_reader_identity_sha256`: the direct
external-evidence digest already binds it. It does not repeat the fixed child
name: the evidence schema and imported canonical-manifest child constant own
that invariant. It does not expose paths, handles, token or SID records,
descriptors, ACEs, native errors, or the validator's detached manifest.

## Route Cardinality

The route list is configuration-derived, not fixed at four entries. Let `n` be
the number of canonical `storage_root` components after the drive prefix. The
list contains:

1. every cumulative storage-root component;
2. `GoodQ_Data`;
3. `control`; and
4. `clean_memory`.

Therefore its exact per-call length is `n + 3`, its minimum is four, and its
last element is always the candidate-root identity. A separate candidate-root
field would be redundant.

Configuration v1 currently selects no protocol-level path-component-count cap.
The reader receives no caller-supplied route list: it derives one finite list
from the already-authenticated canonical configuration string. This decision
therefore approves exact configuration-derived cardinality without inventing a
reader-only maximum that would contradict accepted configuration v1. Any later
configuration resource bound is inherited without changing this public API.

## Private Security-Policy Digest

The reader owns one private canonical policy projection with schema
`goodq.clean-memory-protected-manifest-security-policy.v1`. It has exactly three
keys: `candidate_evidence_root`, `manifest_file`, and `schema`.

Each governed-object value contains exactly:

```text
dacl
dacl_revision
denied_access_checks
descriptor_control
mandatory_label
owner_sid
physical_identity
primary_group_sid
role
```

The `dacl` is the accepted ordered ACE vector. Each ACE records exact lowercase
hex `flags` and `mask`, numeric `sid`, and fixed textual `type`.
`mandatory_label` contains exact ACL revision and its single ACE in the same
form, with type `system_mandatory_label`. Each denial record contains the fixed
right `name`, lowercase-hex `raw_mask`, lowercase-hex `mapped_mask`, and
`denied: true`, in the exact policy order. `physical_identity` is the matching
held-object identity.

The private projection contains the already-selected exact candidate and
manifest descriptor policies and denial sets; it does not create another
policy. Its compact canonical UTF-8 SHA-256 is the public
`security_policy_sha256`. Raw policy data never enters the public evidence
projection.

## Dependency And Ownership Graph

The reader may import only these public authorities:

```text
cli.clean_memory
    ResolvedPlanConfiguration, CONFIGURATION_SCHEMA

cli.clean_memory_external_pin
    ExternalPinEvidence, EXTERNAL_PIN_EVIDENCE_SCHEMA

steps.common.clean_memory_protected_manifest
    canonical schema/child/size constants, result type, validator

steps.common.clean_memory_windows_reader_identity
    reader validation/error/digest functions

steps.common.windows_held_handle
    public backend/error/entry/snapshot types

steps.common.windows_security_mechanics
    public profiles, errors, observations, sessions, binding, ABI verification
```

It must not import `cli.clean_memory_protected_membership`, filesystem
observation, candidate planning/storage, Qdrant, MiniAgent, jobs, approvals, or
cleanup execution. No `steps.common` module imports `cli`.

The reader locally owns only consumed-input authentication, route selection,
selected descriptor/access policy, manifest byte authentication, outward error
translation, evidence construction, and operation cleanup coordination.

## Exact Lifecycle And First-Failure Order

The later reader must preserve this order:

1. authenticate direct configuration;
2. authenticate direct external-pin evidence;
3. require Windows and Windows-flavor input;
4. verify and bind shared security capability, then construct only the
   `security_read_label` held-handle backend;
5. resolve `SeChangeNotifyPrivilege`, open one mandatory-policy token session,
   apply shared identity validation, and compare its frozen v1 digest directly
   with the pin's enrolled-reader digest;
6. enter the backend, open only the fixed-volume anchor by path, prove fixed
   NTFS/ReFS and open-by-ID support, and walk every projected component by
   complete parent enumeration and `open_by_id`;
7. read, parse, and validate the candidate-root `0x17` descriptor and every
   selected denial result before selecting the fixed child;
8. select one non-reparse regular child with link count one, one unnamed stream,
   and stable metadata;
9. read, parse, and validate its `0x17` descriptor and denial results;
10. require initial size in `1..PROTECTED_MANIFEST_MAX_BYTES`;
11. issue one `read_file_bounded` call with `initial_size + 1`, require EOF and
    exact initial length, and immediately require an equal resnapshot;
12. hash those exact bytes and compare with the direct external-pin digest;
13. only after equality, invoke `validate_protected_manifest()` exactly once on
    the identical bytes object with `path_flavor="windows"`, require the exact
    result type, and cross-check its digest;
14. recheck both direct inputs, the full effective token, both exact descriptor
    byte strings, static policy, denial results, every held snapshot, and every
    complete parent enumeration;
15. revalidate the shared reader-identity digest and both direct inputs once
    more, then construct the evidence candidate;
16. close every resource in its selected ownership order; and
17. return evidence only when operation and cleanup both succeeded.

Digest mismatch always precedes every UTF-8, JSON, schema, and parser error.
Initial malformed versus unsupported native structure follows the existing
security-mechanics classification; a post-acceptance change is a race.

## Closed Outward Error Table

`ProtectedManifestReaderError` is a `RuntimeError` with one immutable `.code`.
It accepts only these sixteen code/message pairs:

| Code | Fixed path-free message |
| --- | --- |
| `invalid_configuration` | `Clean-memory protected manifest configuration is invalid` |
| `invalid_external_pin_evidence` | `Clean-memory protected manifest external pin evidence is invalid` |
| `unsupported_platform` | `Clean-memory protected manifest reading is unsupported` |
| `unsupported_filesystem` | `Clean-memory protected manifest storage is unsupported` |
| `unsupported_security` | `Clean-memory protected manifest security inspection is unsupported` |
| `untrusted_reader` | `Clean-memory protected manifest reader is not authorized` |
| `security_policy_mismatch` | `Clean-memory protected manifest security policy is invalid` |
| `manifest_missing` | `Clean-memory protected manifest is missing` |
| `malformed_manifest` | `Clean-memory protected manifest payload is invalid` |
| `manifest_digest_mismatch` | `Clean-memory protected manifest digest does not match the external pin` |
| `redirected_boundary` | `Clean-memory protected manifest boundary is redirected` |
| `unexpected_entry_type` | `Clean-memory protected manifest entry type is unsupported` |
| `duplicate_identity` | `Clean-memory protected manifest identity is ambiguous` |
| `sharing_conflict` | `Clean-memory protected manifest is not quiescent` |
| `observation_raced` | `Clean-memory protected manifest changed during observation` |
| `observation_failed` | `Clean-memory protected manifest observation failed` |

Missing required route components and the fixed child share
`manifest_missing`. Zero or over-limit initial size and canonical-validator
rejection are `malformed_manifest`. Stable digest inequality is
`manifest_digest_mismatch`.

Shared failures translate exactly:

- unsupported platform/filesystem and held-handle public codes retain their
  matching reader code;
- initial thread token or shared identity-policy rejection is
  `untrusted_reader`;
- a thread token or token change during recheck is `observation_raced`;
- unavailable ABI or a structurally valid but unselected descriptor form is
  `unsupported_security`;
- malformed descriptor/native output or impossible internal result is
  `observation_failed`;
- initially wrong owner, group, control, ACL, label, ACE, trustee, mask, flag,
  or denial result is `security_policy_mismatch`; and
- any accepted input, token, descriptor byte, policy result, snapshot, stream,
  or parent enumeration that later changes is `observation_raced`.

No raw exception, path, SID, descriptor, Win32 code/message, handle, or manifest
content may appear in the public error graph.

## Cleanup And Control-Flow Contract

Access-check scopes close immediately and exactly once. Descriptor-native
allocations remain owned by the shared descriptor reader. Transient comparison
tokens remain owned by shared token observation. Backend exit attempts every
held-handle close in strict reverse acquisition order; the retained token
session closes after backend exit.

An ordinary operation failure remains primary. The first sanitized cleanup
failure becomes cause only when the primary has no cause, otherwise context;
all remaining cleanup is still attempted. Cleanup-only failure becomes
`observation_failed` and prevents evidence. No cleanup is retried.

`KeyboardInterrupt`, `SystemExit`, and `GeneratorExit` remain the identical
primary objects with their original tracebacks after complete cleanup. Any
linked cleanup nodes are sanitized reader errors. No partial evidence escapes.

## Focused RED Matrix

Before GREEN, the exact two-file seam must demonstrate RED for:

1. absent exact four-export module, function signature, and init-disabled
   evidence object;
2. exact-type configuration and pin evidence; canonical private payloads,
   digest/shape forgery, initial precedence, and final mutation races;
3. import purity and platform/security preflight before backend construction;
4. mandatory-policy baseline token, shared validation, direct enrolled-digest
   comparison, full-token rechecks, and consumer-owned error translation;
5. one-component and multi-component storage roots with exact `n + 3` route
   cardinality, anchor-to-leaf ordering, candidate root last, and no independent
   protocol cap;
6. missing, extra, reordered, duplicated, substituted, redirected, cross-volume,
   wrong-kind, or changed route identities and parent memberships;
7. exact candidate and manifest descriptor policies, labels, denial order,
   mapped masks, immediate scope closure, and byte/result rechecks;
8. fixed child, link/stream/type/size fences, one same-handle size-plus-one read,
   EOF, exact size, and immediate resnapshot;
9. pin mismatch before parser invocation, one validator call with the identical
   bytes object, exact result type, and returned-digest equality;
10. exact nine-key path-free evidence, detached projection, immutable retained
    bytes, route completeness, private policy digest, and evidence digest;
11. all sixteen fixed errors, complete sanitized exception-chain privacy,
    first-failure precedence, reverse cleanup, control-flow preservation, and no
    partial evidence; and
12. static containment forbidding duplicate parser, identity projector, token,
    descriptor, held-handle, path reopen, environment, dynamic capability,
    membership, filesystem, Qdrant, planning, approval, or cleanup authority.

## Verification Gate

Run the new reader suite first. Then preserve the unchanged 1,422-test authority
union and add every newly collected reader node. The zero-drop baselines are:

- shared reader identity: 65;
- external pin: 499;
- Windows security mechanics: 254;
- Windows held handle: 167;
- clean-memory filesystem: 46;
- canonical validator plus protected membership: 205; and
- configuration/candidate remainder: 186.

Also require exact two-file compilation and diff census, exact public exports
and signature, import/AST/dependency gates, semantic-drift and banned-token
checks, and two independent current-byte reviews. The exact native `0xb014`
enrollment and `CandidatePlanStore` compatibility witness remains a separate
deployment/integration gate; synthetic reader tests may not claim it.

## Reconciled Review Result

Three independent read-only audits traced API ownership, lifecycle/error
precedence, and evidence/digest parity. Their one initial disagreement was
resolved against the earlier composition and security contracts: the evidence
must retain the complete held route, not only the policy-governed endpoint.
Their initial four-directory assumption was then corrected against configuration
v1: four is the minimum, while exact cardinality is authenticated `n + 3`.

No prerequisite remains open for the isolated two-file RED/GREEN checkpoint.

## Audit Boundary

This decision read repository source, tests, contracts, checkpoints, and the
sole roadmap only. It did not read or change a live token, ACL, descriptor,
configured or protected root, manifest, pin, service, GoodQ data, Qdrant store,
evidence store, job, MiniAgent, approval, or cleanup target.
