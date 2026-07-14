<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# R-07 Protected-Manifest Reader Capability-Gap Audit

## Outcome

Do not create the protected-manifest reader source/test pair yet.

Three independent read-only reviews agree that no equivalent production reader
exists and that the intended fixed-child, direct-pin, digest-before-parser
boundary is directionally correct. Current public capabilities are nevertheless
insufficient to implement it without weakening an already checkpointed
contract or creating a second authority:

1. the shared held-handle reader rejects every byte cap above 66, while the
   manifest protocol needs an EOF witness through byte 4,194,305;
2. the only exact canonical manifest validator remains private inside the
   structural membership module; and
3. the governing source decision requires manifest-chain owner and effective
   write-authority validation, but the manifest-specific policy and the shared
   projection-neutral token, descriptor-parsing, and effective-access mechanics
   needed beyond the existing detached descriptor read remain unselected or
   unavailable.

The exact first prerequisite is therefore only a two-file extension of the
existing held-handle read capacity. It must widen the accepted ceiling to
`4_194_305` while preserving the method, signature, return contract, lifecycle,
public surface, and the external-pin reader's exact 66-byte request. It must not
add a second read API or begin manifest-reader code.

This checkpoint supersedes only the 66-byte *maximum accepted argument* recorded
by the earlier pin-specific bounded-read checkpoint. The external-pin payload,
65-byte EOF proof, exact 66-byte request, and all reader behavior remain
unchanged.

## Governing Invariant

The future manifest reader must return the exact complete canonical byte string
read from one already-held file handle and authenticated by the direct exact
`ExternalPinEvidence` invoked by production orchestration. It may not reopen the
file by path, hash a second read, accept caller bytes or digests, duplicate
canonical parsing, or invent an owner/write policy.

A manifest of the maximum permitted size is 4,194,304 bytes. Under the existing
bounded-read contract, EOF is observed only when a successful synchronous read
returns zero bytes; reaching the requested cap returns `False` without an extra
probe. The caller therefore needs an exact read allowance of
`maximum_manifest_bytes + 1`, or `4_194_305`, to distinguish a complete maximum-
size manifest from an over-limit file.

## No-Repeat Proof

Repository production search found no function that performs all of the
following:

- derives the candidate evidence root from exact resolved configuration;
- selects only fixed child `protected-boundaries.json` through held no-follow
  traversal;
- binds the direct exact external-pin evidence;
- obtains complete bytes and EOF from the same held manifest handle;
- compares SHA-256 with the direct pin before decoding or parsing;
- applies the one canonical manifest validator to those same bytes; and
- returns immutable path-free evidence after full race and security rechecks.

The existing authorities remain distinct and must not be repeated:

| Authority | Completed responsibility | Missing reader responsibility |
| --- | --- | --- |
| `cli.clean_memory` | Exact import-pure configuration projection | No manifest acquisition or composition |
| `cli.clean_memory_external_pin` | Windows pin trust-root observation | No manifest bytes, root routing, or manifest policy |
| `cli.clean_memory_protected_membership` | Structural projection from caller-supplied canonical bytes | No provenance, pin authentication, or physical observation |
| `steps.common.windows_held_handle` | Opaque held-handle traversal, snapshots, bounded reads, detached descriptor bytes | No manifest-sized read allowance or security-policy interpretation |
| `steps.common.clean_memory` | Injected candidate-plan validation/storage | No production reader or observer |

Unrelated ingestion and scene-manifest readers are not protected-authority
readers and cannot be adapted by name alone.

## Proven Capacity Blocker

`WindowsHeldHandleBackend.read_file_bounded()` currently accepts only exact
integers from 1 through 66. The method already has the correct ownership and
same-handle behavior:

- exact-type argument validation precedes native I/O;
- the opaque handle token must be live and owned by the backend;
- the same native handle is rewound;
- reads are bounded by remaining capacity;
- impossible native counts fail closed;
- zero-byte success proves EOF; and
- reaching the cap returns `(prefix, False)` without an extra read.

`hash_file()` is not a substitute. It rewinds and reads again, returns only a
digest and byte count, and therefore cannot prove that its digest covers the
exact byte object returned to the parser.

No new public primitive is needed for fixed-child physical traversal. The
existing volume-root, directory enumeration, `OpenFileById`, snapshot, and
reverse-cleanup capabilities are sufficient once the remaining security
contract exists.

## Exact First Prerequisite Seam

The next mutating checkpoint is limited to:

- `steps/common/windows_held_handle.py`; and
- `tests/unit/test_windows_held_handle.py`.

Change only the accepted upper boundary of the existing
`read_file_bounded(..., maximum_bytes=...)` contract from `66` to
`4_194_305`. Preserve:

- the method name, parameters, return type, EOF semantics, error translation,
  handle ownership, and cleanup behavior;
- the module's exact four-symbol `__all__` export;
- the backend's existing public method set;
- every filesystem-observer adapter and fake-backend parity check; and
- `cli.clean_memory_external_pin` requesting exactly 66 bytes.

Do not add a second complete-read method, a manifest constant to the shared
backend, parser logic, token logic, descriptor policy, path traversal, or reader
code in this seam. The numeric ceiling is projection-neutral transport
capacity, not manifest authority.

## Focused RED Matrix

The two-file seam must prove all of the following before implementation:

1. exact integer `4_194_305` is accepted;
2. `4_194_306`, booleans, integer subclasses, non-integers, zero, and negative
   values fail path-free before seek or read;
3. a 4,194,304-byte payload with cap 4,194,305 returns the complete payload and
   `eof_observed=True` after the explicit zero-byte read;
4. a 4,194,305-byte payload with the same cap returns the exact capped prefix and
   `eof_observed=False` with no extra read;
5. partial reads, rewind behavior, impossible counts, native-error translation,
   foreign/closed/post-context token refusal, and reverse cleanup remain green;
6. the Windows native oracle proves maximum-size EOF and exact-cap behavior;
7. external-pin tests still prove exactly one bounded request at 66 bytes; and
8. filesystem-observer and external-pin public/backend parity remain unchanged.

The approved regression census after focused RED/GREEN is:

- `tests/unit/test_windows_held_handle.py`;
- `tests/unit/test_clean_memory_external_pin.py`; and
- `tests/unit/test_clean_memory_filesystem.py`.

Do not create `tests/unit/test_clean_memory_protected_manifest.py` in this
checkpoint.

## Canonical-Parser Authority Blocker

The exact byte/schema validator currently exists only as private helpers in
`cli.clean_memory_protected_membership` and covers strict UTF-8, duplicate-key
and non-finite-number rejection, recursive NFC/control validation, canonical
JSON byte equality, exact schema/role/member census, member ordering, policy,
path canonicalization, bounds, and manifest SHA-256.

The reader must not import those private helpers, copy their logic, call
`project_protected_membership()` as a physical-reader surrogate, or return
authenticated but unvalidated bytes. Any of those choices would violate either
import ownership, the frozen reader-before-membership order, or the one-
canonical-validator invariant.

After the capacity checkpoint, a separate read-only audit must select one pure,
projection-neutral canonical manifest validator and its exact extraction/parity
seam. That later checkpoint must adapt structural membership without changing
its public API or output and prove byte-for-byte/error parity before the reader
may depend on it. This audit does not freeze that module name or public shape.

## Security-Policy Authority Blocker

The protected-authority source decision requires every governed parent and the
manifest file to have trusted owner and effective write authority, with the
policy rechecked before return. The shared backend exposes detached self-
relative descriptor bytes but intentionally does not parse owners/DACLs,
snapshot process tokens, evaluate generic rights, or run `AccessCheck`.

Those mechanics and the external-pin-specific policy currently remain private
to `cli.clean_memory_external_pin` and may not be imported or copied. The pin-
specific policy must not move into the projection-neutral backend; the later
extraction/parity audit must select the placement of genuinely generic security
mechanics from fresh dependency evidence. The repository has not yet selected:

- which candidate-root ancestors are policy governed;
- the valid owner/group/ACE set;
- who may create, replace, delete, or write the manifest;
- the accepted reader token/elevation/privilege state; or
- which exact rights must succeed or fail.

Without those decisions, `security_policy_mismatch` has no trustworthy oracle.
A separate decision-only audit must select the manifest security anchor and
policy. Only then may a separate extraction/parity checkpoint expose the
projection-neutral token, descriptor-parsing, and effective-access mechanics
that the selected policy actually needs. Pin- and manifest-specific policy must
remain in their respective readers.

## Stable Future Reader Boundary

The dependency blockers do not change the selected stable input boundary:

```python
def read_protected_manifest(
    configuration: ResolvedPlanConfiguration,
    *,
    external_pin_evidence: ExternalPinEvidence,
) -> ProtectedManifestEvidence:
    ...
```

The future reader must require both exact public types, reject subclasses and
caller substitutes, validate their private canonical projections and detached
digests at entry, and recheck them before return. Production provenance comes
from the future `plan` edge directly invoking both readers; exact types alone do
not prove provenance.

The intended closed public surface is limited to one evidence schema constant,
one stable path-free reader error, one frozen init-disabled evidence class, and
the reader function. Full evidence fields and the final finite error set remain
unfrozen until the security and parser prerequisites are selected. No protected-
manifest reader source file is authorized by this audit.

## Required Future Reader Order

Once all prerequisites exist, the reader order remains:

1. exact configuration and external-pin input fences;
2. Windows/capability and effective-token baseline;
3. candidate-root traversal and constant-child selection through held no-follow
   handles only;
4. complete parent membership, physical identity, type, link, stream, metadata,
   and selected security-policy validation;
5. require initial size `1..4_194_304`;
6. read once from the same held handle with `initial_size + 1`, require EOF and
   exact initial size, then immediately resnapshot;
7. compute SHA-256 from the returned bytes locally;
8. compare with direct pin evidence before UTF-8 decoding or JSON parsing;
9. pass the same bytes through the one shared canonical validator;
10. recheck exact input projections/digests, token, descriptors, held snapshots,
    complete parent enumerations, and input projections/digests again;
11. construct immutable evidence only after all fences pass; and
12. close all held resources in exact reverse acquisition order, preserving the
    primary failure and sanitizing cleanup-only failures.

ProgramData locator/recheck, protected-member observation, pin/member lexical
and physical exclusion, final composition, Qdrant observation, runnable
planning, approval, and cleanup remain later separate seams.

## Dependency Order

The only immediately executable seam is the held-handle capacity extension.
After it checkpoints, current evidence requires both of these branches before
reader RED begins:

- canonical-validator extraction/parity; and
- manifest security-policy decision followed by only the shared security
  mechanics that decision proves necessary.

Their relative scheduling may be reassessed from fresh evidence, but the
security decision must precede security-mechanics extraction, and both branches
must finish before reader implementation. This dependency graph prevents an
easy transport fix from being mistaken for reader readiness.

## Independent Review

Three bounded read-only reviewers independently traced parser/API ownership,
held-handle lifecycle/capabilities, adapter parity, and current contracts. All
three found the 66-byte capacity blocker, rejected a second read API, rejected
duplicate canonical parsing, and agreed that no reader source/test pair should
be created yet. The lifecycle review independently identified the unresolved
manifest-specific owner/write-authority policy and confirmed that public
traversal capability otherwise exists.

## Evidence Boundary

This audit read only repository source, tests, active contracts, checkpoints,
and the sole roadmap. It did not read or change live ProgramData, a production
pin or manifest, token, ACL, configured or protected root, service, GoodQ data,
Qdrant, evidence store, job, MiniAgent, or cleanup target.
