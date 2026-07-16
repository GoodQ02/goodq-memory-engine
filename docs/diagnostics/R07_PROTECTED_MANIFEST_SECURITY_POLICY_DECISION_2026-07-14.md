<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# R-07 Protected-Manifest Security-Policy Decision

## Outcome

Select an exact Windows security policy for the already-approved fixed
protected-authority manifest. The policy is deliberately narrower than the
whole GoodQ data route and stronger than a DACL-only check:

1. the independently verified external pin remains the sole content authority;
2. held, no-follow identity and parent-membership evidence binds the projected
   route to one physical candidate root and manifest;
3. only the candidate evidence root and fixed manifest receive an exact
   administrator-owned protected DACL policy; and
4. one immutable filtered descriptor must carry owner, group, DACL, and
   mandatory-integrity-label evidence for exact policy parsing and conservative
   mutation-denial checks; and
5. successful positive access is proved by the real kernel open and same-handle
   read, never by detached authorization replay alone.

This decision does not inspect or change a live root, descriptor, DACL, token,
manifest, pin, service, or protected member. It does not implement enrollment,
publication, security mechanics, the physical reader, planning, approval, or
cleanup.

## Governing Invariant

An accepted manifest must be the exact canonical bytes authorized by the
independent external pin, read from the same held regular-file handle whose
physical identity and selected filtered Windows security state were verified.
The ordinary reader may retain only the minimum authority required to traverse
and read the manifest and to create sibling candidate-plan files. It may not
write, append, replace, delete, relabel, take ownership of, or change policy on
the accepted manifest.

Any unsupported security form, rejected token, policy mismatch, digest
mismatch, or state change fails closed and returns no partial authority.

## No-Repeat Boundary

Keep these completed contracts closed:

- configuration v1 and fixed `candidate_evidence_root` derivation;
- canonical protected-manifest schema, child name, parser, and membership
  projection;
- immutable candidate-plan content and first-writer store behavior;
- shared held-handle identity, enumeration, bounded read, and existing
  owner/group/DACL-only `security_read` profile;
- the no-argument external-pin reader, its exact five-object policy, finite
  errors, evidence schema, and private token/security implementation; and
- external-pin enrollment, publication, and reader cadence.

Do not copy private external-pin symbols, reinterpret its policy as this policy,
move manifest decisions into the shared filesystem backend, or claim that the
existing `security_read` descriptor includes mandatory-label evidence.

## Authority Layers

The trust layers answer different questions and must not be collapsed:

| Layer | Exact authority |
| --- | --- |
| Resolved configuration projection | Selects the logical candidate root and binds routing. It does not authorize manifest bytes. |
| Held no-follow route | Proves fixed local filesystem capability, parent/child membership, object type, physical identity, and race-free traversal. |
| External pin evidence | Authorizes one exact canonical manifest SHA-256 independently of the manifest location and author. |
| Candidate-root policy | Proves the currently observed root has the selected administrator-owned policy and preserves the intended sibling-plan DACL shape. |
| Manifest policy | Proves the currently observed child is administrator-owned and mutation-denied to the ordinary reader. |
| Canonical validator | Proves schema and protected-member meaning only after direct pin comparison. |

The external digest means an attacker who can remove an outer route component
can cause a visible denial of service but cannot authorize different member
bytes. The exact administrator owner and policy prevent a non-elevated process
from freshly manufacturing a policy-valid substitute. They do not prove the
permanent historical identity of the first-published object: a previously
TCB-created exact-policy object could later be relocated into an absent name if
the mover has source-side delete authority. Equal bytes still must match the
independent pin, so this decision establishes current-call content authority and
race safety, not durable publication provenance. Availability is not elevated
into authority.

## Governed Object Set

The physical volume root remains a capability and identity anchor. The existing
backend intentionally cannot read its security descriptor.

Every descendant selected by the projected route through `data_root`,
`control_root`, and `candidate_evidence_root` remains physically governed:

- fixed local NTFS or ReFS volume with open-by-ID support;
- held no-follow traversal, exact parent membership, and supported object kind;
- no redirect, reparse component, name search, path fallback, or caller-selected
  root; and
- complete before/after identity and membership equality while all handles are
  held without delete sharing.

Only these two objects are security-policy governed:

1. the exact `candidate_evidence_root`; and
2. its direct fixed regular-file child `protected-boundaries.json`.

The broader data and control roots are deliberately not assigned a new exact
DACL here. They are existing protected/runtime roots with established ingestion,
control-plane, and service writers. Making every non-TCB ACE on those roots
read-only would break working GoodQ persistence and would exceed the manifest
reader's rollback boundary. Their physical route is still held and rechecked;
the independent digest and exact candidate-root policy prevent a replacement
route from becoming accepted authority.

This paragraph refines the earlier provisional requirement to validate write
authority on every pre-existing parent. Outer-route mutability is a fail-closed
availability risk, not a manifest-content authorization path. The candidate
root and manifest are the first objects whose exact descriptor policy is part
of the reader's trust decision.

## Ordinary-Reader Token Contract

The manifest reader independently applies this complete acceptance policy. Its
canonical reader-identity digest must use the exact unchanged external-pin v1
projection and equal
`ExternalPinEvidence.enrolled_reader_identity_sha256`:

- call `OpenThreadToken(TOKEN_QUERY, OpenAsSelf=TRUE)` first;
- only `ERROR_NO_TOKEN` permits process-token fallback; any discovered thread
  token is `untrusted_reader`;
- accept only a process primary token;
- `TokenUser` is the sole enrolled reader SID present in both exact DACLs;
- `TokenElevation` is false and `TokenElevationType` is exactly `Default` or
  `Limited`, never `Full`;
- `TokenIntegrityLevel` is exactly medium SID `S-1-16-8192` / RID `0x2000`;
- `TokenMandatoryPolicy` contains `TOKEN_MANDATORY_POLICY_NO_WRITE_UP` and no
  unknown bit: the exact accepted values are `0x1` and `0x3`; this field is
  validated and rechecked locally but remains outside the frozen external-pin
  v1 identity projection and digest; the optional
  `NEW_PROCESS_MIN` bit does not affect this process's file access;
- no restricted SID, AppContainer, or UIAccess state is accepted;
- `TokenHasRestrictions` is false for `Default` and true for `Limited`;
- the Administrators SID, when present, is deny-only and not enabled; and
- the only enabled privilege allowed is `SeChangeNotifyPrivilege`. Every other
  privilege, including backup, restore, take-ownership, relabel, impersonate,
  debug, TCB, manage-volume, and symlink privilege, must be disabled.

The complete token snapshot includes user, groups and attributes, restricted
SIDs, privileges and attributes, token type/statistics, elevation, integrity,
mandatory policy, UIAccess, AppContainer, and restriction state. Equal snapshots
bracket route selection, descriptor checks, the content read, pin comparison,
validation, and final return. The reader never requests
`TOKEN_ADJUST_PRIVILEGES`; this contract proves the current effective token, not
resistance to arbitrary malicious code already executing inside the process.

## Selected Filtered-Descriptor Envelope

The future label-aware descriptor transport requests exactly:

```text
OWNER_SECURITY_INFORMATION |
GROUP_SECURITY_INFORMATION |
DACL_SECURITY_INFORMATION |
LABEL_SECURITY_INFORMATION
```

The numeric mask is `0x00000017`. Microsoft specifies that owner, group, DACL,
and mandatory-label queries require `READ_CONTROL`; a full SACL is not requested
and `ACCESS_SYSTEM_SECURITY` is not added. This is intentionally a filtered
descriptor. It omits resource attributes, scoped central-access-policy data,
process-trust or access-filter state, and every other SACL class not returned by
`LABEL_SECURITY_INFORMATION`.

For both governed objects, the filtered self-relative descriptor must have:

- security-descriptor revision `1`;
- control exactly `0xb014`: `SE_SELF_RELATIVE | SE_DACL_PRESENT |
  SE_SACL_PRESENT | SE_DACL_PROTECTED | SE_SACL_PROTECTED`;
- owner and primary group exactly Builtin Administrators
  (`S-1-5-32-544`), with neither defaulted;
- a present, non-null ACL-revision-2 DACL containing only the exact ordered
  ordinary allow ACE vector selected below;
- no deny, object, callback, inherited, `OWNER RIGHTS`, unknown, duplicate, or
  trailing nonzero ACE material; and
- a present, non-null ACL-revision-2 returned mandatory-label ACL containing
  exactly one
  `SYSTEM_MANDATORY_LABEL_ACE_TYPE` (`0x11`), flags `0x00`, mask
  `SYSTEM_MANDATORY_LABEL_NO_WRITE_UP` (`0x1`), and medium-integrity SID
  `S-1-16-8192`.

The protected returned mandatory-label ACL avoids inherited label drift. The
token and both objects are medium integrity, so the selected MIC evidence does
not manufacture a denial later misattributed to the DACL.

This filtered descriptor is not a complete replay of the Windows object
manager's authorization state. Omitted policy can further restrict a real open,
but it cannot grant a mutation right that the exact DACL denies. The accepted
token also lacks every privilege that could bypass the selected file DACL.
Accordingly, detached `AccessCheck` is used only as a conservative bounded
mutation-denial oracle. It is never a general authorization oracle and never
proves a positive grant. Positive access is proved by the actual native open of
the held candidate root or manifest and, for the manifest, the same-handle
bounded read. Querying the full SACL would require
`ACCESS_SYSTEM_SECURITY`/`SeSecurityPrivilege` and would violate the ordinary
reader's least-privilege contract.

## Exact Candidate-Root DACL

The DACL is ordered exactly as follows. All masks are raw object-specific masks;
no generic bit is permitted in an ACE.

| Order | ACE | Trustee | Raw mask | Flags | Meaning |
| ---: | --- | --- | ---: | ---: | --- |
| 1 | allow | Local System `S-1-5-18` | `0x001f01ff` | `0x03` | Full control, object and container inherit. |
| 2 | allow | Builtin Administrators `S-1-5-32-544` | `0x001f01ff` | `0x03` | Full control, object and container inherit. |
| 3 | allow | exact enrolled reader SID | `0x001200a3` | `0x00` | List, traverse, read attributes/control, synchronize, and add direct child file. |
| 4 | allow | Creator Owner `S-1-3-0` | `0x0013019f` | `0x0d` | Object-inherit, no-propagate, inherit-only read/write/delete for direct child files. |

Flags `0x03` are `OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE`. Flags `0x0d`
are `OBJECT_INHERIT_ACE | NO_PROPAGATE_INHERIT_ACE | INHERIT_ONLY_ACE`.
Windows replaces the Creator Owner placeholder with the creating SID when the
ACE is inherited. The ACE is not effective on the candidate root and does not
propagate beyond the direct child.

## Exact Manifest DACL

The fixed manifest DACL has no inheritable or inherited ACE:

| Order | ACE | Trustee | Raw mask | Flags |
| ---: | --- | --- | ---: | ---: |
| 1 | allow | Local System `S-1-5-18` | `0x001f01ff` | `0x00` |
| 2 | allow | Builtin Administrators `S-1-5-32-544` | `0x001f01ff` | `0x00` |
| 3 | allow | exact enrolled reader SID | `0x00120089` | `0x00` |

No fourth ACE is accepted. The reader is neither the object owner nor an
enabled Administrator, so the owner's implicit `WRITE_DAC` rule cannot grant it
policy authority.

## Fixed Generic Mapping And Access Outcomes

Use exactly one file-object `GENERIC_MAPPING`:

| Field | Raw mask |
| --- | ---: |
| `GenericRead` | `0x00120089` |
| `GenericWrite` | `0x00120116` |
| `GenericExecute` | `0x001200a0` |
| `GenericAll` | `0x001f01ff` |

Preserve every raw mask for evidence. Map a detached checking copy with
`MapGenericMask`, reject unknown or remaining generic bits, and call
`AccessCheck` with explicit mutation masks only. `MAXIMUM_ALLOWED` and
caller-selected masks are forbidden.

The selected DACL outcomes are:

| Object | Filtered simulation expected grant | Must deny individually |
| --- | --- | --- |
| candidate root | `0x001200a3` | `FILE_ADD_SUBDIRECTORY (0x4)`, `FILE_WRITE_EA (0x10)`, `FILE_DELETE_CHILD (0x40)`, `FILE_WRITE_ATTRIBUTES (0x100)`, `DELETE (0x10000)`, `WRITE_DAC (0x40000)`, `WRITE_OWNER (0x80000)` |
| fixed manifest | `0x00120089` | `FILE_WRITE_DATA (0x2)`, `FILE_APPEND_DATA (0x4)`, `FILE_WRITE_EA (0x10)`, `FILE_WRITE_ATTRIBUTES (0x100)`, `DELETE (0x10000)`, `WRITE_DAC (0x40000)`, `WRITE_OWNER (0x80000)` |

Each denied right is checked separately. Windows permits deletion or source-side
rename when either the child grants `DELETE` or its parent grants
`FILE_DELETE_CHILD`; both are denied for the fixed manifest. `FILE_ADD_FILE` on
the root does not overwrite an already-existing protected child.

`AccessCheck` API failure is `observation_failed`, never evidence of denial. A
successful denial check must have internally consistent `AccessStatus` and
`GrantedAccess`. Every accepted denial check must return `PrivilegeCount == 0`.
The fixed `PRIVILEGE_SET` implementation is therefore a bounded DACL, owner,
current-token, and current-privilege mutation-denial verifier, not a positive or
general arbitrary-mask access engine.

The reader separately proves its required positive access by successfully
opening each governed object with exact native desired access `0x00020081`
(`READ_CONTROL | FILE_READ_DATA/FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES`).
The manifest's successful bounded same-handle read is additional positive
evidence. Availability of `FILE_ADD_FILE` for `CandidatePlanStore` is not probed
by this passive reader; a later test-owned persistence/integration witness must
prove its create, no-replace rename, and owned-temp cleanup path.

## CandidatePlanStore Coexistence

The candidate root is intentionally shared with the completed
`CandidatePlanStore`. Making the whole root read-only would break its established
lock, temporary-file, no-replace publication, and owned-temp cleanup behavior.

The selected root DACL is designed to preserve that behavior without exposing
the manifest; the later persistence witness remains the positive compatibility
gate:

- `FILE_ADD_FILE` permits direct sibling file creation;
- the Creator Owner inherit-only ACE gives the creator of a direct plan, lock,
  or temporary file `0x0013019f`—file generic read, file generic write, and
  child `DELETE`;
- parent `FILE_DELETE_CHILD` remains denied; and
- the protected manifest inherits nothing and grants no write or delete right.

This is not an OS-level immutability guarantee for candidate-plan children. A
creator owns and can modify or delete its own files. The completed store's
immutability remains a content/first-writer contract; changing its post-publish
ACL or authority is a separate R-07 seam and is not smuggled into this reader
decision.

## Enrollment And First-Publication Constraint

`FILE_ADD_FILE` is name-agnostic. No DACL can both permit arbitrary sibling plan
creation and reserve an absent `protected-boundaries.json` name for another
writer. A policy-valid deployment therefore uses this staged TCB operation:

1. an elevated enabled Administrator or Local System exclusively creates the
   candidate root with a temporary TCB-only protected policy;
2. while the ordinary reader still has no add-file right, the publisher creates
   a same-directory manifest temporary file with an explicit protected final
   descriptor from birth, validates canonical bytes, flushes, and publishes by
   no-replace rename;
3. the publisher reopens by physical identity and verifies exact content,
   owner, group, DACL, mandatory label, parent membership, and external-pin
   separation; and
4. only after the fixed manifest is accepted does it install and reverify the
   complete final candidate-root envelope: physical identity, parent membership,
   owner, group, exact `0xb014` control, DACL, and returned mandatory label.

The manifest temporary file must not first inherit the Creator Owner ACE and be
hardened later. Same-volume rename preserves the source file's security
descriptor. An existing root produced under default security, an existing fixed
child, or any foreign first writer encountered by this workflow is preserved and
fails closed for separate operator recovery; automatic adoption or deletion is
forbidden.

The selected reader policy protects an already-present manifest. It does not
authorize enrollment, first publication, rotation, replacement, deletion, or
recovery. It also cannot prove the permanent historical identity of that first
publication. Durable provenance would require a separately pinned physical
identity or enrollment record, which is not selected here. Rotation remains
closed.

## Threat And Action Matrix

This matrix records the selected DACL design. Positive cells still require the
kernel or persistence witnesses defined above; detached simulation alone does
not close them.

| Actor/action | Candidate root | Own direct plan child | Fixed manifest |
| --- | --- | --- | --- |
| Local System / elevated enabled Administrator | Full OS capability; separate workflow approval still required | Full | Full OS capability; no v1 rotation workflow |
| Exact ordinary reader: traverse/read | Grant | Grant | Grant |
| Ordinary reader: create direct file | Designed grant after first publication; later persistence witness required | Grant only after that witness | Cannot create over existing child |
| Ordinary reader: create subdirectory | Deny | Not applicable | Not applicable |
| Ordinary reader: write/append | Deny on root object | Grant | Deny |
| Ordinary reader: delete/rename | Deny root | Grant through child `DELETE` | Deny leaf and parent route |
| Ordinary reader: change DACL/owner | Deny | Creator owns its child | Deny |
| Unenrolled non-TCB principal | No ACE | Only if separately creator-authorized | No ACE |

TCB capability is not GoodQ workflow authorization. Every future mutation still
requires its own exact operation, scope, confirmation, durable audit, and
recovery contract.

## Required Reader Failure Order

The later physical reader must preserve this exact high-level order:

1. validate exact direct configuration and external-pin evidence types,
   private bytes/projections, and digests before I/O;
2. prove Windows, fixed NTFS/ReFS, open-by-ID, label-aware filtered-descriptor,
   token, generic-mapping, and bounded denial-check capability;
3. capture and accept the baseline process token and match the external-pin
   reader-identity digest;
4. hold the volume anchor and walk the projected route one child at a time,
   no-follow, with complete membership evidence;
5. select the candidate root through the successful exact native open, then
   validate its filtered-descriptor structure, exact static policy, mandatory
   label, and bounded mutation-denial outcomes;
6. select only the fixed manifest child; require a non-reparse regular file,
   link count one, one unnamed stream, and stable metadata;
7. validate manifest filtered-descriptor structure, exact policy, mandatory
   label, and bounded mutation-denial outcomes before trusting content;
8. require initial size `1..4_194_304`, read once from the same handle with
   `initial_size + 1`, require EOF and exact size, and resnapshot immediately;
9. hash those exact bytes and compare directly with the external pin before any
   UTF-8 decode, JSON parse, or schema validation;
10. invoke the shared canonical validator on those same bytes and cross-check
    its digest;
11. recheck direct inputs, full token, every selected filtered-descriptor byte
    string, static policy and bounded denial results, object snapshots,
    stream/link state, and complete parent enumerations; and
12. return immutable evidence, then close in reverse order without replacing a
    primary failure.

Failure classification is exact:

- unavailable ABI or structurally valid but unselected control/ACL/ACE form:
  `unsupported_security`;
- malformed native structure, output, bounds, or impossible status:
  `observation_failed`;
- rejected effective token: `untrusted_reader`;
- structurally supported but wrong owner, group, control, DACL, label, ACE,
  trustee, mask, flag, or access result: `security_policy_mismatch`;
- any change after acceptance: `observation_raced`; and
- digest mismatch wins before every manifest decode/parser error.

Cleanup failure remains secondary to an existing primary failure and prevents a
successful return.

## Projection-Neutral Mechanics Boundary

After label transport is checkpointed, a separate extraction may provide only:

- lazy, pointer-width-exact Win32 token, descriptor, ACL/ACE, generic mapping,
  duplication, and `AccessCheck` bindings;
- bounded immutable token snapshots and exact equality, including integrity and
  mandatory policy;
- a bounded self-relative filtered-descriptor parser returning owner, group,
  control, DACL revision and ordered raw ACEs, plus the selected returned
  mandatory-label ACL;
- one pinned immutable descriptor buffer shared by parsing and `AccessCheck`;
- the fixed file `GENERIC_MAPPING`, mapped checking copies, and raw-mask
  preservation;
- one explicit mutation-mask access operation returning a validated denial
  result and zero-privilege witness; and
- generic malformed-versus-unsupported internal errors.

It must contain no candidate-chain roles, fixed child name, trusted SID, token
acceptance policy, DACL sequence, access outcome, manifest error code, evidence
schema, or security-policy digest construction. The manifest reader owns those
decisions. Existing private external-pin helpers remain private until a later
parity adaptation explicitly proves both consumers unchanged.

## Mandatory Next Prerequisite

The existing shared backend's `security_read` profile requests only owner,
group, and DACL (`0x7`). Its exact behavior is checkpointed and the external-pin
parser rejects SACL content. It must remain byte-for-byte unchanged.

The smallest next seam is a two-file TDD extension:

- add opt-in profile `security_read_label` to
  `steps/common/windows_held_handle.py`; and
- extend only `tests/unit/test_windows_held_handle.py`.

The new profile uses the same `READ_CONTROL` descendant open mask, held-handle
ownership, native ABI, detached-copy validation, bounds, cleanup, and public
`read_security_descriptor()` method. Only its `GetSecurityInfo` request changes
to `0x17`. The default `observation` profile and existing `security_read`
profile/call mask `0x7` remain exact. The volume root stays security-unreadable.

RED must prove the absent profile and `0x17` request first. GREEN must freeze
profile validation, exact ABI and open rights, detached label-bearing bytes,
existing `0x7` parity, foreign/closed/root rejection, structural validation,
allocation cleanup, native-failure precedence, public-surface exactness, and
unchanged observer/external-pin suites. A Windows-only test-owned temporary-file
witness must also execute the real held-handle `GetSecurityInfo(..., 0x17)` path
and prove successful detached transport and cleanup without reading or changing
any configured or production ACL. No token, policy parser, `AccessCheck`, reader,
or publication implementation belongs in that seam.

That native transport witness does not prove the selected exact `0xb014` control
and ACE envelope. The policy remains unsupported for deployment until a later
TCB-owned, test-only enrollment/integration witness establishes that exact form
and the `CandidatePlanStore` persistence path. Synthetic exact-policy bytes may
freeze parser behavior but cannot replace that native witness.

## Official Platform Evidence

- [GetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo)
- [SECURITY_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/secauthz/security-information)
- [Mandatory Integrity Control](https://learn.microsoft.com/en-us/windows/win32/secauthz/mandatory-integrity-control)
- [SYSTEM_MANDATORY_LABEL_ACE](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-system_mandatory_label_ace)
- [SYSTEM_RESOURCE_ATTRIBUTE_ACE](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-system_resource_attribute_ace)
- [Central access policies](https://learn.microsoft.com/en-us/windows-server/identity/solution-guides/scenario--central-access-policy)
- [TOKEN_INFORMATION_CLASS](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ne-winnt-token_information_class)
- [TOKEN_MANDATORY_POLICY](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-token_mandatory_policy)
- [AccessCheck](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-accesscheck)
- [MapGenericMask](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-mapgenericmask)
- [File access rights](https://learn.microsoft.com/en-us/windows/win32/fileio/file-access-rights-constants)
- [MoveFileEx](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw)
- [Order of ACEs in a DACL](https://learn.microsoft.com/en-us/windows/win32/secauthz/order-of-aces-in-a-dacl)
- [ACE inheritance rules](https://learn.microsoft.com/en-us/windows/win32/secauthz/ace-inheritance-rules)
- [Well-known SIDs](https://learn.microsoft.com/en-us/windows/win32/secauthz/well-known-sids)
- [Security-descriptor control](https://learn.microsoft.com/en-us/windows/win32/secauthz/security-descriptor-control)
- [Owner of a new object](https://learn.microsoft.com/en-us/windows/win32/secauthz/owner-of-a-new-object)
- [Privilege constants](https://learn.microsoft.com/en-us/windows/win32/secauthz/privilege-constants)

Context7 resolved the official Win32 reference as
`/websites/learn_microsoft_en-us_windows_win32_api`; direct Microsoft Learn
checks supplied the mandatory-label, token-policy, inheritance, ownership, and
delete/rename details above.

## Review And Evidence Boundary

Three independent read-only reviews traced existing security-mechanics
ownership, official Windows authorization semantics, CandidatePlanStore
coexistence, token and descriptor requirements, and the threat/action matrix.
Two adversarial current-byte re-reviews returned `READY` after the decision was
narrowed to filtered-descriptor mutation denial, native positive-access proof,
explicit publication-provenance limits, and a test-owned native transport
witness. The reviewed SHA-256 was
`677061FC5BF278DFBE578B27B6D529052B7A2C11EB3E2ED89E75C87E4DF005AD`.

No live ProgramData, pin, manifest, token, ACL, configured/protected root,
service, GoodQ data, Qdrant, evidence store, job, MiniAgent, or cleanup target
was read or changed while selecting this policy.
