# SCRIPT_REGISTRY

_Public branch refreshed: 2026-05-09_

## Scope

This file is a lightweight public orientation note for the maintained script
surface. It is not a generated inventory and it is not runtime authority.

Runtime authority remains with:

- root launchers: `LAUNCH_GOODQ.ps1`, `LAUNCH_GOODQ.bat`
- bootstrap and validation: `scripts/bootstrap_install.py`,
  `scripts/bootstrap_verify.py`, `scripts/bootstrap_validate.bat`,
  `scripts/bootstrap_models.py`
- interpreter bindings: `scripts/_lib/interpreter_bindings.ps1`,
  `scripts/_lib/interpreter_bindings.bat`
- canonical ingest: `cli/run_ingestion.py`
- isolated step execution: `cli/step_runner.py`
- watchdog: `cli/watchdog.py`
- WSL audio bridge: `scripts/wsl2_audio_bridge.py`, `wsl2_audio/`

## Public Archive Policy

The public branch omits old one-time migration scripts, retired validation
harnesses, root legacy UI snapshots, and excluded legacy tests. Those materials
were useful during project archaeology, but they are not part of the supported
public runtime or contributor surface.

Do not re-add historical scripts to public for completeness. If an old harness
becomes useful again, reintroduce it as a maintained script with:

- neutral paths and fixtures
- current docs
- focused tests
- a clear owner and validation command

## Supported Script Discovery

Use these docs first:

- [`scripts/README.md`](../../scripts/README.md)
- [`tests/README.md`](../../tests/README.md)
- [`docs/CLI-REFERENCE.md`](../CLI-REFERENCE.md)
- [`docs/guides/install/QUICKSTART.md`](../guides/install/QUICKSTART.md)
- [`docs/reference/WSL_AUDIO_RUNTIME.md`](../reference/WSL_AUDIO_RUNTIME.md)