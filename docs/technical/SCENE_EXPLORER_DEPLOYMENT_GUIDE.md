# Scene Explorer - Historical Deployment Note
> Historical note — this document originally captured the 2025 Scene Explorer rollout. Scene data endpoints still exist, but the implementation details here are no longer canonical. Old references to `api_server.py` and legacy launcher batches are preserved only as historical context.

## Current Runtime Truth

- The canonical API surface is launched via `python -m api.server`.
- Scene listing is currently provided through `GET /api/scenes` in the canonical API.
- The old deployment narrative around restarting `api_server.py` and using legacy web-interface batch files is no longer current runtime guidance.

## Use Instead

- [`api/API_DOCUMENTATION.md`](../../api/API_DOCUMENTATION.md)
- [`docs/guides/general/LAUNCH_INSTRUCTIONS.md`](../guides/general/LAUNCH_INSTRUCTIONS.md)
- [`docs/releases/SHIP_PROFILE.md`](../releases/SHIP_PROFILE.md)

## Why This Note Exists

- The original deployment report described a one-time rollout into the old API monolith.
- The feature idea persisted, but the canonical API surface changed.
- Recasting this file as historical keeps the implementation breadcrumb without advertising a retired backend path as live.
