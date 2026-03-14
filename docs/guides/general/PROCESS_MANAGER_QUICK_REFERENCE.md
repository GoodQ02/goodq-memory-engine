# GoodQ4All Process Manager - Historical Note
> Historical note — `process_manager.py` and `TEST_PROCESS_MANAGER.bat` were retired from the tracked surface on 2026-03-14 because they targeted deleted legacy launchers and were no longer part of the supported runtime.

## Current Fast Paths

- Canonical launcher: `LAUNCH_GOODQ.bat`
- Canonical launcher (PowerShell): `LAUNCH_GOODQ.ps1`
- Canonical watchdog: `python -m cli.watchdog`
- Scaffolded API wrapper, when explicitly needed: `python -m api.server`

## Current References

- [`docs/CLI-REFERENCE.md`](../../CLI-REFERENCE.md)
- [`docs/systems/WATCHDOG_SYSTEM.md`](../../systems/WATCHDOG_SYSTEM.md)
- [`docs/CONTROL_AGENT.md`](../../CONTROL_AGENT.md)
