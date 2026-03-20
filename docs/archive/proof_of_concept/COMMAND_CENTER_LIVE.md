# Command Center - Historical Implementation Note
> Historical note — this document originally captured the 2025 rollout of the Command Center UI. The feature still exists, but the implementation details here are no longer canonical. Old references to `api_server.py` are preserved only as historical context.

## Current Runtime Truth

- The canonical API surface is launched via `python -m api.server`.
- The current Command Center compatibility endpoint is `GET /api/command-center`.
- The current process-status compatibility endpoint is `GET /api/processes`.
- The current launcher path is `LAUNCH_GOODQ.bat` or `LAUNCH_GOODQ.ps1`, not the retired legacy API monolith.

## Use Instead

- [`docs/reference/API.md`](../../reference/API.md)
- [`docs/CLI-REFERENCE.md`](../../CLI-REFERENCE.md)
- [`docs/releases/SHIP_PROFILE.md`](../../releases/SHIP_PROFILE.md)

## Why This Note Exists

- The original 2025 implementation report referred to `api_server.py` as the active backend.
- The endpoint family survived and moved into the canonical API surface.
- Keeping the old rollout prose as live guidance made the supported runtime look different from what actually ships.
