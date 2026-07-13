<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-07 — establish immutable clean-memory candidate-plan authority.

## Outcome

Implement only the import-pure, job-independent candidate-plan core selected in
`8ed29592`, building on the completed approval-authority checkpoint `248bbd33`.
The core accepts already-resolved logical scope and injected temporary inventory
evidence, produces one canonical `goodq.clean-memory-plan.v1` authority and
digest, and atomically preserves first-writer immutable plan evidence. It does
not resolve production configuration or make cleanup executable.

## Governing evidence

- `docs/diagnostics/R07_CLEAN_MEMORY_REPLACEMENT_SELECTION_2026-07-13.md`
- `docs/releases/ROADMAP.md`
- `steps/common/clean_memory.py` (new)
- `tests/unit/test_clean_memory_authority.py` (new)
- private foundation checkpoint `248bbd33`

## Governing invariant

Unchanged resolved scope produces one stable candidate-plan identity independent
of time, random IDs, action jobs, approval, disposition, and rollback evidence.
Only injected read-only observations may enter its authority. The first
successful writer atomically preserves the exact canonical plan; a repeated or
concurrent identical writer verifies and returns it, while any same-digest
authority mismatch fails closed. Planning cannot reach a cleanup target.

## Scope

- Add focused RED tests before production code for import purity, canonical
  compact sorted JSON with `allow_nan=False`, deterministic job-independent
  hashing, derived plan identity, and observation metadata outside authority.
- Define only the typed logical records needed for resolved cleanup scope,
  ordered filesystem/Qdrant inventory evidence, protected-boundary identities,
  preconditions, and an immutable candidate plan.
- Add atomic first-writer plan persistence beneath an injected temporary
  evidence root, including repeated/concurrent convergence, collision refusal,
  byte preservation when replacement/persistence fails, and rejection of a
  redirected or reparse-point evidence root.
- Prove through injected fakes and temporary roots that planning creates no
  action job or token, resolves no disposition/rollback artifact, starts/stops no
  process, and performs no target mutation or configured/live access.

## Boundaries

- Touch only `PROJECT.md`, new `steps/common/clean_memory.py`, new
  `tests/unit/test_clean_memory_authority.py`, the two mechanically generated
  tracked-file indexes required by documentation authority, and the roadmap
  checkpoint after verification.
- Do not add `cli.clean_memory`, production configuration resolution, live
  filesystem or Qdrant adapters, approval/apply/reconcile/status commands,
  execution journals, receipts, target deletion, process probes, or leases.
- Do not reopen `248bbd33`, change MiniAgent/action-job behavior, or alter
  existing authorization callers.
- Do not read or mutate configured data, Qdrant, databases, epochs, FAISS,
  services, models, ingestion, identity, WSL, public checkout, or mixed main.
- Do not change dependencies, API/UI routes, runtime launchers, documentation
  replacement surfaces, legacy cleanup scripts, or corpus-retention authority.

## Completion gate

The focused tests first fail because the candidate-plan authority is absent,
then pass after the smallest implementation. Importing the module has no I/O;
canonical authority and digest are stable under repeated and concurrent input;
observational timestamps and job/approval evidence cannot affect the digest;
the immutable plan file cannot be silently replaced; and all tests remain
temporary-only. Checkpoint only after focused tests, compilation, static gates,
staged-diff inspection, and independent current-byte review are fresh and green.
