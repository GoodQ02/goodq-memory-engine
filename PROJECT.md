<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-07 — audit protected-boundary authority before implementation.

## Outcome

Produce one read-only, no-repeat authority audit for the eight protected roles
that remain unresolved in the canonical clean-memory configuration projection.
Determine which repository authority, if any, can supply each role and how exact
physical-boundary evidence can reuse the proven platform identity backend
without guessing a root or reading configured data during the audit.

## Governing evidence

- configuration checkpoint `a12ceb18`
- candidate-plan checkpoint `c870a1cb`
- filesystem-observer audit checkpoint `f3ce0920`
- filesystem-observer implementation checkpoint `e8961889`
- `docs/diagnostics/R07_FILESYSTEM_OBSERVER_BOUNDARY_AUDIT_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Governing invariant

Every protected role must come from explicit authority and bind one exact
ordinary physical boundary. Projected path text is not physical-identity
evidence. Missing, ambiguous, redirected, inaccessible, duplicated, or changing
authority remains unresolved and prevents runnable planning; it is never guessed
or converted into partial evidence.

## Exact audit scope

- Trace the canonical protected-role census and `ProtectedBoundaryEvidence`
  contract through current production code and focused tests.
- Reconcile every projected, configured, externally supplied, and unresolved
  role source without reading the configured roots themselves.
- Audit whether the filesystem observer's private Windows/POSIX identity backend
  can be reused without reversing dependency direction or broadening authority.
- Define the smallest deterministic public API, finite failure contract, and RED
  oracle only if repository evidence supports an implementation seam.
- Checkpoint the audit separately before any production or test implementation.

## Boundaries

- Read repository instructions, source, tests, and existing evidence only.
- Do not inspect configured/live protected roots, data, models, services, WSL,
  Qdrant, evidence stores, jobs, tokens, MiniAgent, or cleanup execution.
- Do not modify production source or tests during the audit.
- Do not absorb protected-boundary authority into the completed target observer.
- Do not begin Qdrant observation or runnable planning.
- If any protected role lacks explicit authority, record that fact and preserve
  the fail-closed gate rather than inventing a default.

## Completion gate

Fresh source traces and independent read-only reviews agree on role authority,
placement, API shape, error semantics, reuse boundaries, and the focused RED
matrix. The diagnostic, sole roadmap, and next bounded mission are checkpointed
separately. Completion selects at most one implementation seam; it does not
authorize that implementation.
