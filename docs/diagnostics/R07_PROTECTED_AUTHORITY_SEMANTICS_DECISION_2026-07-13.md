<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-07 Protected-Authority Semantics Decision

## Status

This decision completes the exact manifest-member and external-pin policy beneath
the operator-approved source model recorded in
`docs/diagnostics/R07_PROTECTED_AUTHORITY_SOURCE_DECISION_2026-07-13.md`.
It is an engineering contract only. It does not create, read, publish, rotate,
or recover a manifest or pin, and it does not inspect any configured or live
protected member.

The approved invariant is unchanged:

> The manifest supplies protected-member content. One independently protected
> external pin authorizes only the canonical manifest bytes having its exact
> digest. Neither source authenticates itself or supplies the other source's
> content.

R-07 planning remains fail closed until the selected pure projection, readers,
platform security backend, observer, and production orchestration are separately
implemented and verified.

## No-Repeat Findings

The completed `goodq.clean-memory-configuration.v1` projection already binds the
exact resolved routing topology and its SHA-256. It does not prove whether an
environment value, local overlay, bootstrap rewrite, or caller override supplied
that topology. Reopening v1 to add source labels would repeat and invalidate the
configuration checkpoint.

The exact compatible rule is therefore:

> Resolved configuration is locator and routing scope, never protected-member
> authorization.

The external pin authenticates the manifest bytes. The non-authoritative
membership projection digest binds those bytes and their parsed membership to
the existing configuration digest. Future authenticated composition binds the
verified pin-reader result to that projection. A routing change therefore
creates a different membership scope and invalidates every prior plan, approval,
and job scope without pretending that the configuration digest proves origin.

The completed filesystem observer contains useful target-specific platform
patterns but no reusable protected-authority reader or security-policy backend.
Private observer symbols may not be imported or copied.

## Canonical Manifest Contract

### Logical location

The one manifest child remains:

```text
<candidate_evidence_root>/protected-boundaries.json
```

The relative child is constant. The absolute `candidate_evidence_root` may move
only as resolved routing inside the already-bound v1 configuration projection;
that movement changes the configuration and membership digests and grants no
membership authority. No configuration field, environment value, CLI argument,
caller mapping, manifest field, sibling file, or search fallback may override
the constant child or bypass the v1-resolved root.

### Byte and JSON rules

The manifest is one regular file whose complete content is canonical UTF-8 JSON:

- minimum size: one byte;
- maximum size: 4,194,304 bytes;
- no byte-order mark, comments, trailing newline, trailing whitespace, or
  concatenated value;
- duplicate object keys are rejected while parsing;
- object keys use the repository's existing canonical encoding: Unicode output,
  no non-finite numbers, lexicographically sorted keys, and compact separators;
- every string is NFC-normalized and contains no control or delete character;
- the parsed value must re-encode byte-for-byte to the bytes read from the same
  held handle; and
- SHA-256 covers those exact bytes. The manifest contains no self-hash.

The size and count limits are v1 protocol limits, not claims about operating-
system maxima. They bound memory use before JSON parsing and support the complete
member census below.

### Exact schema

Top-level keys are exactly `schema` and `roles`. This abridged structural
example shows one role; a valid manifest contains the complete ordered eight-
role census specified immediately below:

```json
{
  "roles": [
    {
      "members": [
        {
          "absolute_path": "<canonical-local-absolute-path>",
          "member_id": "primary",
          "object_kind": "directory",
          "presence": "required"
        }
      ],
      "role": "backup_root"
    }
  ],
  "schema": "goodq.clean-memory-protected-authority.v1"
}
```

`roles` contains exactly these eight records in this order:

1. `backup_root`
2. `download_cache`
3. `public_checkout`
4. `qdrant_service_logs`
5. `recovery_root`
6. `reports_root`
7. `repository`
8. `source_media`

Each role record has exactly `role` and `members`. Each role has between 1 and
64 members. The manifest therefore has between 8 and 512 members total.

Each member has exactly:

- `member_id`: explicit operator-selected ASCII identifier matching
  `[a-z][a-z0-9_]{0,63}`;
- `absolute_path`: exact canonical local absolute path, at most 4,096 UTF-8
  bytes;
- `object_kind`: exactly `directory`; and
- `presence`: exactly `required` or `allow_absent`, with no default.

Member IDs are unique within their role and sorted in ascending byte order.
Unsorted or duplicate IDs are rejected rather than normalized. The selector
cannot prove how a syntactically valid ID was chosen. The later authoring command
must therefore require an explicit operator-provided ID and must never synthesize
one from a path or ordinal; that is an authoring/review rule, not a parser claim.
Supporting a manifest-protected regular file or another object kind requires a
later schema decision.

`required` means the later observer must return a present object of the exact
kind. `allow_absent` means the later observer may instead return the approved
stable-absence proof. It never permits an omitted role/member, inaccessible
object, missing parent, unsupported filesystem, redirect, wrong kind, or race.
Presence is explicit per member so the reviewed and pinned manifest—not a role
default or current existence—selects that policy.

### Canonical paths and duplicates

The selector applies the completed configuration projection's `path_flavor` to
every path and accepts only its canonical spelling:

- one local absolute path flavor for the complete 18-role census;
- forward separators, NFC text, no unresolved environment reference, no empty,
  dot, or dot-dot component, no trailing separator, and no repeated separator;
- uppercase Windows drive letter, no UNC/device namespace, alternate drive-root
  spelling, reserved component, trailing dot/space, or case alias; and
- no normalization on acceptance: if canonicalization would change the source
  string, membership validation rejects it.

Before its first filesystem call, the later orchestration rejects exact path
duplicates and Windows comparison aliases within or across all 18 roles. It
also rejects a manifest member already assigned to a configured role and any
manifest member overlapping a cleanup target or `candidate_evidence_root`.

Do not reject every protected ancestor/descendant relationship. The configured
`data_root` and `control_root` intentionally contain protected and evidence
subtrees. Exact duplicate ownership and destructive-scope overlap are invalid;
intentional protected containment is not.

## Configured-Role Compatibility Contract

The manifest cannot add to or override the ten configured roles. The pure
membership projection consumes the exact completed `ResolvedPlanConfiguration`, verifies its
canonical bytes and SHA-256, and converts its existing ordered role/path lists
using this built-in table:

| Configured role | Members | Kind | Presence |
| --- | --- | --- | --- |
| `archive_root` | `configured_00` | `directory` | `allow_absent` |
| `control_root` | `configured_00` | `directory` | `required` |
| `data_root` | `configured_00` | `directory` | `required` |
| `failed_media` | `configured_00` | `directory` | `allow_absent` |
| `import_media` | `configured_00` | `directory` | `allow_absent` |
| `model_cache` | `configured_00` | `directory` | `allow_absent` |
| `processed_media` | `configured_00` | `directory` | `allow_absent` |
| `processing_media` | `configured_00` | `directory` | `allow_absent` |
| `qdrant_storage` | `configured_00` | `directory` | `allow_absent` |
| `watchdog_state` | `configured_00`, `configured_01` | `regular_file` | `allow_absent` |

The two required directories are structural prerequisites of the fixed manifest
locator. Optional runtime/cache/media directories and watchdog files remain
protected lexically even when stably absent.

The v1 projection deliberately stores the watchdog pair as a sorted path list
without retaining its source-field labels. Reopening v1 merely to recover
`lock_file` and `state_file` names is prohibited. `configured_00` and
`configured_01` therefore mean positions in that immutable canonical list and
are valid only under the bound `configuration_scope_sha256`. Any configured
path change creates a new membership digest, so these compatibility IDs are not
claimed to survive a routing change.

The selector produces exactly one role record for each of all 18 roles. The
role-level logical ID is exactly `protected:<role>` with underscores preserved.
The composite-envelope member logical ID is
`protected:<role>:<member_id>`. Candidate planning continues to receive exactly
one `ProtectedBoundaryEvidence` per role.

## Pure Membership Projection Contract

The first detached projection is deliberately non-authoritative. Its schema is
`goodq.clean-memory-protected-membership.v1`. This abridged structural example
shows one role; a valid projection contains the complete ordered 18-role census
specified immediately below, with exactly the nested object keys shown:

```json
{
  "configuration_scope_sha256": "<64-lowercase-hex>",
  "manifest": {
    "child_name": "protected-boundaries.json",
    "sha256": "<64-lowercase-hex>"
  },
  "path_flavor": "windows",
  "protected_roles": [
    {
      "members": [
        {
          "absolute_path": "<canonical-local-absolute-path>",
          "member_id": "configured_00",
          "object_kind": "directory",
          "presence": "allow_absent"
        }
      ],
      "role": "archive_root"
    }
  ],
  "schema": "goodq.clean-memory-protected-membership.v1"
}
```

Every nested object has exactly the keys shown. `protected_roles` contains
exactly this canonical candidate-plan census order from
`PROTECTED_BOUNDARY_ROLES`:

1. `archive_root`
2. `backup_root`
3. `control_root`
4. `data_root`
5. `download_cache`
6. `failed_media`
7. `import_media`
8. `model_cache`
9. `processed_media`
10. `processing_media`
11. `public_checkout`
12. `qdrant_service_logs`
13. `qdrant_storage`
14. `recovery_root`
15. `reports_root`
16. `repository`
17. `source_media`
18. `watchdog_state`

Members retain the configured or manifest ordering already selected above. The
immutable object exposes `protected_membership_scope_sha256`, computed over the
canonical projection but not embedded inside it. Raw paths remain only in this
detached in-process object and must not enter candidate-plan output, ordinary
logs, audit messages, API errors, or pin data.

The projection requires the exact `ResolvedPlanConfiguration` type, unchanged
canonical bytes and digest, canonical manifest bytes, and the exact role/member,
limit, flavor, order, presence, kind, and lexical-uniqueness rules above. It
rechecks every immutable input before returning. Mappings, subclasses,
self-declared provenance labels, and caller-provided `no_overrides` flags are
rejected.

This projection proves structure and digest consistency only. It does not
consume pin evidence, compare against the external trust root, or authorize
membership. A Python type, supplied digest, or prebuilt membership projection
cannot prove that either reader ran. Authenticated selection remains closed
until the platform reader/enrollment evidence schema is separately selected.

The projection performs no configuration load, filesystem operation, network
call, process action, persistence, plan construction, job/token work, MiniAgent
call, or cleanup.

## Resolved-Configuration Entry Contract

A future production `plan` edge may accept only one exact epoch identifier. It
must expose no configuration mapping/file, local-overlay, data-root, evidence-
root, manifest-path, pin-path, digest, source-ID, member, or override argument.

That edge must lazily call `load_configs(None)` exactly once, immediately create
the unchanged v1 projection, invoke the approved pin and manifest readers
itself, and pass their direct outputs through membership validation and the
later authenticated composition gate. It may accept no caller-built reader
evidence, membership projection, or prebuilt selection. Environment, local
YAML, bootstrap, and runtime state may legitimately influence routing before
projection, but they never authorize pin identity or manifest members.

Any routing change yields a different configuration and membership digest.
Existing observer output, candidate plan, approval, token, or job evidence may
not be reused. The runtime must never search for a manifest when the fixed child
fails and must never accept a caller assertion that overrides were absent.

## External Pin Trust Root

### Logical source and payload

The one source has:

- schema: `goodq.clean-memory-external-pin-source.v1`;
- source ID: `goodq.clean-memory-protected-authority-pin.primary.v1`;
- constant child: `protected-boundaries.sha256`; and
- exact payload: 64 lowercase ASCII hexadecimal characters followed by one LF,
  for 65 bytes total.

It contains no path, member data, source ID, author, timestamp, self-hash,
fallback, or second digest. Source identity comes only from the statically
selected platform locator and independently verified physical/security state.

### Platform locators

The one logical source maps statically by platform:

- Windows: the actual `FOLDERID_ProgramData` Known Folder returned by the shell
  Known Folder API, followed by constant child components
  `GoodQ/authority/clean-memory/protected-boundaries.sha256`;
- POSIX reserved locator:
  `/etc/goodq/authority/clean-memory/protected-boundaries.sha256`.

Environment expansion, configuration, CWD, repository/Git discovery, CLI or
caller input, manifest content, sibling search, and fallback are forbidden.
Windows v1 supports only a `DRIVE_FIXED` NTFS or ReFS volume that reports
`FILE_SUPPORTS_OPEN_BY_FILE_ID`, permits the proven held-handle/open-by-ID
contract, and has no redirect or reparse component. A missing capability fails
`unsupported_filesystem`; it never falls back to pathname-only traversal.

The POSIX locator is reserved for schema portability but is not enabled in v1.
Enrollment, reading, and publication return `unsupported_platform` until a
separate audit selects exact local-filesystem, ACL, capability, credential, and
descriptor-relative support oracles. POSIX prose below records the minimum
future policy and grants no current authority.

Lexical pin/member disjointness cannot be proven by the pure membership
projection because the Known Folder location is runtime-resolved. Future
production orchestration performs that check with its internally resolved pin
locator after manifest authentication and before protected observation. The
observer then compares pin-chain physical identities with every protected
parent/member identity before authenticated composition succeeds.

### Dedicated trust-root enrollment

Enrollment is a separate Windows administrator mutation and precedes first pin
publication. It accepts only one explicit, operator-reviewed canonical reader
SID. It accepts no path, digest, manifest, member, configuration, environment,
display-name, or discovery input. The elevated administrator's review of that
numeric SID is the enrollment authorization; the SID is never inferred from an
environment value or the elevated token.

The enrollment command must:

1. resolve `FOLDERID_ProgramData` through the Known Folder API and prove the
   exact fixed-volume/filesystem/open-by-ID support boundary above;
2. bind and recheck the effective elevated token, stable volume/anchor identity,
   anchor owner, and effective access policy, rejecting any non-TCB ability to
   delete or replace the dedicated child through its parent;
3. create each missing constant dedicated-directory component exclusively,
   no-follow, and without replacing a foreign first writer;
4. apply the exact owner/protected-DACL policy below before exposing the next
   child;
5. flush directory metadata, reopen every component by stable identity, and
   verify owner, DACL, parent membership, and effective writer token; and
6. on repeat invocation, act as verify-only when the full existing chain exactly
   matches the enrolled reader SID and policy, otherwise fail closed and preserve
   every object.

The reader SID is stored only as the exact ACE in the secured DACL. There is no
adjacent self-declared enrollment metadata. Enrollment creates no pin. Pin
publication remains the second, separately approved administrator action.

### Effective identity and security policy

Security decisions use numeric identities only—SIDs on Windows and UID/GID on
POSIX. Display names are never authority.

On Windows:

- use the thread impersonation token when present and the process token only on
  `ERROR_NO_TOKEN`;
- bind and recheck the user SID, enabled/deny-only group attributes, restricted
  state, integrity/elevation state, impersonation level, and enabled privileges
  around every operation;
- ordinary reading requires the exact enrolled operator SID, a non-elevated
  token, no unexpected impersonation, and no enabled write-bypass, restore, or
  take-ownership privilege;
- the dedicated `GoodQ/authority/clean-memory` chain and pin file have protected,
  non-null DACLs with inheritance disabled and no unrecognized ACE;
- owner is the built-in Administrators SID;
- SYSTEM and built-in Administrators receive full control;
- the exact enrolled operator SID receives only list/traverse/read-attributes,
  `READ_CONTROL`, and synchronization on the dedicated directories, and only
  read-data/read-EA/read-attributes, `READ_CONTROL`, and synchronization on the
  pin file; and
- every other principal receives no access through the protected DACL.

First publication runs only as SYSTEM or an elevated enabled member of the
built-in Administrators SID. The ordinary manifest author/runtime reader cannot
mutate, delete, replace, take ownership of, or change the DACL on the pin parent
or file without crossing that explicit OS-administrator trust boundary.

For a later POSIX support decision, the minimum policy is:

- the dedicated chain is root-owned, uses the exact enrolled runtime-reader
  group, and has mode `0750` with no extended ACL or group/other write authority;
- the pin is a root-owned regular file with the same reader group, mode `0440`,
  link count one, and no extended ACL;
- reading binds and rechecks effective UID/GID, supplementary groups,
  capabilities, and any impersonation-equivalent state; and
- an ordinary reader with a mutation-bypass capability is rejected. First
  publication is root-only.

The enrolled Windows operator SID would become part of future verified
path-free pin-source evidence. Enrollment and first publication remain later
explicit host mutations; no value is inferred or created by this decision.

### Reader evidence boundary

The held-handle reader must eventually return canonical path-free evidence that
binds:

- fixed source ID and platform tag;
- path-free stable anchor, dedicated-parent, and pin-file physical identities;
- the enrolled reader identity digest;
- the exact security-policy digest; and
- the manifest SHA-256 read from the same verified pin handle.

The reader verifies security before trusting content, reads the 65 bytes from
the same held handle, then rechecks effective identity, file/parent physical
identity, security state, content metadata, and parent membership. Unsupported
token/ACL/credential/capability, no-follow, local-filesystem, stable-identity,
or security-revalidation capability fails closed with a finite path-free error.

This decision deliberately does not invent the final reader-evidence JSON or
security-policy digest preimage. That exact schema belongs to the next Windows
enrollment/reader boundary audit and must bind proven platform identity and
security-descriptor records, not caller-supplied hashes. Consequently the first
pure membership implementation consumes no pin evidence and cannot create an
authenticated selection.

## Publication, Rotation, and Recovery

Manifest authoring and pin authorization are separate operator actions. A
manifest author may produce and review canonical candidate bytes and digest but
cannot change the pin. Planning may create neither source.

Pin v1 supports first publication only on the selected Windows backend:

1. verify the effective elevated writer and already-existing secured dedicated
   parent;
2. create a unique same-parent regular temporary file exclusively and no-follow;
3. write exactly 65 bytes, flush content, apply and verify final owner/security;
4. reread from the same held handle;
5. publish atomically without replacing an existing child;
6. flush directory metadata and re-open the child no-follow;
7. verify content, physical identity, owner, DACL/ACL, parent membership, and
   effective writer identity; and
8. preserve a foreign first writer and remove only a temporary object whose
   exact physical identity this operation created.

If durable no-replace publication is unsupported, publication is unsupported.
The current path-based candidate-plan evidence writer is an oracle for
first-writer behavior, not a reusable pin writer.

Pin rotation is deliberately unsupported in v1. A missing, malformed,
replaced, redirected, multiply linked, security-drifted, or digest-mismatched
pin fails closed and preserves every byte. Post-publication uncertainty returns
`manual_recovery_required`. There is no automatic delete/recreate, backup,
sibling fallback, adoption, manifest rewrite, or pin rewrite.

Adding compare-and-swap rotation and rollback protection requires a later
explicit operator decision, separate platform-capability audit, RED oracle, and
checkpoint. Until then, changing protected membership is not a runnable cleanup
operation; it requires an independently reviewed authority re-enrollment path.

## Observer Handoff and Structural Absence

The protected observer must receive the complete immutable membership projection
plus internally held verified pin-chain exclusion identities before its first
protected-member filesystem operation. It returns no partial evidence and
produces exactly one canonical path-free composite envelope per role:

```json
{
  "logical_id": "protected:<role>",
  "members": [
    {
      "absence": null,
      "child_comparison_sha256": "<64-lowercase-hex>",
      "logical_id": "protected:<role>:<member_id>",
      "member_id": "<member_id>",
      "object_identity": {
        "schema": "<approved-platform-file-identity-schema>"
      },
      "object_kind": "directory",
      "parent_identity": {
        "schema": "<approved-platform-file-identity-schema>"
      },
      "state": "present"
    }
  ],
  "protected_membership_scope_sha256": "<64-lowercase-hex>",
  "role": "<role>",
  "schema": "goodq.clean-memory-protected-boundary-identity.v1"
}
```

Top-level and member objects have exactly the keys shown. Members are ordered by
member ID. `parent_identity` and a present `object_identity` are canonical
objects using the already approved platform file-identity schema. The
`child_comparison_sha256` is SHA-256 of the canonical UTF-8 comparison key for
the final component: exact NFC bytes on POSIX and NFC casefolded bytes on
Windows. It binds the child without emitting the name.

For a present member, `state` is `present`, `object_identity` is non-null, and
`absence` is null. For an absent member, `state` is `absent`,
`object_identity` is null, and `absence` has exactly:

```json
{
  "after_membership_sha256": "<64-lowercase-hex>",
  "before_membership_sha256": "<64-lowercase-hex>",
  "schema": "goodq.clean-memory-stable-absence.v1"
}
```

Both membership digests must be equal and cover the canonical ordered,
path-free parent membership snapshot. Before hashing, each complete enumeration
is encoded exactly as:

```json
{
  "entries": [
    {
      "comparison_name_sha256": "<64-lowercase-hex>",
      "entry_identity": {
        "file_id": "<16-lowercase-hex>",
        "file_id_kind": "ntfs_file_index_64",
        "platform": "windows",
        "schema": "goodq.clean-memory-directory-entry-identity.v1",
        "volume_serial": "<16-lowercase-hex>"
      },
      "entry_kind": "regular_file"
    }
  ],
  "schema": "goodq.clean-memory-parent-membership.v1"
}
```

Each object has exactly the shown keys. `entry_kind` is exactly `directory`,
`regular_file`, `redirect`, `device`, or `other`. The comparison-name digest
uses the same canonical final-component bytes defined above. Entries are sorted
by that digest, and duplicate comparison-name digests are rejected.

For Windows, `entry_identity` has the exact schema above and uses either
`ntfs_file_index_64` with 16 lowercase hexadecimal file-ID characters or
`refs_file_id_128` with 32; identity is the complete
`(volume_serial, file_id_kind, file_id)` tuple. For a later enabled POSIX
backend, `entry_identity` instead has exactly `schema`, `platform`, `device`,
and `inode`, with schema `goodq.clean-memory-directory-entry-identity.v1`,
platform `posix`, and nonnegative decimal device/positive decimal inode strings.

The observer compares the complete before/after canonical snapshot bytes and
requires equality before emitting their equal SHA-256 values. The surrounding
member already binds the held parent identity and comparison child digest, so
two absent aliases beneath the same physical parent produce the same alias key
and are rejected globally.

For `allow_absent`, stable absence requires a present, held, supported immediate
parent; two complete no-follow parent enumerations bracketing the observation;
absence of the exact canonical child in both; unchanged parent/configuration/
authority identity; and a final membership recheck. A missing ancestor,
inaccessible parent, unsupported or remote filesystem, redirect, wrong kind,
identity alias, or race is failure—not absence.

Before returning, the observer globally rejects duplicate
`(parent_identity, child_comparison_sha256)` keys, hardlinks, junctions, mount
aliases, duplicate canonical Windows
`(volume_serial, file_id_kind, file_id)` identities, or duplicate POSIX
`(device, inode)` identities within and across all 18 roles. It also rejects any protected parent/member
identity equal to a pin-chain exclusion identity and rechecks exact membership
bytes/digest. Candidate-plan duplicate composite-envelope validation remains
defense in depth and does not replace member-level physical-alias rejection.

Only after reader security/content verification, lexical pin/member separation,
membership projection, protected observation, physical pin/member separation,
and final race rechecks may future production orchestration compose an
authenticated protected-authority selection. Its exact pin-evidence and final
selection schemas remain closed until the Windows reader boundary is audited.

## First Implementation Seam

The next bounded seam is only the import-pure protected-membership projection
in:

- `cli/clean_memory_protected_membership.py`; and
- `tests/unit/test_clean_memory_protected_membership.py`.

It will use TDD and temporary/injected immutable values only. It may implement
the exact manifest parsing, configured-role compatibility mapping, lexical
validation, detached membership projection, and membership digest specified
here.

That implementation is not a production trust-root reader and is not
authorization for candidate planning. It consumes no pin evidence and performs
no digest comparison against a trust root. No runtime entrypoint may consume a
caller-constructed membership projection. Production authority remains closed
until the later orchestration owns and invokes both approved readers directly
and completes the authenticated composition gates above.

It will not load configuration, read a manifest or pin, inspect a path, call a
service, persist evidence, build a candidate plan, create a job/token, call
MiniAgent, or perform cleanup. Reader, platform security backend, authoring,
shared no-follow extraction, protected observation, Qdrant observation,
runnable planning, and execution remain later seams.

## Rejected Alternatives

- Reopening v1 to add loader provenance or watchdog source labels.
- Treating `configuration_scope_sha256` as source authentication.
- Trusting a mapping, subclass, Pydantic result, caller provenance flag, or
  `load_configs({})` as proof that ambient inputs were absent.
- Putting configured roles, manifest digest, pin identity, timestamps, or a
  self-hash into the manifest.
- Putting member values, paths, source ID, or second authority into the pin.
- Using repository-local config, an environment variable, or a protected member
  as the external trust root.
- Inferring member ID, kind, or presence from path spelling or current existence.
- Silently sorting or normalizing malformed authority input.
- Treating inaccessible or unsupported state as structural absence.
- Treating lexical uniqueness or candidate-plan envelope uniqueness as physical
  alias proof.
- Importing or copying private target-observer helpers.
- Implementing pin overwrite, implicit rotation, or automatic recovery before a
  separate rollback-safe protocol is approved.

## Verification Boundary

This decision used repository source, tests, prior checkpoints, and three
independent bounded audits. No configured/live protected root, service, data,
Qdrant instance, evidence store, job, token, manifest, pin, or cleanup authority
was read, inferred, created, or changed.
