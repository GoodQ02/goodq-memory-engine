<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: DRAFT_SELECTION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-07 Protected-Authority Source Decision Brief

## Status

No protected-authority source or trust bootstrap is approved by this document.
R-07 runnable planning remains fail closed for the eight unresolved protected
roles until the operator explicitly approves one source or rejects or defers
both models below.

This brief is decision evidence, not a second backlog. Future work remains
tracked only in `docs/releases/ROADMAP.md`.

## Decision Requested

The operator must choose one of three outcomes:

1. **Approve the recommended manifest plus independent external pin model.**
   The next isolated checkpoint may then select its exact trust root and member
   semantics before code is written.
2. **Select a strict full mapping in ignored local configuration instead.**
   This viable simpler alternative removes the manifest reader but accepts the
   configuration-loader provenance tradeoffs described below. The next isolated
   checkpoint must bind the exact pre-normalization file source and member
   semantics before code is written.
3. **Reject or defer both models.** No substitute is inferred; runnable
   planning remains unavailable until a different explicit source is approved.

Approval means approval of the source and trust model only. It does not approve
member values, configuration changes, a manifest writer, a reader, an observer,
Qdrant access, plan composition, or cleanup execution.

## Recommended Source

Use one versioned machine-local canonical JSON manifest at the single fixed
logical location:

```text
<candidate_evidence_root>/protected-boundaries.json
```

The child name and relative placement are not independently configurable.
`candidate_evidence_root` is derived from configured cleanup topology and bound
into the completed configuration projection. A runtime reader must append only
the constant child name and must never search for another copy.

The manifest supplies exactly the eight unresolved roles:

- `backup_root`
- `download_cache`
- `public_checkout`
- `qdrant_service_logs`
- `recovery_root`
- `reports_root`
- `repository`
- `source_media`

It cannot override the ten configured roles. Its schema is
`goodq.clean-memory-protected-authority.v1`, and its canonical bytes have one
lowercase SHA-256 digest.

## Recommended Integrity Binding

Pin only the expected canonical manifest SHA-256 in a separately trusted
machine-local source outside every protected member. Its exact location and
owner/write-authority policy are not selected by this brief. The pin source
must have exact-file provenance, stable physical and security identity, and an
independent authorization boundary that the manifest author cannot modify.

Repository-local `configs/config.local.yaml` cannot serve as the external pin
under this recommended model because `repository` is itself a protected member.
Using that file as the single trust root belongs only to the separate strict-
mapping option below; it may not be hybridized into the independently pinned
manifest model.

Do not store the manifest path or member paths with the pin, and do not use
`.env.local`, an environment variable, `runtime_config.json`, a CLI argument,
or a caller override as authority.

Do not modify the completed `goodq.clean-memory-configuration.v1` projection.
Its exact schema and the completed filesystem observer are closed checkpoints.
A later isolated seam should introduce a separate pure protected-authority
selection projection that binds exactly:

1. the existing `configuration_scope_sha256`;
2. the constant manifest child beneath the already projected
   `candidate_evidence_root`; and
3. the expected canonical manifest SHA-256 and trusted pin-source identity.

That selection projection must have its own schema and digest, validate the
expected digest and pin provenance independently of Pydantic, and perform no
filesystem, network, process, persistence, plan, job/token, MiniAgent, or
cleanup operation.

## Viable Simpler Alternative

A strict typed full mapping for the eight roles in ignored
`configs/config.local.yaml` is evidence-backed and viable. A separate pure
protected-authority projection could consume that mapping without modifying the
completed v1 configuration projection. This option removes the manifest,
external digest pin, manifest authoring, and manifest reader.

Its tradeoff is a single broader trust surface: the merged configuration would
contain both member values and their authorization. Before selection it would
need exact local-file provenance, independent schema validation, a no-override
entrypoint contract, preservation across bootstrap rewrites, and an explicit
operator decision that the repository-local file is an acceptable trust root.
It must validate and bind the exact local file's pre-normalization bytes through
a dedicated provenance boundary or a provenance-preserving loader change.
Reading only the merged mapping is insufficient because the current loader
expands environment references before merging and then applies caller overrides.
Protected-authority values must reject interpolation rather than silently
becoming environment-derived. The option must still reject environment,
runtime, CLI, caller, CWD, Git, producer, and ledger fallbacks.

The manifest model remains recommended because it separates selected member
content from the authority that approves those exact bytes. The configuration
mapping remains a real operator choice, not a rejected strawman.

## Configuration Provenance Constraints

Either model must account for current loader behavior:

- `GoodQConfig` forbids unknown root keys, so a typed schema addition must
  precede any local overlay field; validation fallback to a raw mapping is not
  authority.
- caller overrides merge after `config.local.yaml`, and the resolved mapping
  carries no provenance; a clean-memory entrypoint must forbid protected-
  authority overrides and prove that contract in tests;
- the bootstrap installer rewrites generated local configuration wholesale and
  must preserve an existing protected-authority value or refuse the rewrite;
  and
- the portable baseline omits machine-local member values and pins, so runnable
  cleanup planning remains fail closed until local authority is selected.

## Non-Circular Trust Bootstrap

Under the recommended manifest model, the first trusted authority requires two
separate deliberate operator actions:

1. An explicit operator authoring and verification step produces the canonical
   manifest candidate and its digest. It cannot update the external pin.
2. After reviewing that candidate, the operator separately authorizes the
   digest in the independently trusted pin source. Planning cannot create the
   manifest, adopt a self-declared digest, or write the pin.

The manifest, a self-hash inside it, or an unpinned sibling checksum cannot
authenticate itself. A cooperative lock may serialize writers but cannot be the
trust guarantee.

Any future manifest or first-pin publication must bind and recheck the effective
filesystem access identity for each operation. On Windows that means the thread
impersonation token when one is present, otherwise the process token, including
the relevant enabled group and privilege state. Publication must require a pre-
existing independently trusted parent, validate the parent's owner and write
authority, validate canonical content before publication, and use create-if-
absent same-directory staging, durability flushes, no-replace publication, and
post-publication content, owner, and security verification. It must preserve a
foreign first writer and remove only temporary content whose physical identity
it created.

Any future rotation is a new approved operation. It cannot overwrite the first
authority silently or update the manifest and trust pin in one implicit step.

## Reader And Platform Boundary

If the recommended manifest model is selected, the manifest and external-pin
readers are later independent seams. Their shared boundary requirements are:

- validate each pre-existing parent and file identity, owner, and write
  authority without trusting manifest or pin claims;
- open and read the same held regular-file handle used for identity validation,
  without following redirects;
- recheck parent membership and file/security state before returning;
- reject replacement, redirect, race, unsupported capability, owner or access
  control drift, malformed content, and digest mismatch; and
- expose no raw path or operating-system error detail.

The manifest reader must select only the constant
`protected-boundaries.json` child beneath the projected
`candidate_evidence_root`, hash its validated canonical bytes, and compare that
digest with the value returned by the independently verified pin reader. The
pin reader must select only the exact external pin source later approved by the
operator. Its location remains deliberately unselected here; it may not search,
fall back to the merged configuration, or derive authority from any protected
member.

The repository has strong target-observer patterns for Windows and POSIX, but
they are private and target-specific. They may be reused only after the already
required projection-agnostic shared-backend extraction and full parity
checkpoint. No private symbol may be imported or copied into the reader.

The current code does not verify Windows process-token identity, owner identity,
or access-control lists. Those are real missing primitives and cannot be
replaced by file IDs, inode values, or a self-declared author field.

## Rejected Existing Alternatives

| Source | Disposition |
| --- | --- |
| Tracked repository configuration or defaults | Reject. They cover only ten roles; machine-specific private paths do not belong in the portable baseline. |
| Strict typed full mapping in ignored local configuration | Viable alternative. It can use a separate projection and preserve v1, but it couples content and authorization to one provenance-losing merged loader and repository-local trust root. |
| Environment variables or `.env.local` | Reject. They are ambient, mutable, process-scoped, incomplete, and producer-specific. |
| CLI or caller injection | Reject. It is invocation-scoped and already proven non-authoritative. |
| `runtime_config.json` | Reject. It is runtime state limited to Qdrant endpoint overrides, not protected topology. |
| Current directory, module path, Git, or sibling discovery | Reject. Discovery explains where code runs; it does not prove which private or public checkout is protected. |
| Producer defaults | Reject. Legitimate producers select conflicting backup, cache, report, service-log, and source-media locations. |
| Live ledgers or databases | Reject. They describe observed activity, not the complete protected set; reconstructing authority from target state is incomplete and circular. |
| Current-state reports or historical documents | Reject. They are derived evidence and cannot become topology authority. |
| Self-hash or sibling checksum | Reject. Without an external pin it is circular. |

Three independent read-only audits found no existing source that authorizes all
eight roles as-is. They identified the manifest plus independent pin as the
stronger separation model and strict typed local configuration as the simpler
viable alternative; both require an explicit operator trust-root decision.

## Deliberately Unselected Semantics

Even if the source/bootstrap recommendation is approved, the following remain
unselected until the next isolated decision checkpoint:

- exact member identifiers and logical-ID format;
- allowed ordinary object kinds;
- role cardinality and deterministic ordering;
- which members must exist and whether structural absence is ever valid;
- the exact multi-member representation for `source_media` and other roles;
- cross-role and within-role physical-alias rejection;
- exact local configuration field and selection-projection schema names;
- pin-source location and provenance contract;
- trusted effective access identity, including impersonation state, owner, and
  access-control policy; and
- authoring, recovery, and rotation command contracts.

No member paths were inspected or inferred while preparing this brief.

## No-Repeat Boundary

Keep these checkpoints closed:

- immutable candidate-plan authority `c870a1cb`;
- configuration projection `a12ceb18`;
- filesystem observer `e8961889`;
- protected-authority audit `f01e03a7`; and
- duplicate canonical-envelope guard `4230a910`.

Do not modify the v1 configuration projection, import or copy private observer
backends, recreate completed tests, inspect live roots, or begin implementation
until the operator decision is recorded.
