<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-03-20 -->

# GoodQ4All Scripts Guide

This guide lists the maintained script and launcher surfaces for the current
GoodQ4All runtime.

## Canonical Start Surfaces

- `python scripts/bootstrap_install.py`
  - Create or update `goodq_core` and the supported specialized step-env pack.
- `scripts\bootstrap_validate.bat`
  - Run documentation governance, bootstrap verification, and the unit test
    slice used by the supported bootstrap contract.
- `LAUNCH_GOODQ.ps1`
  - Canonical Windows launcher for readiness checks, Qdrant validation, live
    log monitoring, and optional direct ingestion.
- `LAUNCH_GOODQ.bat`
  - Batch wrapper around `LAUNCH_GOODQ.ps1`.

## Explicit Runtime Controls

- `conda run -n goodq_core python -m cli.watchdog`
  - Start watchdog ingestion explicitly.
- `python scripts\utils\check_watchdog_status.py`
  - One-shot watchdog status snapshot.
- `python -m api.server`
  - Start the local API directly.
- `pwsh .\scripts\start_api.ps1`
  - Windows helper for the local API surface.
- `conda run -n goodq_core python cli\run_ingestion.py ingest <media_path>`
  - Direct CLI ingestion entry point.

## Readiness And Diagnostics

- `python scripts\system_readiness_check.py`
  - Manual environment and runtime readiness probe.
- `python scripts\cache_readiness_check.py`
  - Model and dataset cache probe.
- `python scripts\test_llm_client.py`
  - Local LLM connectivity and health check.

## Advanced Repair Surfaces

These remain useful, but they are not the primary onboarding path:

- `scripts\prepare_step_envs.ps1`
  - Manual repair/reinstall surface for specialized step environments.
- `scripts\setup_gpu_environments.bat`
  - Windows GPU stack repair/upgrade helper for the specialized env pack.
- `scripts\install_pipeline_windows.ps1`
  - Broader Windows pipeline repair/provisioning helper.
- `python scripts\install_pipeline_wsl.py`
  - WSL-side pipeline repair/provisioning helper.

Use these only when bootstrap validation or a targeted runtime audit shows a
real env breakage.

## Truth Boundary

- No supported browser UI is currently launched by these scripts.
- Historical dashboard, command-center, and `START_WATCHDOG.bat` rollout notes
  have been archived as proof-of-concept material.
- The maintained operator surface is bootstrap, launcher, CLI ingestion,
  watchdog, API, and persisted runtime artifacts.

## Related Docs

- Launch:
  [`docs/guides/general/LAUNCH_INSTRUCTIONS.md`](LAUNCH_INSTRUCTIONS.md)
- Install:
  [`docs/guides/install/INSTALL.md`](../install/INSTALL.md)
- Quickstart:
  [`docs/guides/install/QUICKSTART.md`](../install/QUICKSTART.md)
- API:
  [`docs/reference/API.md`](../../reference/API.md)
- UI status:
  [`docs/guides/ui/JUSTIFICATION_UI.md`](../ui/JUSTIFICATION_UI.md)
