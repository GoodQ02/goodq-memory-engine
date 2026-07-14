<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# R-07 Protected-Manifest Validator Extraction Decision

## Outcome

Create one projection-neutral canonical protected-manifest validator before any
physical manifest reader is implemented.

The exact future implementation/parity seam is four files:

1. new `steps/common/clean_memory_protected_manifest.py`;
2. new `tests/unit/test_clean_memory_protected_manifest_validator.py`;
3. adapt `cli/clean_memory_protected_membership.py`; and
4. adapt `tests/unit/test_clean_memory_protected_membership.py`.

Do not add a generic canonical-JSON or path-validation module. The completed
membership checkpoint explicitly forbids reopening configuration-v1 merely to
share private validation helpers. Configuration/projection validation therefore
stays private to membership, while the new shared module owns all protected-
manifest interpretation. This preserves separate contract authority without
creating two manifest parsers.

The shared validator must return a frozen, init-disabled, path-free-repr result
with a fresh detached manifest view and the SHA-256 of the exact validated
bytes. Do not return a mutable nested mapping in a tuple and do not expose a
caller-buildable result constructor.

## Governing Invariant

One exact canonical byte/schema validator owns protected-manifest meaning. Both
the completed structural membership projection and the future physical reader
may consume that public authority. Neither may copy manifest parsing, import a
private validator, reinterpret schema or role policy, or accept a caller-built
validated result.

Extracting this authority must preserve the completed membership public API,
canonical projection bytes and digest, accepted/rejected corpus, path-free
errors, capability-free execution, and outward failure precedence.

## No-Equivalent Proof

Repository production census found the manifest schema, fixed child, byte
limit, role order, member policy, canonical parser, path rules, and SHA-256 only
inside `cli.clean_memory_protected_membership`. The private
`_manifest_members()` function is excluded from that module's public API and is
called only by `project_protected_membership()`.

Other JSON helpers are not equivalent:

- `steps.common.clean_memory` validates candidate-plan inputs but does not own
  manifest UTF-8, byte equality, recursive string, schema, role, member, path,
  or digest semantics;
- `cli.clean_memory_filesystem` owns configuration-projection parsing, not
  protected-manifest meaning; and
- no production caller or future reader currently consumes an equivalent
  public protected-manifest validator.

The structural membership projection is complete and must be adapted, not
replaced. The future physical reader remains absent and unauthorized.

## Selected Public Contract

The new shared module is standard-library-only and has this exact public
surface:

```python
PROTECTED_MANIFEST_SCHEMA = "goodq.clean-memory-protected-authority.v1"
PROTECTED_MANIFEST_CHILD_NAME = "protected-boundaries.json"
PROTECTED_MANIFEST_MAX_BYTES = 4_194_304
PROTECTED_MANIFEST_ROLE_ORDER = (
    "backup_root",
    "download_cache",
    "public_checkout",
    "qdrant_service_logs",
    "recovery_root",
    "reports_root",
    "repository",
    "source_media",
)

__all__ = (
    "PROTECTED_MANIFEST_SCHEMA",
    "PROTECTED_MANIFEST_CHILD_NAME",
    "PROTECTED_MANIFEST_MAX_BYTES",
    "PROTECTED_MANIFEST_ROLE_ORDER",
    "CanonicalProtectedManifest",
    "validate_protected_manifest",
)

def validate_protected_manifest(
    manifest_bytes: bytes,
    *,
    path_flavor: str,
) -> CanonicalProtectedManifest:
    ...
```

`PROTECTED_MANIFEST_ROLE_ORDER` is public because membership must verify the
configuration's unresolved-role census before manifest parsing. Deriving it
from validator output would parse the manifest too early and change existing
failure precedence.

`CanonicalProtectedManifest` is `@dataclass(frozen=True, init=False)`. It owns:

```python
_manifest_bytes: bytes = field(repr=False)
manifest_sha256: str

def __new__(cls) -> "CanonicalProtectedManifest":
    raise TypeError("CanonicalProtectedManifest cannot be constructed directly")

@property
def manifest(self) -> dict[str, Any]:
    """Return a fresh detached manifest object."""
```

The validator alone allocates a fully populated instance through an internal
`object.__new__` construction path after all checks pass. The exact immutable
bytes remain private and absent from `repr`; ordinary direct construction fails
with the exact path-free `TypeError` above. The detached view is fresh on every
access. The future reader already owns the exact held-handle bytes and may use
only `manifest_sha256` as a validator cross-check; membership consumes the
detached roles and digest.

## Import Direction

The dependency direction is one-way:

```text
cli.clean_memory_protected_membership
    -> steps.common.clean_memory_protected_manifest

future cli.clean_memory_protected_manifest
    -> steps.common.clean_memory_protected_manifest
```

No shared module may import `cli`. Membership may import only public names from
the shared validator. The future reader may later import the same public
validator only after its separate security-policy prerequisites close.

## Exact Ownership Split

The shared validator exclusively owns:

- manifest schema, fixed child, maximum bytes, and exact eight-role order;
- strict UTF-8 and exact byte round-trip validation;
- duplicate-key and non-finite-number rejection;
- canonical JSON bytes and recursive NFC/control validation;
- exact role/member shapes, ordering, counts, identifiers, policy, and path
  bounds;
- Windows/POSIX manifest path lexical rules; and
- SHA-256 of the exact supplied bytes.

All member/path/count regexes and limits other than the selected public
constants stay private to the shared module.

Membership exclusively retains:

- `PROTECTED_MEMBERSHIP_SCHEMA` and its exact three-symbol public API;
- exact configuration type, canonical snapshot, digest, shape, topology, and
  configured-member validation;
- the full 18-role order and protected-boundary-role compatibility check;
- configured-member synthesis;
- combined configured/manifest alias and cleanup/evidence overlap checks;
- intentional protected-member containment behavior;
- membership projection construction, canonical digest, detached view, and
  final configuration mutation recheck; and
- the outer exact-bytes/type and size compatibility fence that preserves
  pre-configuration failure order.

Membership must contain no manifest schema literal, role/member parser,
manifest UTF-8 decode, duplicate/non-finite JSON hook for manifest bytes, or
manifest path lexical validation or canonicalization after adaptation. Its
retained generic JSON/path helpers serve configuration/projection only.

## Rejected Generic-Helper Extraction

The current generic-looking JSON and path helpers serve both configuration
revalidation and manifest parsing because those responsibilities happen to
share one module today. Moving them into a new generic public helper layer would
change the completed configuration dependency surface solely to reduce source
similarity.

That conflicts with the membership checkpoint's no-repeat rule: do not reopen
configuration-v1 or filesystem-observer internals merely to share private
validation helpers. The selected four-file seam therefore allows private
contract-local mechanics in both modules while keeping manifest schema and
meaning in exactly one authority. Tests, not cross-contract helper coupling,
freeze their current behavioral parity.

## Shared Validation Order And Failures

The shared function must fail in this exact order:

1. non-exact bytes:
   `TypeError("manifest_bytes must be exact bytes")`;
2. empty or over `PROTECTED_MANIFEST_MAX_BYTES`:
   `ValueError("Manifest bytes exceed the protocol size boundary")`;
3. non-exact path-flavor string:
   `TypeError("path_flavor must be exact str")`;
4. unsupported flavor:
   `ValueError("path_flavor must be 'windows' or 'posix'")`;
5. strict UTF-8 decode;
6. canonical JSON and recursive string validation;
7. exact decoded-text byte round trip;
8. exact schema and role census/order;
9. exact role/member records, counts, identifiers, ordering, policy, and paths;
   and
10. digest and immutable result construction.

Existing manifest-side errors remain plain `TypeError` or `ValueError` with
their current path-free messages, including:

- `Manifest bytes are not canonical UTF-8`;
- `Manifest is not canonical JSON`;
- `Manifest is not a JSON object`;
- `Manifest contains a noncanonical string`;
- `Manifest bytes are not canonical`;
- the existing schema, role, member, count, identifier, order, policy, and path
  boundary messages; and
- the existing `Protected-membership path ...` lexical messages.

Do not introduce a shared custom exception. The future physical reader owns a
separate finite path-free error taxonomy and must later translate validator
failures at its own boundary.

## Preserved Membership Failure Precedence

`project_protected_membership()` keeps this outward order:

1. exact manifest-byte type and size compatibility fence;
2. protected-role authority compatibility;
3. exact configuration type, bytes, digest, shape, topology, configured
   membership, and cleanup-scope validation;
4. one call to `validate_protected_manifest()` with the original bytes object
   and configuration-derived flavor;
5. combined role census, aliases, and destructive-scope overlap;
6. projection serialization and digest; and
7. final configuration mutation recheck.

The shared validator still rechecks its complete public input contract. The
outer membership fence is compatibility ordering, not a second manifest parser.

## Focused RED Matrix

Before production movement, add direct tests that fail because the new module
and API do not yet exist. RED must freeze:

- the exact six-symbol `__all__`, constants, signature, keyword-only flavor,
  frozen init-disabled result, detached view, digest, and path-free `repr`;
- exact direct-construction refusal through
  `TypeError("CanonicalProtectedManifest cannot be constructed directly")`;
- exact input types and new path-flavor failures;
- accepted POSIX and Windows manifests, case preservation, both presence
  values, one and 64 members per role, 512 total members, 4,096-byte path
  acceptance, and stable SHA-256;
- otherwise-valid duplicate and Windows-casefold-alias member paths accepted by
  the direct validator, proving alias authority remains in membership;
- every existing UTF-8, canonical JSON, duplicate/non-finite, recursion,
  noncanonical-string, schema, role, member, count, identifier, order, policy,
  path-flavor, reserved-name, and boundary rejection;
- exact exception class and message parity for the direct manifest corpus;
- standard-library-only imports and poisoned/audited capability-free import and
  invocation with no filesystem, environment, network, process, native,
  logging, output, or `sys.path` mutation; and
- no public constructor or mutable nested-state escape.

Then add adapter RED proving:

- membership invokes the shared validator exactly once with the original bytes
  object and resolved flavor;
- membership imports exactly the public child name, maximum bytes, role order,
  and validator, each under a private local alias;
- membership contains no locally redeclared manifest schema, child, maximum-
  byte, role-order, member-count, path-bound, or member-ID constants, and no
  `_manifest_members`, manifest-byte decode/parser call, or use of retained
  configuration JSON/path helpers to interpret `manifest_bytes`;
- its exact public API, projection bytes, manifest digest, membership digest,
  detached views, and path-free `repr` remain unchanged;
- configuration forgery, canonical-byte/digest, final-race, alias, overlap, and
  intentional-containment tests remain unchanged; and
- multi-fault cases preserve bytes-before-configuration and configuration-
  before-manifest-schema precedence.

## GREEN And Regression Gates

After focused RED/GREEN/refactor, run sequentially through the explicit
`goodq_core` interpreter:

- `tests/unit/test_clean_memory_protected_manifest_validator.py`;
- `tests/unit/test_clean_memory_protected_membership.py`, preserving the
  existing 98-test baseline before adding adapter oracles;
- the focused validator-plus-membership pair; and
- the existing 331-test configuration/candidate/filesystem/membership authority
  union, plus all new validator tests.

Also require Python compilation, exact import/export and AST ownership checks,
capability-poisoned isolated execution, staged and unstaged diff checks, and an
independent current-byte spec/security/test-oracle review. The implementation
checkpoint must record the final test counts rather than infer them from this
decision.

## Future Reader Boundary

This decision closes only canonical-validator ownership. It does not authorize
the protected-manifest reader.

The later reader must first compare the locally computed same-handle digest
with the direct external-pin evidence before decoding or parsing. Only then may
it pass those exact same bytes and selected flavor to this validator and
cross-check `manifest_sha256`. Manifest security policy and shared security
mechanics remain separate mandatory blockers before reader RED.

ProgramData locator/recheck, protected-member observation, pin/member lexical
and physical exclusions, authenticated composition, Qdrant observation,
runnable planning, approval, and cleanup remain closed later seams.

## Independent Review And Adjudication

Three independent read-only audits traced parser equivalence, API/error
ownership, and parity/test boundaries. The initial parity review proposed a
six-file generic-helper extraction. Contract review instead selected four files
because configuration and manifest validation are distinct authorities.

The binding completed-membership no-repeat rule resolved the disagreement. On
reconsideration, both the parity reviewer and a separate boundary adjudicator
changed to the exact four-file seam. All final receipts agree on the frozen
detached result, public immutable role order, one-way import direction,
preserved outer membership fence, and no generic helper layer.

## Evidence Boundary

This audit read repository source, tests, contracts, checkpoints, and the sole
roadmap only. It did not read or change live ProgramData, a pin, manifest,
token, ACL, configured or protected root, service, GoodQ data, Qdrant, evidence
store, job, MiniAgent, or cleanup authority.
