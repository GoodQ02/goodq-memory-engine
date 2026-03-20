<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_POINTER -->
<!-- DOC_LAST_VERIFIED: 2026-03-19 -->

# GoodQ4All API Documentation Pointer

This file remains in place to preserve historical links from older rollout and
deployment notes.

## Current Runtime Truth

- The canonical API process is launched via `python -m api.server` or the
  supported launcher surfaces.
- The API bind defaults are configuration-driven and currently resolve to
  `127.0.0.1:30000` unless explicit environment overrides are set.
- `GET /` returns JSON status metadata and links to `/docs` and
  `/openapi.json`.
- The API process does **not** serve a supported product UI at the root path.

## Use Instead

- Canonical API reference:
  [`docs/reference/API.md`](../docs/reference/API.md)
- UI status note:
  [`docs/guides/ui/JUSTIFICATION_UI.md`](../docs/guides/ui/JUSTIFICATION_UI.md)
- Canonical launch/install docs:
  [`README.md`](../README.md),
  [`docs/guides/install/INSTALL.md`](../docs/guides/install/INSTALL.md),
  [`docs/guides/install/QUICKSTART.md`](../docs/guides/install/QUICKSTART.md)

## Historical Note

The previous contents of this file described a 2025 web UI rollout in which the
API process also served dashboard pages such as `dashboard.html`. That scaffold
is no longer a supported release surface and has been demoted to historical
context.
