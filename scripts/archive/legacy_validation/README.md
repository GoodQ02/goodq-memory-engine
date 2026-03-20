# Legacy Validation Archive

**Purpose:** Historical helper scripts and one-off validation harnesses  
**Status:** Archived, non-canonical  
**Last Verified:** 2026-03-20

This directory preserves helper scripts that were useful during individual build phases, workstation diagnostics, or short-lived verification campaigns, but are no longer part of the supported runtime or release-validation surface.

## Current Layout

- `scripts/archive/legacy_validation/root/` - retired root-level `test_*.py` helpers
- `scripts/archive/legacy_validation/utils/` - archived `check_*` and `validate_*` utilities
- `scripts/archive/legacy_validation/diagnostics/` - archived diagnostics probes
- `scripts/archive/legacy_validation/bat/` - retired batch harnesses

Recent additions to this archive include:

- retired control-agent validation harnesses
- retired one-off VAD / diarization probes
- retired quick GPU setup helper
- retired command-center / system-diagnostic console utilities

## Canonical Active Replacements

Prefer the maintained surfaces instead:

- `python -m pytest -q`
- `python -m cli.system_status`
- `python scripts/system_readiness_check.py`
- `tests/integration/test_watchdog.py`
- `scripts/test_llm_client.py`
- `scripts/test_wsl2_bridge.py`
- `scripts/test_vllm_from_windows.ps1`
- `scripts/test_gpu_config.py`
- `scripts/utils/check_watchdog_status.py`
- `scripts/diagnostics/check_dbs.py`
- `scripts/diagnostics/check_latest_results.py`
- `scripts/diagnostics/monitor_progress.py`

## Why These Were Archived

- They are already classified as obsolete in the script registry.
- Many rely on historical paths, retired phases, or workstation-specific fixtures.
- They add surface area and confusion without contributing to the current release contract.
