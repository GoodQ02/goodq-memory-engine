<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: HISTORICAL_REFERENCE -->
<!-- DOC_LAST_VERIFIED: 2026-04-22 -->

# Pipeline Engines UI - Historical Implementation Note
> Historical note — this document originally captured the 2025 Pipeline Engines UI rollout. The old compatibility endpoint described here is no longer part of the active supported API surface. References to `api_server.py` and `GET /api/pipeline-engines` are preserved only as historical context.

## Current Runtime Truth

- The canonical API surface is launched via `python -m api.server`.
- Engine/runtime truth is currently exposed through `GET /api/engines`, `GET /api/status`, and `/openapi.json`.
- The old implementation report described a rollout into the retired `api_server.py` surface and should not be treated as current operational guidance.

## Use Instead

- [`docs/reference/API.md`](../reference/API.md)
- [`docs/guides/general/LAUNCH_INSTRUCTIONS.md`](../guides/general/LAUNCH_INSTRUCTIONS.md)
- [`docs/releases/SHIP_PROFILE.md`](../releases/SHIP_PROFILE.md)

## Why This Note Exists

- The original completion report captured a specific 2025 UI/API integration milestone.
- The engine/runtime capability survived, but the old compatibility endpoint did not.
- Leaving the old rollout prose in active form created drift between the documented and actual API surface.
