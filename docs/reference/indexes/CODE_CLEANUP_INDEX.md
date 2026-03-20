# GoodQ4All Code Cleanup Index

**Purpose:** Maintain a truthful map of the remaining manual-review utility surface after the large archive and quarantine passes.

## Current State

Large legacy validation packs have already been quarantined into:

- `tests/legacy/`
- `scripts/archive/legacy_validation/`
- `docs/archive/`

This index now tracks the smaller set of still-visible helper surfaces that may deserve future audit, not the already-archived legacy pack.

## Canonical Keepers

These still have clear present-day value and should not be treated as cleanup targets without a separate audit:

- `cli/watchdog.py`
- `scripts/utils/check_watchdog_status.py`
- `tests/integration/test_watchdog.py`
- `scripts/test_llm_client.py`
- `scripts/test_wsl2_bridge.py`
- `scripts/test_vllm_from_windows.ps1`
- `scripts/test_gpu_config.py`
- `scripts/monitor_gpu_pipeline.py`
- `scripts/run_gpu_optimization_tests.py`
- `scripts/diagnostics/check_dbs.py`
- `scripts/diagnostics/check_latest_results.py`
- `scripts/diagnostics/monitor_progress.py`

## Remaining Manual-Review Surfaces

These are still tracked and may be useful, but they are not part of the smallest canonical release surface:

### Control / Recovery Utilities

- `scripts/test_control_agent_phase2.py`
- `scripts/test_control_integration.py`
- `scripts/test_from_windows_simple.py`
- `scripts/test_vad_simple.py`

### GPU / Operator Utilities

- `scripts/quick_gpu_setup.py`
- `scripts/command_center.ps1`
- `scripts/diagnostics/diagnose_system.py`
- `scripts/Test-AudioDiarization.ps1`
- `scripts/diagnostics/verify_phase1.ps1`

## Recently Archived

The following broad legacy families were removed from the active surface and preserved only for historical reference:

- old root-level `tests/test_*.py` harnesses
- old `tests/utils/` validation helpers
- obsolete `scripts/utils/check_*` and `scripts/utils/validate_*` probes
- obsolete phase-era `scripts/test_*.py` validation helpers

See:

- `tests/legacy/README.md`
- `scripts/archive/legacy_validation/README.md`

## Suggested Next Actions

1. Audit the remaining manual-review surfaces one family at a time.
2. Promote anything still truly useful into canonical docs.
3. Archive anything that remains phase-bound, workstation-specific, or superseded.
