<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# R-07 Protected-Manifest Validator Extraction Checkpoint

## Outcome

Private checkpoint `41e56c74` closes the canonical-parser ownership
prerequisite selected by the protected-manifest reader capability-gap audit.

One standard-library-only module now owns exact protected-manifest byte,
canonical JSON, schema, role, member, policy, path, bound, and digest meaning.
Structural membership consumes that public validator exactly once and no longer
owns or copies manifest parsing. Its public API, configuration authority,
combined 18-role alias/overlap checks, projection bytes, digest, and final
configuration mutation fence remain unchanged.

This is not a physical reader. It does not locate, open, authenticate, enroll,
publish, rotate, recover, or observe a manifest or protected member.

## Exact Diff

The implementation checkpoint contains exactly four files:

- `steps/common/clean_memory_protected_manifest.py` adds the pure validator;
- `tests/unit/test_clean_memory_protected_manifest_validator.py` adds its direct
  contract and parity corpus;
- `cli/clean_memory_protected_membership.py` delegates manifest meaning while
  retaining membership-specific authority; and
- `tests/unit/test_clean_memory_protected_membership.py` freezes delegation,
  precedence, ownership, and unchanged projection behavior.

No reader, locator, security policy, filesystem observer, held-handle backend,
external-pin reader, or candidate plan changed. No external dependency,
service, live runtime state, or externally observable membership contract
changed.

## Closed Public Contract

The new module exports exactly:

```python
PROTECTED_MANIFEST_SCHEMA
PROTECTED_MANIFEST_CHILD_NAME
PROTECTED_MANIFEST_MAX_BYTES
PROTECTED_MANIFEST_ROLE_ORDER
CanonicalProtectedManifest
validate_protected_manifest
```

`validate_protected_manifest()` accepts exact bytes and one keyword-only path
flavor. It validates strict UTF-8, duplicate-free finite canonical JSON,
recursive canonical strings, the exact eight-role/member contract, lexical
paths and bounds, then returns a frozen init-disabled result containing the
exact-byte SHA-256 and a fresh detached manifest view.

Ordinary result construction is refused. Raw bytes are private and omitted
from `repr`. The validator intentionally accepts otherwise-valid duplicate and
Windows-casefold-alias paths; only structural membership owns combined-role
alias and destructive-scope overlap rejection.

## Preserved Membership Contract

Membership still applies this exact order:

1. exact manifest-bytes type and outer size compatibility fence;
2. protected-role authority check;
3. exact configuration validation;
4. one shared-validator call with the original bytes and resolved flavor;
5. combined 18-role census, alias, and cleanup-scope checks;
6. canonical projection and digest construction; and
7. final configuration mutation recheck.

The outer fence is compatibility ordering, not a second parser. Tests prove
the byte fence wins when byte and protected-role inputs are both invalid, and
that valid bytes reach the role-authority failure before configuration or
shared validation.

## TDD Evidence

RED first failed because the shared module was absent:

```text
1 failed
AssertionError: canonical protected-manifest validator is absent
```

After the exact API skeleton passed, behavioral RED failed only through the
deliberate unimplemented validator:

```text
73 failed, 3 passed, 1 deselected
```

Adapter RED then proved membership still owned the parser and made no shared
validator call:

```text
5 failed, 1 passed, 96 deselected
```

The identical adapter selection passed after the minimal delegation change:

```text
6 passed, 96 deselected
```

## Oracle Hardening

Self-review and independent review closed every discovered oracle gap before
commit. The final tests additionally prove:

- the otherwise unreachable total-member rejection by lowering the private
  total only inside the test while freezing production at 512;
- an opaque original bytes object is delegated once and membership consumes a
  fake result's detached role corpus and sentinel digest rather than reparsing
  or recomputing;
- exact multi-fault bytes, protected-role, configuration, and manifest failure
  precedence;
- exact signature annotations, member-ID behavior and regex flags;
- no renamed local manifest parser, constants, or hidden project import edge;
  and
- module-body execution and invocation remain capability-free under poisoned
  filesystem, environment, network, process, native, logging, import, and
  audit boundaries.

The final independent current-byte review reported no Critical, Important, or
Minor findings and returned `READY`.

## Fresh Verification

The implementer and controller independently reproduced the final committed
gates through the explicit `goodq_core` interpreter:

| Gate | Result |
|---|---:|
| Direct protected-manifest validator | 103 passed |
| Structural protected membership | 102 passed |
| Validator plus membership pair | 205 passed |
| Approved authority union | 437 passed |
| Exact four-file Python compilation | passed |
| Staged and committed diff checks | passed |
| Changed-file census | exactly four |
| Independent current-byte review | READY |

The 102 membership items preserve all 98 pre-extraction items and add four
ownership/delegation items. The 437-item authority union preserves the current
330-item pre-task census and adds those four membership items plus 103 direct
validator items.

## No-Repeat Boundary

Do not add another canonical protected-manifest parser, restore private parsing
to membership, reopen completed configuration helpers to create a generic JSON
layer, move alias/overlap authority into the direct validator, or treat this
checkpoint as authenticated reader evidence.

The future reader must hash the exact held bytes, compare that digest with the
direct external-pin evidence before decoding or parsing, pass those same bytes
to this validator, and cross-check the returned digest. That reader remains
unauthorized until its manifest-specific security policy and required shared
security mechanics are separately selected and checkpointed.

## Next Bounded Mission

Run a decision-only, read-only no-repeat audit of manifest-chain security
policy. Select the exact governed ancestor/file set, owner/group/ACE policy,
effective reader token state, write/create/replace/delete authority, and rights
that must succeed or fail. Then identify only the projection-neutral token,
descriptor-parsing, and effective-access mechanics the selected policy proves
necessary.

Do not inspect live ProgramData or ACLs, extract mechanics, or create reader
code during that audit. Pin-specific policy remains private to the completed
external-pin reader; manifest-specific policy belongs only to the future
manifest reader.

## Evidence Boundary

Implementation and verification used repository source, tests, isolated
processes, and test-owned data only. No live ProgramData, production pin,
manifest, token, ACL, configured or protected root, service, GoodQ data,
Qdrant, evidence store, job, MiniAgent, or cleanup target was read or changed.
