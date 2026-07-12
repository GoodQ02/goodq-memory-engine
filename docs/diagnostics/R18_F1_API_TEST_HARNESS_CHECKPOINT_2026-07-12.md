<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-12 -->

# R-18-F1 API Synthetic Test-Harness Truth Checkpoint

## Objective

Restore truthful execution of the two synthetic `api.main` authority suites
without changing production code or teaching the tests to ignore newly mounted
routers.

## Fresh failure evidence

The clean isolated baseline produced `5 failed, 7 passed`. All five failures
occurred before their behavioral assertions because duplicated synthetic
`api.routes` inventories had drifted behind the import contract in
`api/main.py`: both omitted `identity`, and one also omitted `summary`.

This was a test-harness failure, not evidence that the API behavior under test
was wrong. It was not waived as an unrelated baseline issue.

## Repair

Commit `c136861f` adds one test-only router harness used by both suites. The
harness parses the real `from api.routes import ...` statement, compares it with
the explicit synthetic inventory, and raises a named missing/stale-router error
before executing `api.main`.

The existing isolation remains intact: `meta` and `runtime` stay real only where
the original tests require them; all unrelated routers remain inert; and every
temporary `sys.modules` entry is restored.

## Test-of-the-test evidence

The new oracle deliberately removed `identity` from the synthetic inventory.
Before the helper existed, its focused RED run failed at the missing helper
boundary. After implementation, the oracle proved the production harness names
the actual defect:

```text
missing synthetic routers: ['identity']
```

This prevents a passing suite from merely comparing duplicated or
self-generated expectations.

## Verification

Fresh controller verification after the commit:

```text
tests/unit/test_api_main_legacy_prune_truth.py
tests/unit/test_system_engine_truth.py
13 passed
```

All three changed or added Python files compiled successfully. Both staged and
committed diff checks passed. An independent review found no Critical,
Important, or Minor issues and approved the checkpoint.

One parallel verification attempt encountered the known Windows `conda run`
temporary-file contention. The required commands were retried sequentially and
passed; no production environment or dependency was changed.

## Boundaries and no-repeat rule

- Production API code, configuration, live services, persisted data, and the
  public checkout were not changed.
- Do not restore duplicated router lists or repair future drift by appending a
  missing module in multiple files.
- A future `api.main` router change must first produce the harness-truth failure,
  then update the one explicit inventory deliberately.
