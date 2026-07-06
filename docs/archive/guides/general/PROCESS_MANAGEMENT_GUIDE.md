<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: REFERENCE_ONLY -->
<!-- DOC_CANONICAL_POINTER: docs/guides/general/LAUNCH_INSTRUCTIONS.md -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

# GoodQ4All Process Management System - Historical Note
> Historical note — the old `process_manager.py` stack was retired from the tracked surface on 2026-03-14 because it depended on deleted legacy launchers (`api_server.py`, `scripts/watchdog_ingest.py`, and `analytics_dashboard.py`).

## Current Runtime Truth

- GoodQ4All no longer ships a generic process-manager surface.
- Canonical startup and health flow goes through `LAUNCH_GOODQ.bat` or `LAUNCH_GOODQ.ps1`.
- Canonical ingestion and file monitoring runs through `python -m cli.watchdog`.
- The scaffolded FastAPI wrapper, when needed manually, is `python -m api.server`.

## Use Instead

- [`docs/reference/CLI-REFERENCE.md`](../../reference/CLI-REFERENCE.md)
- [`docs/systems/WATCHDOG_SYSTEM.md`](../../systems/WATCHDOG_SYSTEM.md)
- [`docs/agent/CONTROL_AGENT.md`](../../agent/CONTROL_AGENT.md)

## Why It Was Retired

- The retired stack still tried to launch deleted legacy surfaces.
- The old batch entrypoints were already gone from the tracked repo.
- Keeping the cluster around made the supported runtime look broader than it is.
