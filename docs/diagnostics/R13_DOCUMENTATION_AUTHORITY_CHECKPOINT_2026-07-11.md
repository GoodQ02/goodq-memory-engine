<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# R-13 Documentation Authority Checkpoint

## Scope

This checkpoint consolidates documentation authority without changing runtime,
data, model, service, or network behavior. Implementation checkpoint:
`3a78e3c0` (`docs: consolidate documentation authority`).

The frozen mixed checkout remained untouched at 96 expanded status entries.
The public checkout remained clean.

## Completed Cutover

- Moved the eight R-17-owned superseded plans/reports into `docs/archive/`
  with historical badges, canonical pointers, and archive warnings.
- Archived the duplicate UCF clean-reingest baseline; retained one clearly
  historical active evidence path used by current-state projections.
- Classified every active root/docs Markdown authority surface. Four
  schema-governed `SKILL.md` files remain deliberately exempt because YAML
  frontmatter must be first.
- Replaced stale `PROJECT.md`, `PLAN.md` naming drift, the long-form legacy
  agent-status narrative, and the stale documentation landing page.
- Rebuilt both repository indexes from a documented `git ls-files` scope.
- Added `scripts/docs/doc_authority_lint.py` and CI coverage for metadata,
  links, mission naming, index parity, R-09 projection parity, epoch claims,
  evidence containment, and Qdrant storage semantics.
- Archived the stale machine-local `%SYSTEMDRIVE%\Tools\RESEARCH_TOOL_AUDIT.md`
  as `%SYSTEMDRIVE%\Tools\archives\RESEARCH_TOOL_AUDIT_2026-06-18.md`, corrected its active
  references, and removed broad Hermes restore advice. These machine-local
  changes are intentionally outside this repository commit.

## Verification

Fresh focused evidence:

```text
tests/unit/test_doc_authority_lint.py: 11 passed
doc_drift_lint: 290 files; 0 active path, ghost-path, CUDA, archive-banner,
  corruption, or snapshot-authority violations
build_current_state.py verify: evidence 2923b9a7ca972db2 matches all projections
banned_token_lint: passed
dependency_drift_lint: passed
active metadata findings: 0
active broken links: 0
mission findings: 0
epoch findings: 0
index findings: 0
current-state findings: 0
```

The machine-local research-tool health check completed with 35 PASS, 12 WARN,
0 FAIL, and all documentation checks passed. The warnings are optional/runtime
availability signals, not documentation failures.

Three independent read-only reviews confirmed the archive cutover, machine-tools
handoff, and checker implementation after their findings were repaired.

## Deliberate Blocker

The full authority verifier remains red on exactly one semantic contradiction:

```text
QDRANT_STORAGE_DRIFT
config: ${GOODQ_DATA_ROOT}/qdrant_storage
canonical docs: ${GOODQ_DATA_ROOT}/GoodQ_Data/qdrant_storage
```

This is not hidden or allowlisted. Architecture-contract alignment owns the
trace and correction. R-13 must remain `IN_PROGRESS` until that bounded seam
proves one storage root and the full documentation verifier passes.

## Resume

Continue with the active bounded mission in `PROJECT.md`. Trace the configured
Qdrant storage root through runtime consumers and focused tests; do not move
data or change runtime configuration merely to make documentation green. After
that checkpoint, rerun every R-13 gate and update the roadmap from evidence.
