# Pipeline Engines UI - Historical Implementation Note
> Historical note — this document originally captured the 2025 Pipeline Engines UI rollout. The endpoint still exists, but the implementation details here are no longer canonical. Old references to `api_server.py` are preserved only as historical context.

## Current Runtime Truth

- The canonical API surface is launched via `python -m api.server`.
- The current compatibility endpoint is `GET /api/pipeline-engines`.
- The old implementation report described a rollout into the retired `api_server.py` surface and should not be treated as current operational guidance.

## Use Instead

- [`docs/reference/API.md`](../reference/API.md)
- [`docs/guides/general/LAUNCH_INSTRUCTIONS.md`](../guides/general/LAUNCH_INSTRUCTIONS.md)
- [`docs/releases/SHIP_PROFILE.md`](../releases/SHIP_PROFILE.md)

## Why This Note Exists

- The original completion report captured a specific 2025 UI/API integration milestone.
- The endpoint family survived, but the backend surface moved.
- Leaving the old rollout prose in active form created drift between the documented and actual API surface.
