<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# R-18 Validator Evidence Isolation Checkpoint

## Invariant

Hermetic validation must never alter operator reports or repository state.
Explicit live and golden evidence runs must either prove every selected
dependency or fail; missing services and missing corpus evidence must never be
reported as a passing skip.

## Checkpoint Lineage

- Branch: `codex/r18-evidence-isolation`
- Base: `a7d82498`
- Code checkpoint: `892976f7 fix: isolate validator and runtime evidence`
- Status: independently reviewed and privately checkpointed

## Included Surface

- explicit validator `--report-dir` and configured report-root handling
- stale-report fingerprint rejection in MiniAgent validator paths
- repository-owned UCF ledger loading for ingestion and scene detection
- removal of the obsolete machine-local skill-copy test
- exact-scope lifecycle confirmation tests with the three stale `xfail` cases
  converted into ordinary passing tests
- central isolated-mode collection gate for every `live_runtime` test
- pinned golden epoch and exact four-collection Qdrant authority
- fail-not-skip API, Qdrant, UCF ledger, and identity retrieval witnesses
- immutable SQLite ledger reads with pre/post database and sidecar fingerprints
- caller-independent, OS-temp, no-bytecode validator and runtime evidence
  runners

## Explicit Frozen-Main Sub-Seam

The frozen main inventory assigned the validator implementation and its focused
test to R-18. That pair also contained one concrete semantic correction:
`t_end` beyond media duration now fails both `temporal_bounds` and
`absolute_timestamps`. R-18 explicitly owns that extracted sub-seam rather than
hiding it as report plumbing. The focused failure-mode test proves both gates;
no other timestamp contract was changed.

## No-Repeat Ownership Proof

R-18 necessarily touches R-02-owned MiniAgent tests and an R-06-overlapping
ingestion loader. Those families were not reimplemented. Fresh non-regression
evidence was run after the R-18 changes:

- R-02 final-authority pack: **137 passed**. The authoritative R-02 checkpoint
  baseline was 129; no checkpoint case was lost.
- R-06 hermetic pack: **42 passed**.
- R-06 expanded pack: **29 passed**.
- canonical loader regression: ingestion and scene detection resolve the same
  repository-owned module object.

## Verification Evidence

Fresh verification completed on 2026-07-11 from the isolated worktree.

- `scripts/dev/run_r18_validator_suite.ps1` was invoked from outside the
  repository: **122 passed** in 95.07 seconds.
- Before and after that suite, existence, size, modification time, and SHA-256
  were unchanged for both JSON/Markdown operator-report surfaces in the
  isolated and frozen-primary checkouts.
- The fresh run left **0** `__pycache__` directories, **0** `.pyc` files,
  **0** `.pytest_tmp` directories, **0** repository-local Conda temp
  directories, and **0** worktree validator reports.
- Core lifecycle/profile/runner/loader pack: **81 passed**.
- Runner/wrapper regression pack after portability hardening: **7 passed**,
  including service-free collection from an unrelated working directory.
- Pinned July Qdrant and immutable UCF witnesses: **4 passed**.
- Isolated runtime-evidence collection: **5 skipped centrally** before service
  fixtures; isolated identity retrieval: **8 skipped centrally**.
- The complete golden runner was invoked while the GoodQ API was intentionally
  stopped: the API witness failed with required evidence unavailable while the
  other **4 passed**. This is the required truthful missing-service result, not
  a successful integrated-runtime claim.
- An explicit live identity run with the skip flag set failed at setup instead
  of reporting a skip.
- Python compile, JSON parsing, PowerShell parsing, stale-reference scans, and
  `git diff --check` passed.
- Three independent final reviews returned READY after the runner hardening.

## Safety Boundaries

- No ingestion, promotion, re-ingestion, service start, or Qdrant mutation was
  performed.
- Qdrant witnesses used inventory and payload reads with vectors suppressed.
- The live UCF ledger used SQLite `mode=ro&immutable=1`, rejected a non-empty
  WAL, and left the database, WAL, and SHM evidence unchanged.
- The mixed main checkout remained frozen at 96 expanded entries.
- The public checkout remained clean.

## Resume

Start R-09 from this checkpoint in a new isolated worktree. Capture one fresh
evidence source and generate both human and JSON current-state projections from
it; do not reopen the completed R-18 validator or lifecycle work.
