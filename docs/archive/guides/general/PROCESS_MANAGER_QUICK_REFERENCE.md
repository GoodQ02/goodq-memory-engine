<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: HISTORICAL_POINTER -->
<!-- DOC_CANONICAL_POINTER: docs/guides/general/LAUNCH_INSTRUCTIONS.md -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

# GoodQ4All Process Manager - Historical Note
> Historical note — `process_manager.py` and `TEST_PROCESS_MANAGER.bat` were retired from the tracked surface on 2026-03-14 because they targeted deleted legacy launchers and were no longer part of the supported runtime.

## Current Fast Paths

- Canonical launcher: `LAUNCH_GOODQ.bat`
- Canonical launcher (PowerShell): `LAUNCH_GOODQ.ps1`
- Canonical watchdog: `python -m cli.watchdog`
- Scaffolded API wrapper, when explicitly needed: `python -m api.server`

## Current References

- [`docs/reference/CLI-REFERENCE.md`](../../reference/CLI-REFERENCE.md)
- [`docs/systems/WATCHDOG_SYSTEM.md`](../../systems/WATCHDOG_SYSTEM.md)
- [`docs/agent/CONTROL_AGENT.md`](../../agent/CONTROL_AGENT.md)
