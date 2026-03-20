<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-03-19 -->

# GoodQ4All API Reference

This is the current API reference for the supported local GoodQ4All runtime.

## Runtime Contract

- Launch surface: `python -m api.server`, `LAUNCH_GOODQ.ps1`, or
  `LAUNCH_GOODQ.bat`
- Default bind: `127.0.0.1:30000` unless explicit environment overrides are set
- Root endpoint: `GET /` returns JSON status metadata
- OpenAPI docs: `GET /docs`
- OpenAPI schema: `GET /openapi.json`
- Supported surface: API + CLI + watchdog/runtime artifacts
- No supported product UI is currently served by the API process

## Canonical Endpoint Families

Primary status and compatibility endpoints defined in the active API surface:

- `GET /api/status`
- `GET /api/health/summary`
- `GET /api/engines`
- `GET /api/pipeline-engines`
- `GET /api/command-center`
- `GET /api/processes`
- `GET /api/scenes`

Router-backed endpoint families mounted into the same process:

- `/api/search`
- `/api/timeline`
- `/api/media`
- `/api/system`
- `/api/run-index`
- `/api/run-summary`

## Discovery Rule

Use `/docs` and `/openapi.json` as the authoritative machine-readable endpoint
inventory for the currently running build. Older completion reports and UI audit
notes may mention additional browser pages or retired compatibility paths that
should not be treated as the supported release surface.

## Related Docs

- Install:
  [`docs/guides/install/INSTALL.md`](../guides/install/INSTALL.md)
- Quickstart:
  [`docs/guides/install/QUICKSTART.md`](../guides/install/QUICKSTART.md)
- CLI reference:
  [`docs/CLI-REFERENCE.md`](../CLI-REFERENCE.md)
- UI status:
  [`docs/guides/ui/JUSTIFICATION_UI.md`](../guides/ui/JUSTIFICATION_UI.md)
