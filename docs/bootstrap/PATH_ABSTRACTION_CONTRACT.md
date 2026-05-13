<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-02-14 -->

# Path Abstraction Contract

This document codifies the active documentation path-surface rules already established by Bootstrap governance.

## Contract Rules
- Absolute Windows paths are forbidden in active docs.
- All examples must use:
  - `<GOODQ_DATA_ROOT>`
  - `<project_root>`
  - `<GOODQ_WSL_WORKSPACE>`
- Archive may contain legacy literals.
- README may include one annotated legacy example for migration clarity.

## Alignment Notes (No New Semantics)
- `docs/bootstrap/bootstrap_manifest.md` establishes path abstraction via `GOODQ_DATA_ROOT`.
- `docs/guides/install/INSTALL.md` defines `GOODQ_DATA_ROOT` and `GOODQ_WSL_WORKSPACE` usage.
- `scripts/docs/doc_drift_lint.py` enforces non-archive `<drive>:/` prohibition as the current guardrail.
