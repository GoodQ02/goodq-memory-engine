<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-07 — audit the passive filesystem-observer boundary.

## Outcome

Perform one read-only no-repeat audit that reconciles the completed
configuration projection with existing filesystem, identity, hashing, and race
handling helpers. Select one smallest import-pure observer implementation seam,
its exact test oracle, and its file allowlist before any new production code is
written.

## Governing evidence

- private configuration-projection checkpoint `a12ceb18`
- `cli/clean_memory.py`
- `steps/common/clean_memory.py`
- `tests/unit/test_clean_memory_cli.py`
- `tests/unit/test_clean_memory_authority.py`
- `docs/diagnostics/R07_PASSIVE_PLAN_ORCHESTRATION_AUDIT_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Governing invariant

The observer is passive evidence collection, not cleanup authority. It may
eventually accept only already-projected exact logical paths and return exact
epoch-root identity plus immutable filesystem-target evidence. It must never
load configuration, guess a path, follow a reparse/symlink boundary, create a
directory, mutate a target, contact a service, create evidence, build a plan,
or touch jobs, tokens, MiniAgent, or cleanup execution.

## Audit questions

1. Which existing helpers, tests, or platform abstractions already prove part
   of no-follow opening, stable physical identity, SHA-256, reparse rejection,
   or before/after race detection?
2. Which helpers follow paths, fail soft, mutate state, import unrelated
   runtime authority, or omit ancestor/root checks and therefore cannot be
   reused?
3. What exact Windows file/volume identity and reparse evidence is required,
   and what CPU-safe portable fallback is valid for non-Windows tests?
4. How must absent singleton targets be represented without manufacturing
   stale metadata or confusing absence with scan failure?
5. How must every regular file below the exact FAISS root be enumerated,
   no-follow opened, hashed from the same handle, ordered, and race-checked?
6. What negative-capability oracle proves import purity and prevents config,
   environment, network, process, mkdir, or target mutation?
7. What exact source/test file pair is the smallest coherent next seam, and
   which focused evidence closes it before Qdrant observation begins?

## Scope lock

This mission is read-only except for its final reviewed documentation
checkpoint. It may inspect repository source, tests, and active documentation.
If the audit closes cleanly, it may update only:

- `PROJECT.md`;
- `docs/releases/ROADMAP.md`;
- one new filesystem-observer diagnostic for the active roadmap item; and
- generated documentation indexes only if the repository authority gate
  requires them.

No production observer or new test is authorized until the audit is complete,
independently reviewed, checkpointed, and this mission is rewritten with an
exact implementation allowlist.

## Boundaries

- Do not read configured data, databases, FAISS content, services, Qdrant,
  models, ingestion, identity, WSL, the mixed main checkout, the public
  checkout, or operator reports.
- Do not call filesystem helpers on configured paths or use the current working
  directory as authority.
- Do not load configuration or environment values.
- Do not add a runnable command, Qdrant observer, evidence store write, plan,
  job, token, approval, apply, reconcile, status, retention, or lease behavior.
- Do not reopen checkpoints `248bbd33`, `c870a1cb`, or `a12ceb18` without
  contradictory evidence.

## Completion gate

The audit names completed work, rejects unsafe reuse with source evidence,
defines the exact passive observer and test contract, and receives at least two
independent read-only current-byte reviews. The documentation authority,
semantic-drift, banned-token, dependency, and diff gates pass. Only then may
`PROJECT.md` advance to one exact filesystem-observer implementation seam.
