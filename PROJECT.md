<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-07 — implement the strict clean-memory configuration
projection.

## Outcome

Add RED tests, then implement one import-pure deterministic projection that
turns an injected already-loaded configuration mapping plus one exact requested
epoch into the secret-free logical authority required by later passive
observers. This checkpoint does not add a runnable command or construct a
candidate plan.

## Governing evidence

- `docs/diagnostics/R07_PASSIVE_PLAN_ORCHESTRATION_AUDIT_2026-07-13.md`
- `docs/diagnostics/R07_CLEAN_MEMORY_REPLACEMENT_SELECTION_2026-07-13.md`
- `docs/releases/ROADMAP.md`
- `steps/common/clean_memory.py`
- `configs/config.yaml`
- private candidate-plan checkpoint `c870a1cb`

## Governing invariant

Projection is a pure authority operation. It accepts no path override, reads no
environment or filesystem state, contacts no service, mutates no caller input,
and creates no evidence. It validates one exact configured epoch, exact logical
target topology, explicit Qdrant enablement and canonical loopback endpoint,
optional-port equality, exact four collection names, and the candidate evidence
root. It emits a versioned secret-free projection, stable SHA-256, configured
protected mappings, and one deterministic unresolved protected-role set.

## Test-first order

1. Add focused RED tests in `tests/unit/test_clean_memory_cli.py`.
2. Prove failures for import effects, config mutation, epoch/path/collection/
   endpoint ambiguity, Qdrant enabled/port drift, unstable hashing, secret
   inclusion, and arbitrary non-config protected-path injection.
3. Add only the minimum pure implementation in `cli/clean_memory.py`.
4. Run the focused suite, repeated determinism checks, compilation, import
   purity, documentation, banned-token, dependency, and diff gates.
5. Obtain independent current-byte code and test reviews before checkpointing.

## Scope lock

Implementation may touch only:

- new `cli/clean_memory.py`;
- new `tests/unit/test_clean_memory_cli.py`;
- `PROJECT.md`;
- the reviewed diagnostic and sole roadmap for final checkpoint evidence; and
- generated documentation indexes only when the repository authority gate
  proves the new tracked file requires them.

## Boundaries

- Do not import `load_configs` at module import. This seam accepts an injected
  mapping; a later runnable CLI may load canonical config once inside `main()`.
- Do not inspect filesystem existence, physical aliases, symlinks, junctions,
  reparse points, file or volume identity, hashes, or FAISS contents.
- Do not contact Qdrant or any service, follow redirects, read proxies, page
  points, or create a Qdrant client.
- Do not instantiate `FilesystemTargetEvidence`, `QdrantCollectionEvidence`,
  `ProtectedBoundaryEvidence`, `ResolvedCleanupScope`, `CandidatePlanStore`, or
  call `build_candidate_plan()`.
- Do not add argparse/main execution, plan persistence, a report root, action
  job, token, MiniAgent, disposition/rollback, lease, receipt, apply,
  reconcile, or status behavior.
- Do not read configured data, databases, services, models, ingestion,
  identity, WSL, mixed main, public checkout, or operator reports.
- Do not reopen checkpoints `248bbd33` or `c870a1cb` without contradictory
  evidence.

## Completion gate

RED is witnessed before implementation. The focused temporary/injected suite
then proves deterministic secret-free projection, unchanged caller input,
exact lexical topology, exact Qdrant authority, deterministic unresolved roles,
and import purity without configured or live access. Static gates and at least
two independent current-byte reviews are clean. The checkpoint advances only
to the separate filesystem-observer seam; it does not claim `plan` is runnable.
