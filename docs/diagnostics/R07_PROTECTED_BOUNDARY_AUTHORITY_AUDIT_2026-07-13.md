<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-07 Protected-Boundary Authority Audit

## Decision

Keep the completed configuration projection and filesystem observer closed.
Keep the candidate-plan schema, evidence types, public API, and persistence
closed while reopening one newly proven validation gap surgically. The
repository does not currently contain one canonical source for the eight
protected roles deliberately left unresolved by the configuration projection.
An observer cannot repair missing lexical
authority and must not infer it from the current directory, environment
fallbacks, sibling checkouts, producer defaults, historical records, or live
data stores.

No new authority source is approved by this audit. The strongest candidate for
an explicit later architecture decision is a versioned, machine-local
protected-authority manifest at one fixed location derived from the already
projected candidate-evidence root:

```text
<candidate_evidence_root>/protected-boundaries.json
```

This is a proposal, not current authority. Its authoring identity, trust
bootstrap, no-follow reader, member semantics, and operator approval must be
selected before implementation. If approved, it would be local control
evidence, not a committed portable default; would supply exactly the eight
unresolved roles; and could not override the ten roles already supplied by
canonical configuration. Until a source is approved and complete, runnable
planning remains fail closed.

Before that projection seam is implemented, close one proven defense-in-depth
gap in the completed candidate-plan authority: different protected roles can
currently carry byte-identical canonical identity JSON envelopes. The immediate
next bounded implementation is one focused validation/test seam that rejects
that duplicate envelope. It does not resolve paths or observe a filesystem.

## Governing Invariant

Protected-boundary authority has two independent parts:

1. an exact lexical role-to-member mapping from one selected authority; and
2. exact physical evidence acquired from that mapping without following a
   redirect or guessing a root.

Neither part substitutes for the other. Every role is present exactly once and
every member is deterministic. The observer later owns actual cross-member and
cross-role physical uniqueness; the candidate-plan guard owns only identical
canonical envelope rejection. No partial role set can become
`ResolvedCleanupScope` evidence.

## Scope and Method

This audit read only repository instructions, source, tests, and existing
checkpoint evidence. It did not read configured or live protected roots, local
data, models, services, WSL, Qdrant, evidence stores, jobs, tokens, MiniAgent,
or cleanup state. Three independent read-only traces covered:

- the 18-role census and every existing role source;
- the `ProtectedBoundaryEvidence` and candidate-plan validation contract; and
- the private Windows/POSIX identity backend and dependency direction.

No production source or test was changed during the audit.

## Canonical Census and Current Projection

`steps/common/clean_memory.py:47-66` defines exactly 18 roles. The completed
projection in `cli/clean_memory.py:46-57,325-488` supplies ten:

| Configured role | Canonical lexical source |
| --- | --- |
| `archive_root` | `paths.nas_path` |
| `control_root` | exact `<data_root>/control` derivation |
| `data_root` | `paths.data_root` |
| `failed_media` | `paths.failed` |
| `import_media` | `paths.import_inbox` |
| `model_cache` | `paths.models_cache` |
| `processed_media` | `paths.processed` |
| `processing_media` | `paths.processing` |
| `qdrant_storage` | `paths.qdrant_storage` |
| `watchdog_state` | exact state-file and lock-file pair |

The configured projection currently supplies only role/path lists. It does not
authorize member identifiers, object kinds, cardinality, or presence policy.
The two-path `watchdog_state` role proves those semantics cannot be inferred
from a one-role/one-root assumption. A later architecture decision must define
those configured-role semantics alongside the eight unresolved roles; this
audit does not invent them.

The remaining eight are emitted deterministically as unresolved. The negative
oracle at `tests/unit/test_clean_memory_cli.py:500-517` proves that arbitrary
`clean_memory.protected_paths`-style injection cannot gain authority.

## Unresolved-Role Findings

| Role | Repository evidence | Audit disposition |
| --- | --- | --- |
| `backup_root` | `cli/memory.py:53-63` writes memory backups below configured `log_dir` or the current directory. `agents/config_healer.py:88-100` separately derives a config-backup directory below the data root. These are different producer scopes. | No canonical global backup boundary. Do not select either producer fallback. |
| `download_cache` | `steps/common/platform_config.py:58-75` uses `GOODQ_CACHE_ROOT` or platform defaults. Dataset, Hugging Face, Torch, and model code use other optional roots and aliases. | No distinct canonical download-cache boundary. Producer discovery is not authority. |
| `public_checkout` | Governance names the downstream remote and branch, but no config key or local-checkout registry identifies a physical directory. | Remote identity cannot prove a local boundary. Never infer a sibling checkout. |
| `qdrant_service_logs` | The Windows service script uses configured `log_dir`; development and packaged launch modes use different roots. The active service owner/mode is not part of the clean-memory projection. | Multiple valid producers conflict. Any approved future authority must name the protected boundary explicitly; R-23 still owns retention reconciliation. |
| `recovery_root` | Production search finds no resolver or configuration key beyond the role census. | Entirely missing. Any approved future authority must require an explicit member; no default exists. |
| `reports_root` | `lib/run_index.py:10-40`, `api/routes/runtime.py:49-67`, MiniAgent, and validators select different report roots or subtrees. | No global report boundary. Caller and environment fallbacks are not authority. |
| `repository` | Several modules derive their own source tree from `__file__`; bootstrap discovery also admits environment, frozen layout, marker search, and current directory. | Module and bootstrap discovery do not prove the private development authority. Any approved future authority must name the protected checkout explicitly. |
| `source_media` | `cli/run_ingestion.py:7518-7578` accepts an arbitrary operator input directory and otherwise uses the already separate import inbox. UCF records individual media paths, not one corpus root. | This is potentially a multi-root role. Do not relabel `import_media` or read a live ledger to manufacture authority. |

The audit therefore found zero role among the eight that can be promoted from
existing producer behavior into canonical clean-memory authority without a new
explicit selection surface.

## Candidate Machine-Local Manifest Architecture

This candidate requires explicit operator approval before it becomes an
implementation mission. The following requirements explain why it is the
strongest current option; they are not active authority.

If approved, a later pure projection would accept canonical manifest content
supplied by a runtime edge that reads only the fixed manifest location derived
from the integrity-bound configuration projection. It would never search for
another copy.

The candidate versioned manifest contract would require:

- schema `goodq.clean-memory-protected-authority.v1`;
- exactly the eight unresolved roles, no configured-role override;
- each role has a non-empty, deterministically ordered member list;
- each member has one canonical identifier, exact absolute lexical path, and
  declared ordinary object kind;
- one role may have multiple members, including `source_media`;
- repeated lexical paths, Windows aliases, cleanup/evidence overlap, or a path
  already assigned to another role fail before filesystem access;
- missing required roles or members fail before filesystem access;
- caller mappings, environment values, CWD, Git discovery, and fallback paths
  are not alternate sources; and
- a canonical manifest SHA-256 binds the selected lexical set without putting
  raw paths into candidate-plan output.

The candidate projection would merge those eight role mappings with the ten
configured role/path lists and return exactly the 18-role lexical set. Before
that seam can be selected, the architecture decision must define exact member
IDs, kinds, cardinality, ordering, presence/absence policy, authoring identity,
and trust bootstrap for both sources. The projection itself would perform no
filesystem access, service call, persistence, plan construction, job/token
work, or cleanup.

The fixed-location, fail-closed runtime reader and any future authoring command
would remain separate seams. A reader boundary audit must determine how it can
read only the exact manifest child, bind the expected authority, and reject
redirect, replacement, changing bytes, or unsupported no-follow capability. No
command may create or populate this candidate manifest implicitly.

The candidate is machine-local by design. Portable repository defaults cannot
know the private checkout, downstream checkout, household source roots, or
deployment-specific backup/report/service boundaries. Portability comes from
the schema and verifier, not copied path values.

## Protected Physical-Evidence Contract

`ProtectedBoundaryEvidence` at `steps/common/clean_memory.py:139-144` contains
only `role`, `logical_id`, and tagged canonical `identity_json`. Production
currently permits a generic safe logical ID and any complete tagged canonical
identity object. A later approved authority schema and observer audit must
select, rather than infer:

- exact logical-ID format;
- versioned identity-envelope schema and authority-digest binding;
- member identifiers, kinds, cardinality, and ordering;
- which members must exist and whether any may bind structural absence;
- deterministic multi-member representation; and
- cross-role and within-role physical-identity rejection with no partial output.

The `watchdog_state` pair proves that single-role/multiple-member semantics are
not theoretical. `source_media` may also require multiple members. The current
three-field evidence type can carry a versioned composite identity, but the
exact composite schema and absence policy belong to a later approved authority
decision and observer boundary audit.

## Existing Candidate-Plan Gap

`steps/common/clean_memory.py:596-612` requires exactly all 18 roles and unique
logical IDs. It does not reject the same canonical `identity_json` envelope
assigned to two different roles. This is a useful defense-in-depth check, but it
does not prove physical uniqueness between different composite envelopes; that
remains the later observer's responsibility.

The immediate RED oracle is exact:

1. create an otherwise valid `ResolvedCleanupScope`;
2. assign one protected role's canonical identity JSON to another role while
   preserving distinct roles and logical IDs;
3. require `build_candidate_plan()` to raise before producing a plan; and
4. prove valid distinct identities and authority round-trip remain unchanged.

The smallest implementation changes only:

- `steps/common/clean_memory.py`; and
- `tests/unit/test_clean_memory_authority.py`.

It does not change `ProtectedBoundaryEvidence`, configuration, observers,
manifest selection, persistence, runtime, or cleanup behavior.

## Backend Reuse Boundary

The completed target observer has the required platform ideas but no supported
generic API. Its public surface is sealed to four symbols at
`cli/clean_memory_filesystem.py:29-34`; its POSIX and Windows primitives are
private and close over target-specific projection, error, hashing, FAISS, and
handle-lifecycle state.

Do not:

- import those private symbols from a protected observer;
- copy the security-critical backend into a second implementation; or
- add protected-role authority to `observe_filesystem()`.

If an approved authority projection later proves a protected observer is
executable, first select an extraction-only checkpoint into a projection-agnostic,
standard-library `steps/common` identity backend. Both CLI adapters may then
depend downward on that backend while keeping their typed role/projection logic
separate. Extraction must preserve the existing observer's four-symbol public
API and full focused regression oracle before any protected observation is
added.

## Later RED Matrix

If the candidate architecture is explicitly approved, its pure projection must
prove:

- exact schema, eight-role membership, member ordering, and detached immutable
  output;
- tampered content/digest, missing/extra/duplicate roles, empty members,
  invalid kinds, aliases, overlap, selected configured-member drift, and
  configured-role override fail before I/O;
- no environment, CWD, Git, config loading, filesystem, network, process,
  persistence, MiniAgent, job/token, or cleanup capability; and
- the candidate manifest location is derived only from the integrity-bound
  configuration projection.

The later physical observer, after authority semantics are approved, must prove:

- exact 18-role input before its first filesystem call;
- no-follow held-handle identity with finite path-free errors;
- deterministic multi-member envelopes and the approved structural-absence
  policy;
- wrong kind, redirect, inaccessible state, unsupported filesystem, duplicate
  identity, rename, replacement, membership drift, and ancestor swap fail with
  no partial evidence;
- Windows remains fixed-drive NTFS/ReFS with held enumeration and
  `OpenFileById`, without descendant-path fallback;
- POSIX opens only `/` by pathname and walks descriptor-relative;
- output contains no raw path or OS-error detail; and
- no plan persistence or mutation occurs during observation.

## Corrected Remaining Order

1. close the duplicate canonical protected-identity envelope validation gap;
2. obtain explicit operator approval for one protected-authority source and its
   non-circular authoring/trust bootstrap;
3. checkpoint exact configured/unresolved member semantics before implementation;
4. if the manifest candidate is approved, implement its pure projection;
5. audit the fixed-location reader boundary and no-follow reuse requirements;
6. audit/select a projection-agnostic shared physical-identity extraction if
   the reader or protected observer requires it;
7. checkpoint the extraction-only implementation with unchanged target-observer
   behavior and full parity, if selected;
8. implement the approved fixed-location reader without folding it into
   projection, protected observation, or final composition;
9. implement the separate protected-boundary observer;
10. implement the fail-closed Qdrant observer;
11. compose runnable `plan` only when all exact evidence is present.

R-23 remains authoritative for retention, disposition, and rollback policy. It
may revise which local boundaries the operator selects, but it does not permit
R-07 to guess them today. R-16 remains authoritative for public release flow;
the local public-checkout path remains an explicit deployment value rather than
an inferred sibling.

## Independent Review Result

Three independent read-only reviews agreed that:

- the eight-role gap is real and complete;
- no existing authority registry resolves it;
- arbitrary path injection and existing producer fallbacks are unsafe;
- the current physical backend is reusable only after a deliberate shared
  extraction, not through private imports or copying;
- byte-identical canonical protected-identity envelopes are not rejected
  downstream, while full physical uniqueness remains observer work; and
- runnable planning must remain fail closed.

No review authorized configured-root reads, implementation, or cleanup.
