<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-07 Passive Plan Orchestration Audit

## Decision

Keep the immutable candidate-plan authority at checkpoint `c870a1cb` closed.
No existing production helper can safely turn canonical configuration into its
injected `ResolvedCleanupScope`, and no existing filesystem or Qdrant helper
satisfies the passive exact-state contract.

Implement the production `plan` path as four ordered seams:

1. a strict, pure configuration projection in `cli/clean_memory.py`;
2. a separate import-pure filesystem observer;
3. a separate fail-closed Qdrant observer; and
4. the runnable `plan` orchestration that supplies both observers' evidence to
   `CandidatePlanStore`.

The next bounded implementation seam is **only item 1**. It adds RED tests in
`tests/unit/test_clean_memory_cli.py`, then implements a pure
`resolve_plan_configuration()`-style function in `cli/clean_memory.py`. It does
not add a runnable command, read the filesystem, contact Qdrant, create the
evidence root, write a plan, construct a job, or invoke MiniAgent.

This sequence is smaller and safer than introducing a nominal CLI that hides
three unproven authorities. Configuration projection is a prerequisite for
both observers; the observers do not share a rollback boundary and therefore
remain separate later seams.

## Governing Invariant

One exact operator-supplied epoch must equal the canonical configured epoch.
Every candidate target, protected boundary, Qdrant name, endpoint, and evidence
location must be derived from explicit authority before any observation. A
missing, malformed, defaulted, redirected, inferred, or conflicting authority
fails closed. Configuration projection is deterministic and secret-free; it
does not inspect whether a path or service exists.

## No-Repeat Result

The following work is already complete and is not reopened:

- R-05/R-11 action-job and exact-scope authorization foundations;
- the `clean_memory.apply` MiniAgent registration and no-native-executor rule;
- immutable `goodq.clean-memory-plan.v1` construction;
- exact singleton-file and four-role Qdrant evidence validation;
- canonical loopback Qdrant endpoint validation;
- the complete protected-boundary role census; and
- immutable first-writer plan persistence beneath an injected evidence root.

The audit found patterns to reuse as evidence, but no safe production
configuration-to-plan resolver, filesystem target observer, complete Qdrant
fingerprint observer, or runnable `plan` orchestrator. Wrapping an existing
status/report helper would duplicate ambiguity rather than finish prior work.

## Required Inputs And Authority

| Required plan input | Current authority | Audit result |
| --- | --- | --- |
| requested epoch ID | exact CLI value | must equal the configured epoch; no path, glob, prefix, or implicit default |
| loaded configuration mapping | `steps/common/config_loader.py:270-352` | load once only at a future runtime edge; inject directly in tests |
| configured epoch root | `paths.data_root`, `paths.db_dir` in `configs/config.yaml:55-75` | require exact lexical topology `<data_root>/epochs/<epoch>` without existence checks |
| memory database | `paths.db_path` | require exact `<epoch_root>/memory.db` |
| knowledge-graph database | `paths.knowledge_graph_db` | require exact `<epoch_root>/knowledge_graph.db` |
| FAISS root | `paths.faiss_dir` | require exact `<epoch_root>/faiss` |
| database sidecars | fixed `-wal` and `-shm` suffix rules | derive logically; do not require presence during configuration projection |
| four Qdrant names | `qdrant.collections` in `configs/config.yaml:169-181` | require exactly `text`, `clip`, `dino`, `audio` and exactly `goodq_<role>_<epoch>` |
| Qdrant enablement and endpoint | `qdrant.enabled`, `qdrant.host`, optional overlaid `qdrant.port`, plus the validator at `steps/common/clean_memory.py:370-393` | require explicit enabled state; require canonical loopback HTTP spelling; reject or exactly reconcile a separate port with the URL; do not accept credentials, paths, query, fragment, redirect, or fallback |
| evidence root | selection authority plus `paths.data_root` | derive exactly `<data_root>/control/clean_memory`; no CLI override |
| configuration digest | no existing helper | hash a versioned canonical JSON projection containing only the exact cleanup authority; never hash secrets or the whole config |
| epoch-root identity | no existing observer | later filesystem-observer seam; configuration projection carries only the exact logical root |
| filesystem target evidence | `FilesystemTargetEvidence` contract at `steps/common/clean_memory.py:111-123` | later filesystem-observer seam |
| Qdrant collection evidence | `QdrantCollectionEvidence` contract at `steps/common/clean_memory.py:125-136` | later Qdrant-observer seam |
| protected-boundary evidence | role census at `steps/common/clean_memory.py:47-66` | configured roots may be projected; roles without canonical config authority must be explicit injected authority or fail closed, never guessed |
| plan persistence | `CandidatePlanStore` at `steps/common/clean_memory.py:931-1069` | reuse only after all evidence is complete |

The canonical config directly names `data_root`, import, processing, processed,
failed, model-cache, Qdrant-storage, watchdog-state, and archive paths. It does
not provide one complete authority registry for every protected role, including
repository/public-checkout, backup, recovery, reports, service logs, download
cache, and source media. The projection seam must return the configured mapping
plus one deterministic unresolved-role set. It does not accept arbitrary
non-config path injection. A later seam may consume only a separately selected
canonical authority source for those roles; until then the unresolved set
prevents final plan composition. The projector never derives them from the
current working directory, environment guesses, or historical documentation.

## Reuse Boundaries

### Configuration loader

`load_configs()` remains the canonical future runtime entry. It is not the pure
resolver:

- it conditionally loads `.env.local`;
- supplies and aliases environment values;
- logs runtime-profile state;
- reads the base and local configuration plus `runtime_config.json`;
- applies runtime path defaults; and
- can visibly fall back to an unvalidated mapping when schema import or
  validation is unavailable.

The future CLI may call it exactly once, lazily inside `main()`, then pass the
returned mapping to the strict projection. The projection independently
validates every cleanup-relevant field and never reads environment state.

`get_runtime_paths()` is not reused for this seam. It calls
`_ensure_runtime_path_defaults()`, mutates the mapping, resolves tools/PATH, and
does not require the complete database/FAISS/processed/failed/model-cache set
needed here.

### Current-state reporting

`scripts/docs/build_current_state.py:67-106` proves useful exact epoch,
collection-name, and loopback patterns. It is report code, not production plan
authority: it resolves and requires existing paths, imports unrelated runtime
probes, and validates API/current-state concerns outside R-07. Its Qdrant
capture also samples insufficient point state and treats unrelated collections
differently from the selected protected-canary contract.

The small no-proxy/no-redirect transport posture at
`scripts/docs/build_current_state.py:212-233` is a pattern for the later Qdrant
observer, not an import target.

### Existing Qdrant client

`steps/common/qdrant_client.py` cannot serve as the passive plan adapter:

- construction creates a normal `requests.Session()`;
- `collection_exists()` retries, sleeps, caches readiness, logs failures, and
  collapses some failures into absence;
- `stats()` calls `ensure_collection()` and may create a collection;
- `build_qdrant_client()` accepts host and epochless collection fallbacks and
  couples retrieval telemetry; and
- no method provides an authoritative generation token or a complete canonical
  digest of point IDs, payloads, and vectors.

Current Requests documentation confirms that `Session.trust_env` defaults to
`True` and that redirects are enabled by default. A later loopback-only observer
must therefore disable environment trust and redirects explicitly; it must not
inherit this client's defaults. Documentation source:
`https://github.com/psf/requests/blob/main/src/requests/sessions.py`.

### Existing filesystem helpers

No existing helper combines all required properties:

- root, ancestor, entry, and target `lstat`/reparse rejection;
- exact deterministic enumeration of every regular file below the FAISS root;
- no-follow opening;
- stable platform identity from the opened handle;
- SHA-256 over that same handle;
- before/after identity, size, and modification-time comparison; and
- fail-closed scan/read errors.

`CandidatePlanStore._validate_root()` is correctly scoped to evidence-store
publication. `model_cache_inspector.py`, runtime directory-size helpers, and
the duplicated file-hash functions either follow paths, fail soft, scan only a
subset, or carry unrelated imports. They are test patterns only.

### CLI patterns

`cli/ucf_promotion.py` demonstrates argparse subcommands, injected
configuration/factories, JSON output, and exact configured-epoch rejection.
It also imports MiniAgent and lifecycle authority that `plan` must not touch.
The new CLI may copy the injection and output shape, not that authority graph.

`PassiveActionJobReader` is irrelevant to candidate planning. Constructing
`ActionJobLedger`, MiniAgent, a token, or an action job during `plan` remains a
contract violation.

## Selected Next Implementation Boundary

The next mission may touch only:

- new `cli/clean_memory.py`;
- new `tests/unit/test_clean_memory_cli.py`;
- `PROJECT.md`;
- this diagnostic and the sole roadmap after focused review; and
- generated documentation indexes only if a repository gate proves the new
  file requires them.

The first code checkpoint owns only a deterministic configuration projection.
A suitable immutable result contains:

- exact epoch ID and logical epoch root;
- exact database, sidecar, and FAISS logical paths;
- exact four-role collection map;
- explicit Qdrant enabled state and a port value reconciled exactly with the
  canonical endpoint;
- canonical Qdrant endpoint;
- exact candidate evidence root;
- explicit configured protected-root mappings;
- explicit unresolved protected roles that prevent final plan orchestration;
  and
- the versioned secret-free configuration projection and SHA-256.

It does not instantiate `FilesystemTargetEvidence`,
`QdrantCollectionEvidence`, or `ProtectedBoundaryEvidence`; those records bind
observed identities and belong to later observers/composition. It does not call
`build_candidate_plan()` or `CandidatePlanStore` yet.

### RED contract for the next seam

Temporary/injected tests must prove:

1. importing `cli.clean_memory` performs no config load, environment read,
   filesystem access, network call, process probe, directory creation, output,
   MiniAgent import, or action-job construction;
2. repeated and reordered equivalent mappings produce the same versioned
   projection and SHA-256;
3. the caller's mapping remains byte-for-byte/logically unchanged;
4. the requested epoch must be present, syntactically valid, and exactly equal
   to the configured epoch topology;
5. data root, epoch root, database, knowledge-graph, FAISS, and evidence-root
   topology must be lexically absolute, exact, and non-overlapping where
   required, and reject root, `..`, lexical normalization/case aliases,
   alternate filenames, and target/control ancestry; physical aliases,
   reparses, and file/volume identity remain filesystem-observer work;
6. the collection mapping contains exactly the four roles and exact
   `goodq_<role>_<epoch>` names, with no fallback, missing, extra, duplicate, or
   prefix-substituted name;
7. Qdrant enablement is explicit; the endpoint is canonical loopback-only with
   no credentials, path, query, fragment, alternate spelling, or default; and
   an optional separate `qdrant.port` is absent or equals the URL port exactly;
8. configuration hashing includes every cleanup-relevant authority and excludes
   secrets and unrelated settings;
9. absent or ambiguous protected-boundary sources produce one deterministic
   unresolved-role set rather than accepting arbitrary injected paths or
   guessing; and
10. no test resolves configured data, services, models, WSL, identity, the
    mixed main checkout, public checkout, or operator reports.

## Later Seams, Not Yet Authorized

### Filesystem observer

Add an import-pure stdlib-only adapter that accepts the already-projected exact
paths and produces epoch-root identity plus immutable
`FilesystemTargetEvidence`. It must use no-follow, handle-bound identity and
hashing, deterministic complete FAISS enumeration, race detection, and
fail-closed errors. It performs no configuration load, mkdir, network access,
or mutation.

### Qdrant observer

Add a narrow read-only loopback transport that disables proxies and redirects,
queries only the exact four configured names, and treats a direct 404 as absent
evidence. For an existing collection it must either obtain a separately proven
authoritative generation token or page the full point state with payloads and
vectors, reject malformed/duplicate/looping pagination, canonicalize and sort
the complete state, and produce `point_state_sha256`. It never inventories the
server as an equality constraint and never issues PUT or DELETE.

### Runnable plan orchestration

Only after both observer checkpoints may `python -m cli.clean_memory plan`
load configuration once, project exact authority, collect complete evidence,
build `ResolvedCleanupScope`, and persist through `CandidatePlanStore`. Its only
write is immutable candidate evidence. It still creates no job or token and
performs no cleanup mutation.

## Evidence Boundary

This audit used repository source, tests, canonical config declarations, active
documentation, current Requests documentation through the configured Context7
MCP, and three independent read-only review lanes. It did not read configured
data, databases, FAISS content, Qdrant state, services, models, identity, WSL,
the mixed main checkout, or the public checkout. It did not create an evidence
root, plan, action job, token, report, or production configuration.

## Independent Review

Three independent read-only reviewers traced the reconciled current bytes
against the selected R-07 contract and production source:

- the authority reviewer required explicit `qdrant.enabled` and optional-port
  binding, separated lexical projection from physical identity checks, and
  replaced optional non-config path injection with a deterministic unresolved
  role set;
- the filesystem/Qdrant reviewer confirmed complete no-follow and full
  point-state requirements remain in later observer seams; and
- the documentation reviewer confirmed one-register governance, the exact
  two-file next code/test allowlist, valid badges, and an unambiguous mission
  transition.

After those corrections, all three returned clean verdicts on the current
bytes. No reviewer edited, staged, rendered documentation, or contacted live or
configured state.
