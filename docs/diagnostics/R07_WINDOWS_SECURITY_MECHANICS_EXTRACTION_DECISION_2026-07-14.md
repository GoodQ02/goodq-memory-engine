<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# R-07 Windows Security-Mechanics Extraction Decision

## Outcome

Extract one projection-neutral Windows security-mechanics authority and adapt
the completed external-pin reader in the same checkpoint.

The exact next implementation/parity seam is four files:

1. add `steps/common/windows_security_mechanics.py`;
2. add `tests/unit/test_windows_security_mechanics.py`;
3. adapt `cli/clean_memory_external_pin.py`; and
4. adapt `tests/unit/test_clean_memory_external_pin.py`.

Do not change `steps/common/windows_held_handle.py` or its tests. Do not create
the protected-manifest reader. Do not move the frozen clean-memory reader-
identity v1 projection or digest during this checkpoint.

## Governing Invariant

The shared layer may own native mechanics, never GoodQ authority. It may bind
and validate a bounded Win32 security ABI, own token and descriptor lifetimes,
return immutable observations, map file masks, and perform one bounded access
check. It may not know protected roles, fixed names, trusted SIDs, accepted
reader policy, DACL sequences, expected access outcomes, evidence schemas,
consumer error codes, or operation phase.

The completed external-pin reader remains byte- and behavior-exact at its
public boundary. Its no-argument API, four exports, thirteen-code error table,
five-object grammar, token acceptance, enrolled-reader policy, DACL policy,
v1 identity projection and digest, evidence projection and digest, failure
order, cleanup precedence, and race brackets remain reader-owned.

## No-Repeat Result

Keep these completed seams closed:

- held-handle traversal, same-handle bounded reads, and descriptor transport;
- `security_read` request mask `0x7` and `security_read_label` request mask
  `0x17`;
- the external-pin source, reader, evidence, and lifecycle checkpoint;
- protected-manifest canonical validation and structural membership;
- the selected manifest security policy;
- configuration, filesystem observation, candidate planning, and storage; and
- enrollment, publication, rotation, recovery, Qdrant observation, approval,
  and cleanup execution.

No live token, ACL, configured root, manifest, pin, or production object is an
input to this extraction.

## Reconciled Audit Decision

Three independent read-only audits considered parser-first, token-first, and
one combined mechanics checkpoint.

A parser-only checkpoint was rejected because the existing `AccessCheck` must
receive the address of the same private stable descriptor allocation that was
parsed. Moving allocation ownership without moving the bounded access
operation would either expose a raw pointer or require a temporary private
cross-module escape.

A token-only checkpoint was rejected because retained baseline ownership,
private duplication, descriptor provenance, and access cleanup form one native
lifetime and rollback boundary. Staging them separately would adapt the same
external-pin state and cleanup graph twice.

The selected four-file checkpoint is therefore the smallest coherent seam,
even though it is not the smallest line-count seam. It removes the private
duplicate authority in the same checkpoint that introduces the shared one.

The frozen v1 identity projection is different: it is clean-memory policy, not
generic Windows mechanics. It stays private and exact during this checkpoint.
Any later shared identity-projection module requires a separate authority and
parity decision.

## Exact Public Surface

The new module is standard-library-only, import-pure, and has this exact public
surface:

```python
WINDOWS_TOKEN_PROFILE_BASE = "base"
WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY = "mandatory_policy"
WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY = "dacl_only"
WINDOWS_DESCRIPTOR_PROFILE_MANDATORY_LABEL = "mandatory_label"

__all__ = (
    "WINDOWS_TOKEN_PROFILE_BASE",
    "WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY",
    "WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY",
    "WINDOWS_DESCRIPTOR_PROFILE_MANDATORY_LABEL",
    "WindowsSecurityMechanicsError",
    "WindowsSid",
    "WindowsSidRecord",
    "WindowsPrivilege",
    "WindowsTokenStatistics",
    "WindowsTokenSnapshot",
    "WindowsAce",
    "WindowsSecurityDescriptor",
    "WindowsPinnedSecurityDescriptor",
    "WindowsMutationDenial",
    "WindowsAccessCheckScope",
    "WindowsSecuritySession",
    "WindowsSecurityMechanics",
    "verify_windows_security_abi",
    "bind_windows_security",
)

def verify_windows_security_abi() -> None:
    ...

def bind_windows_security(
    *,
    kernel32: object,
    advapi32: object,
) -> WindowsSecurityMechanics:
    ...
```

The shared module never calls `ctypes.WinDLL` at import time, during preflight,
or inside the binder. `verify_windows_security_abi()` performs the pointer-
width and structure-layout gate without a DLL load. Consumers must call it
before their first `WinDLL` call. `bind_windows_security()` repeats the same
idempotent gate, binds the already-loaded libraries, performs no token,
descriptor, or access operation, and creates one private provenance identity.

The public mechanics methods are exact:

```python
class WindowsSecurityMechanics:
    def resolve_privilege_luid(self, privilege_name: str) -> int: ...
    def open_token_session(self, *, profile: str) -> WindowsSecuritySession: ...
    def pin_security_descriptor(
        self,
        descriptor_bytes: bytes,
        *,
        profile: str,
    ) -> WindowsPinnedSecurityDescriptor: ...
    def map_file_mask(self, raw_mask: int) -> int: ...

class WindowsSecuritySession:
    @property
    def baseline_snapshot(self) -> WindowsTokenSnapshot: ...
    def observe_effective(self) -> WindowsTokenSnapshot: ...
    def open_access_check(
        self,
        descriptor: WindowsPinnedSecurityDescriptor,
    ) -> WindowsAccessCheckScope: ...
    def close(self) -> None: ...

class WindowsAccessCheckScope:
    def check_denial(self, *, raw_mask: int) -> WindowsMutationDenial: ...
    def close(self) -> None: ...

class WindowsPinnedSecurityDescriptor:
    @property
    def observation(self) -> WindowsSecurityDescriptor: ...
```

`WindowsSecurityMechanics`, `WindowsSecuritySession`,
`WindowsAccessCheckScope`, and `WindowsPinnedSecurityDescriptor` are opaque,
init-disabled owners. Direct construction raises the fixed path-free
`TypeError("<ClassName> cannot be constructed directly")`. They expose no raw
handle, pointer, address, mutable buffer, native library, output pointer,
arbitrary duplication method, or impersonation operation. A pinned descriptor
may be checked only by a session from the same mechanics provenance.

Every one of those four capability owners rejects `copy.copy`,
`copy.deepcopy`, pickle, and direct reduction through `__copy__`,
`__deepcopy__`, `__reduce__`, and `__reduce_ex__`. Each rejection raises exact
`TypeError("<ClassName> cannot be copied or serialized")`. No operation may
create an owner alias with independent lifecycle state, duplicate close
authority, detached provenance, or a second reference to private native
storage.

The exact observation schemas, in field order, are:

```python
@dataclass(frozen=True, repr=False)
class WindowsSid:
    binary: bytes
    numeric: str

@dataclass(frozen=True, repr=False)
class WindowsSidRecord:
    sid: WindowsSid
    attributes: int

@dataclass(frozen=True, repr=False)
class WindowsPrivilege:
    luid: int
    attributes: int

@dataclass(frozen=True, repr=False)
class WindowsTokenStatistics:
    token_id: int
    authentication_id: int
    expiration_time: int
    token_type: int
    dynamic_charged: int
    dynamic_available: int
    group_count: int
    privilege_count: int
    modified_id: int

@dataclass(frozen=True, repr=False)
class WindowsTokenSnapshot:
    statistics: WindowsTokenStatistics
    user_sid: WindowsSid
    groups: tuple[WindowsSidRecord, ...]
    privileges: tuple[WindowsPrivilege, ...]
    restricted_sids: tuple[WindowsSidRecord, ...]
    elevation_type: int
    is_elevated: bool
    has_restrictions: bool
    integrity: WindowsSidRecord
    ui_access: bool
    mandatory_policy: int | None
    is_app_container: bool

@dataclass(frozen=True, repr=False)
class WindowsAce:
    ace_type: int
    flags: int
    mask: int
    sid: WindowsSid

@dataclass(frozen=True, repr=False)
class WindowsSecurityDescriptor:
    control: int
    owner: WindowsSid
    group: WindowsSid
    dacl_present: bool
    dacl_null: bool
    dacl_revision: int | None
    dacl_aces: tuple[WindowsAce, ...]
    sacl_present: bool
    sacl_null: bool
    sacl_revision: int | None
    mandatory_label_aces: tuple[WindowsAce, ...]

@dataclass(frozen=True, repr=False)
class WindowsMutationDenial:
    raw_mask: int
    mapped_mask: int
    denied: bool
```

The ordinary observation values may be directly constructed for pure policy
and metamorphic tests; only objects carrying native capability or allocation
provenance are init-disabled. Equality is exact dataclass field equality in the
order shown. Every observation class has a custom redacted representation of
the exact form `<ClassName>(<redacted>)`; repr never reveals SIDs, groups,
privileges, integrity, descriptor trustees, masks, bytes, handles, pointers,
addresses, or native errors.

`WindowsPinnedSecurityDescriptor.observation` returns its exact immutable
`WindowsSecurityDescriptor`. It exposes no raw descriptor bytes. The consumer
retains the detached input bytes separately for byte-for-byte rechecks. The
capability-owner copy/serialization prohibition above applies; one strong
private reference keeps the exact-length allocation alive for the entire
access scope.

## Native Binding Ownership

The shared module owns the exact pre-load layouts and the full already-frozen
security ABI availability fence for:

- `GetCurrentThread`, `GetCurrentProcess`, and `CloseHandle`;
- `OpenThreadToken`, `OpenProcessToken`, and `GetTokenInformation`;
- `LookupPrivilegeValueW` and `DuplicateTokenEx`;
- `MapGenericMask`; and
- `AccessCheck`;
- availability-only `LocalFree`; and
- availability-only `GetSecurityInfo`, `IsValidSecurityDescriptor`,
  `GetSecurityDescriptorControl`, and `GetSecurityDescriptorLength`.

It owns the exact Win64 layouts used by those calls, including LUID, token
record, token statistics, generic mapping, and privilege-set structures.
The external-pin adapter retains `_GUID` and its exact 16-byte pre-load size
guard because that layout belongs only to Known Folder resolution, not shared
security mechanics.

The availability-only exports remain unused and must not become a second
descriptor transport. They move only because one binder must preserve the
completed exact export order without duplicating security layouts or binding
logic in the adapter.

External-pin preflight order is exact:

1. validate adapter-owned `ctypes.sizeof(_GUID) == 16`;
2. call `verify_windows_security_abi()` before any DLL load;
3. load `kernel32`, `shell32`, and `ole32`, then `advapi32`, each with
   `use_last_error=True` and the existing load-failure classifications;
4. bind `SHGetKnownFolderPath` and `CoTaskMemFree` with existing classification;
5. call `bind_windows_security(kernel32=..., advapi32=...)`;
6. only after the binder returns, construct the held-handle backend; and
7. only after backend entry, resolve the privilege LUID and capture a token.

Within the shared binder, export lookup and ABI assignment retain current
source order: kernel current-thread/current-process/close/`LocalFree`; advapi
thread-token/process-token/token-information/privilege lookup/duplication/
generic mapping/access check; then the four availability-only descriptor
exports. Missing or malformed security exports are `unsupported_security`.
Binder failure creates no handle, allocation, token observation, descriptor
observation, or cleanup obligation.

## Token Observation Contract

`open_token_session()` always allocates an owner before a handle-producing
call. It probes the current thread first using exact `TOKEN_QUERY` and
`OpenAsSelf=TRUE`.

- Success with a non-null thread token closes that token and raises mechanics
  code `thread_token_present`.
- Failure falls back to the process token only for exact `ERROR_NO_TOKEN`.
- Any other result is `observation_failed`.
- The retained process token opens with exact `TOKEN_QUERY | TOKEN_DUPLICATE`.

The session owns that one retained process-token handle until exact close. It
never installs a thread token. `observe_effective()` repeats the thread probe,
then opens a transient process token with exact `TOKEN_QUERY`, captures one
fresh snapshot, and closes it. It returns the snapshot; the consumer owns the
phase-specific equality check and error classification.

The base profile preserves the current external-pin query sequence exactly:

```text
10, 1, 1, 2, 2, 3, 3, 11, 11, 18, 20, 21, 25, 25, 26, 29, 10
```

The mandatory-policy profile inserts exact `TokenMandatoryPolicy` class `27`
after class `26` and before class `29`, producing 18 calls. Its result is an
exact four-byte DWORD stored as `mandatory_policy`; reserved bits outside the
documented `0x3` mask are malformed native output. Values `0` through `3` are
observations only. A consumer, not the shared module, decides which values are
acceptable.

`WindowsTokenSnapshot` equality includes `mandatory_policy`. Base snapshots
set it to `None`; the external-pin reader uses only the base profile, so class
27 never enters its query sequence, equality, v1 projection, or digest. The
future manifest reader must use the mandatory-policy profile and locally
require exact value `1` or `3`; a policy-only change must fail its race check
even though the frozen v1 identity digest remains unchanged.

All existing bounded token-buffer sizes, query sentinels, statistics-before/
after fence, record-count reconciliation, pointer containment, nonoverlap,
duplicate rejection, sorting, cleanup, and control-flow propagation move
unchanged into the shared module.

Handle-output ownership is exact for thread, process, and duplicate opens:

- the owner exists before the native call;
- only native success plus a non-null output transfers ownership;
- success plus null is `observation_failed` and closes nothing;
- every failure output, including a non-null or sentinel value, is cleared and
  never closed because ownership was not transferred;
- every genuine transient token closes immediately after its observation;
- the retained baseline closes exactly once and remains the final native token
  cleanup after held objects and backend exit; and
- a value is cleared from its owner before `CloseHandle`, so close failure
  cannot permit a second close.

The session state is exact `OPEN` or `CLOSED`. `close()` is idempotent, leaves
the session `CLOSED` even when native close fails, and raises one sanitized
`observation_failed` node for that failure. `baseline_snapshot`,
`observe_effective()`, and `open_access_check()` on a closed session raise
`observation_failed` without a native call. There is no finalizer and no
context-manager API. One session may own at most one open access scope; opening
a second is `observation_failed`. Closing a session with an open scope closes
the scope first and appends any baseline-close failure after the scope-close
failure.

## Descriptor Contract

`pin_security_descriptor()` accepts exact bytes only and enforces the
independent inclusive `20..131072` bound. It copies those bytes once into one
private exact-length, stable allocation, parses directly from that allocation,
and retains it. Python cannot make the `ctypes` allocation physically
immutable; logical immutability is enforced by non-exposure, rejected copy/
pickle paths, and one strong owner reference. The future `AccessCheck` pointer
is the address of that same allocation. No second native descriptor
reconstruction or mutable view is permitted.

Both profiles parse exact revision-1 self-relative descriptors, owner, group,
DACL, SIDs, ACLs, ACEs, alignment, interval ownership, zero gaps, zero padding,
and zero trailing bytes. DACL ordinary allow and deny ACEs preserve raw order,
type, flags, mask, and SID. ACL revisions 2 and 4 are structural observations;
consumer policy owns exact revision requirements.

The DACL-only profile preserves external-pin behavior: it requires a present,
non-null DACL, and every nonzero SACL offset is `unsupported_descriptor`.

The mandatory-label profile records DACL and SACL presence independently from
their offsets:

- control bit clear plus zero offset is absent (`present=False`, `null=False`);
- present control bit plus zero offset is a null ACL (`present=True`,
  `null=True`);
- present control bit plus nonzero offset is a non-null parsed ACL; and
- control bit clear plus nonzero offset is malformed.

An absent or null ACL has revision `None` and an empty ACE tuple. A non-null
empty ACL preserves its parsed revision and has an empty tuple. This exact
representation lets future policy distinguish absent, null, empty, and
populated ACLs. Owner and group remain required non-null requested components.

Within a non-null selected SACL, the mandatory-label profile accepts only
`SYSTEM_MANDATORY_LABEL_ACE_TYPE` (`0x11`) ACEs. It preserves SACL revision and
each label ACE's raw type, flags, mask, and SID. Another well-formed SACL ACE
class is `unsupported_descriptor`; malformed header, ACL, ACE, SID, interval,
alignment, padding, or trailing data is `malformed_descriptor`. The shared
parser does not require either ACL, a label, an exact count, exact flags, an
exact mask, a particular SID, or an exact descriptor control value.

The future manifest reader alone must require exactly one medium-integrity
label ACE with flags `0` and exact no-write-up mask. The external-pin adapter
continues to use DACL-only and continues to reject all SACL-bearing input.

## Mapping And Bounded Access Contract

The shared module owns the exact file generic mapping:

```text
GenericRead    0x00120089
GenericWrite   0x00120116
GenericExecute 0x001200a0
GenericAll     0x001f01ff
```

`map_file_mask()` maps a fresh DWORD copy with `MapGenericMask` and returns the
mapped value. The caller's raw mask remains unchanged.

`WindowsAccessCheckScope.check_denial()` is deliberately not a general
authorization oracle. It accepts
one exact raw mask from this closed projection-neutral file-mutation set:

```text
0x00000002  FILE_WRITE_DATA
0x00000004  FILE_APPEND_DATA
0x00000010  FILE_WRITE_EA
0x00000040  FILE_DELETE_CHILD
0x00000100  FILE_WRITE_ATTRIBUTES
0x00010000  DELETE
0x00040000  WRITE_DAC
0x00080000  WRITE_OWNER
```

It rejects booleans, combinations, zero, generic bits, `MAXIMUM_ALLOWED`, and
every other mask before native execution. The consumer owns which member is
checked for which object.

`open_access_check()` privately duplicates the retained baseline once per
descriptor with exact `TOKEN_QUERY`, no security attributes,
`SecurityImpersonation`, and `TokenImpersonation`. The resulting opaque scope
keeps that single duplicate for sequential one-mask calls and pins the exact
descriptor owner strongly. The consumer evaluates each returned denial
immediately; after the first not-denied result or exception it performs no
later mask. This preserves the external-pin total of five duplicates and 19
`AccessCheck` calls and its first-failure order.

Each call maps the raw mask, zeroes the privilege storage, initializes
`GrantedAccess` to exact `0xffffffff` and `AccessStatus` to exact `-1` as native
write-detection sentinels, invokes `AccessCheck` against the pinned allocation,
and validates privilege-set bounds and padding. It returns only a frozen
`WindowsMutationDenial` containing:

```text
raw_mask
mapped_mask
denied
```

Native API failure is never denial. An exact denial has status `0`, granted
access `0`, privilege count `0`, and privilege control `0`. An exact grant has
status `1` and granted access equal to the mapped mask; it is returned only as
`denied=False`, without exposing granted access or a reusable entitlement.
Other status/grant quadrants or malformed privilege output are
`observation_failed`.

The scope state is exact `OPEN` or `CLOSED`. `close()` clears and closes the one
duplicate before any post-access token fence, is idempotent, and remains closed
after close failure. `check_denial()` after close is `observation_failed`
without a native call. There is no finalizer or context-manager API.

The shared module does not decide whether `denied=False` is acceptable.
External pin and future manifest policy each map it to their own policy
mismatch and require exact `denied=True`. Real kernel opens and same-handle
reads remain the only positive-access proof.

## Shared Error Contract And Translation

`WindowsSecurityMechanicsError` is a frozen-code, path-free `RuntimeError` with
only these codes:

| Code | Exact message |
|---|---|
| `unsupported_security` | `Required Windows security support is unavailable.` |
| `thread_token_present` | `A thread token is active.` |
| `observation_failed` | `Windows security observation failed.` |
| `malformed_descriptor` | `Windows security descriptor is malformed.` |
| `unsupported_descriptor` | `Windows security descriptor uses unsupported features.` |

The constructor accepts only those exact strings, exposes immutable `.code`,
and rejects every other value with
`ValueError("Unknown Windows security mechanics error code")`.

Invalid caller types, profiles, or masks use fixed path-free `TypeError` or
`ValueError`; they are programming-contract failures, not native observations.
Raw Win32 error numbers, token contents, descriptor bytes, paths, pointers,
handles, and exception text never leave the shared error graph.

The programming-contract messages are exact:

| Condition | Exception and message |
|---|---|
| profile is not exact `str` | `TypeError("profile must be exact str")` |
| unsupported token profile | `ValueError("Unsupported Windows token profile")` |
| unsupported descriptor profile | `ValueError("Unsupported Windows descriptor profile")` |
| descriptor input is not exact `bytes` | `TypeError("descriptor_bytes must be exact bytes")` |
| descriptor length outside the bound | `ValueError("descriptor_bytes length is outside the supported boundary")` |
| privilege name is not exact `str` | `TypeError("privilege_name must be exact str")` |
| empty, over-256-code-unit, NUL, or control privilege name | `ValueError("privilege_name is invalid")` |
| mapped mask is not exact `int` | `TypeError("raw_mask must be exact int")` |
| mapped mask outside DWORD | `ValueError("raw_mask is outside the DWORD boundary")` |
| denial mask is not one closed mutation member | `ValueError("raw_mask is outside the mutation-denial boundary")` |

Direct owner construction uses the exact class-name message specified above.
The binder rejects null library objects or missing/malformed exports with
`unsupported_security`; direct `WindowsSecurityMechanics(...)` construction
does not become a second binder.

The external-pin adapter translates exactly:

| Mechanics result | External-pin result |
|---|---|
| bind `unsupported_security` | `unsupported_security` |
| baseline `thread_token_present` | `untrusted_reader` |
| recheck `thread_token_present` | `observation_raced` |
| `malformed_descriptor` | `observation_failed` |
| `unsupported_descriptor` | `unsupported_security` |
| `observation_failed` or unexpected internal failure | `observation_failed` |
| exact `denied=False` result | `security_policy_mismatch` |
| exact `denied=True` result | continue |
| unequal effective snapshot | `observation_raced` |

Cleanup failure remains subordinate to an existing primary failure and primary
when no earlier failure exists. `KeyboardInterrupt`, `SystemExit`, and other
control-flow exceptions retain their original object and traceback while
cleanup is still attempted.

That rule applies recursively, not only to the root code. Every mechanics-
originated cleanup node is already a sanitized
`WindowsSecurityMechanicsError`; raw native exceptions are never linked. The
external adapter clones each mechanics node to the mapped
`ExternalPinReaderError`, preserving explicit-cause versus context edges,
`__suppress_context__`, node order, and the absence of raw text. It appends the
translated cleanup chain after any existing consumer/backend cleanup chain.

Exact phase behavior remains:

- initial thread-token presence is primary `untrusted_reader`; a thread-token
  close failure is a linked sanitized `observation_failed` cleanup node;
- recheck thread-token presence is primary `observation_raced`; its close
  failure is linked after it;
- on a not-denied result, external pin raises `security_policy_mismatch`
  immediately, closes the access scope, and links close failure after that
  primary without checking a later mask or running the post-access fence;
- on a clean series, scope close completes before the post-access token fence;
- outer held-object/backend cleanup remains ahead of baseline-session cleanup,
  and the baseline is the final native handle cleanup; and
- a cleanup-only failure becomes the primary `observation_failed` node.

For a control-flow primary, the original exception object, traceback, cause/
context topology, and suppress-context flag survive; sanitized shared cleanup
is attached without replacement. The existing external-pin cleanup graph
oracles remain authoritative.

## External-Pin Adapter Ownership

After adaptation, `cli/clean_memory_external_pin.py` retains:

- its exact public exports, errors, evidence object, and no-argument operation;
- Known Folder resolution, fixed held route, roles, names, and source grammar;
- backend lifecycle and route-bound `_HeldObject` ownership;
- a small route-bound descriptor wrapper joining one held object to one shared
  pinned descriptor, without exposing the descriptor address;
- intrinsic token acceptance and `SeChangeNotifyPrivilege` policy;
- anchor and dedicated DACL acceptance and enrolled-reader policy;
- exact rights lists and access outcome requirements;
- token recheck placement and phase-specific race mapping;
- v1 reader-identity projection/digest and security-policy/evidence projection;
- final authority rechecks and cleanup precedence; and
- consumer-owned DLL loading and Known Folder binding described above.

It must contain no token-information ctypes layouts or parsers, SID wire
parser, descriptor wire parser, generic-mapping structure, privilege-set
parser, token-handle owner, raw `DuplicateTokenEx`, raw `MapGenericMask`, raw
`AccessCheck`, or descriptor address.

## Exact RED Gate

Before production adaptation, the new tests must fail against the checkpointed
tree for only the absent shared authority. RED must establish at least:

- exact module and `__all__` surface absent;
- import purity and lazy native binding absent;
- base and mandatory-policy token profiles absent;
- class-27 exact DWORD and snapshot-equality cases absent;
- DACL-only and mandatory-label descriptor profiles absent;
- opaque descriptor provenance and same-allocation parsing/checking absent;
- bounded file mapping and opaque access-scope/denial contract absent; and
- an AST containment oracle still finds direct token, descriptor-parser,
  mapping, duplication, and `AccessCheck` mechanics in the external reader.

Do not create a passing placeholder module, copy production code into tests, or
weaken existing external-pin or held-handle oracles to obtain RED.

## GREEN And Parity Gates

The implementation checkpoint is complete only when fresh sequential
`goodq_core` evidence proves:

1. exact shared public surface, standard-library-only import graph, no import-
   time native load, and no `cli` or held-handle import;
2. exact Win64 layouts, active export ABI, missing-export classification, and
   consumer-preserved DLL load/failure order;
3. base 17-call and mandatory-policy 18-call token sequences;
4. class-27 dirty, short, long, reserved-bit, and exact-DWORD handling,
   including structurally valid `0`, `1`, `2`, and `3`;
5. thread-first fallback, baseline/transient rights, statistics fences,
   pointer/buffer/count bounds, exact equality, all four capability-owner copy/
   deepcopy/reduction/pickle rejections, and cleanup quadrants;
6. DACL-only parity and all existing external-pin malformed/unsupported parser
   cases;
7. mandatory-label valid, absent, malformed, overlap, padding, SID, ACL, and
   unsupported-ACE cases;
8. same private descriptor allocation used for parse and `AccessCheck`;
9. exact generic mapping, closed mutation-mask gate, one duplicate per
   descriptor, five-duplicate/19-check external parity, immediate first-
   failure stop, output sentinels, handle-output quadrants, privilege output,
   all grant/deny quadrants, native failure, and cleanup precedence;
10. byte-exact external-pin operation trace, public exports, no-argument API,
    thirteen errors, evidence projection, v1 identity digest, security-policy
    digest, and final cleanup/race ordering;
11. a metamorphic oracle proving otherwise-identical mandatory snapshots with
    values `1` and `3` compare unequal while the external-pin v1 canonical
    projection bytes and SHA-256 remain identical; values `0` and `2` remain
    structurally valid but future-policy rejected, and base remains `None`;
12. proof that external pin never queries class 27 and still rejects every
    SACL-bearing descriptor;
13. a green pre-extraction baseline of the historical 167 held-handle and 477
    external-pin nodes, then a zero-drop coverage receipt mapping every moved
    low-level node to the new shared suite and every retained node to adapter/
    integration coverage; final node counts may change and are recorded in the
    later checkpoint rather than treated as authority;
14. filesystem-observer parity plus the final shared and adapted external-pin
    suites;
15. exact four-file compilation, source containment, documentation authority,
    semantic drift, banned token, dependency, and diff gates; and
16. at least two independent current-byte reviews after all corrections.

Low-level mechanics oracles move to the shared test suite. External-pin tests
retain adapter policy, integration trace, outward bytes, error translation,
failure order, and cleanup parity. Tests must not preserve two production
authorities merely to keep private symbol names stable.

## Rejected Alternatives

- **Parser-only extraction:** requires pointer exposure or a temporary friend
  escape while access remains reader-private.
- **Token-only extraction:** adapts the same retained-token and access cleanup
  graph twice.
- **Copy then migrate later:** creates two mechanics authorities between
  checkpoints.
- **Move the v1 identity projection now:** mixes generic native mechanics with
  clean-memory schema authority and expands the rollback boundary to six files.
- **Import external-pin private helpers:** reverses dependency direction and
  makes a CLI module shared authority.
- **Move held-handle transport:** reopens a completed four-export backend used
  by both filesystem observation and external pin.
- **General access evaluator:** expands a denial-only security witness into an
  authorization capability.
- **Shared policy constants:** leaks GoodQ role, SID, DACL, or accepted-outcome
  authority into a projection-neutral module.

## Evidence Boundary

This decision used repository source/tests, existing checkpoint evidence, and
current official Win32 documentation already recorded by the governing policy
decision. It performed no live token query, ACL read or write, descriptor
inspection, configured-root access, manifest or pin access, service contact,
Qdrant contact, or cleanup action.

## Next Bounded Mission

Implement only the selected four-file mechanics extraction through
RED/GREEN/refactor and exact parity. The protected-manifest reader remains
closed. After the mechanics checkpoint, reassess the separate frozen v1
reader-identity policy seam before authorizing any manifest-reader code.
