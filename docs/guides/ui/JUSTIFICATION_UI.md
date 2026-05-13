<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_NOTE -->
<!-- DOC_LAST_VERIFIED: 2026-05-09 -->

# GoodQ4All UI Status

GoodQ4All does not currently ship a production operator dashboard. It does
ship one supported read-only truth-layer scaffold: the Justification Channel
v1 under `ui/justification_v1/`.

## Current Runtime Truth

- The supported release surface is the local API, CLI, watchdog, manifests, and
  persisted memory artifacts.
- The API process does not serve a supported browser UI at `GET /`.
- The Justification Channel may load only explicit read-only sources: bundled
  example data, a user-selected local JSON file, or `GET /api/read/envelope`
  through an explicit API base.
- It renders envelopes literally. It has no action buttons, no mutation path,
  no ingestion trigger, no healing trigger, and no ControlAgent activation.

## Supported UI Surface

- `ui/justification_v1/index.html`
- Golden render smoke:
  `ui/justification_v1/static/js/test_render.js`
- Optional inspector mode:
  `ui/justification_v1/inspector/inspector.js`

## Not Supported

- No production operator dashboard is shipped yet.
- No browser shell is served from the API root.
- No UI surface may rerun ingestion, mutate memory, heal configs, or activate
  ControlAgent.
- Archived UI notes are historical only and should not override this page.

## Before Future UI Work

- Consume UI-safe conduits and read-only API routes only.
- Keep every source explicit to the operator.
- Do not introduce a second runtime contract or hidden execution path.

## Use Instead

- API reference:
  [`docs/reference/API.md`](../../reference/API.md)
- Install and launch:
  [`README.md`](../../../README.md),
  [`docs/guides/install/INSTALL.md`](../install/INSTALL.md),
  [`docs/guides/install/QUICKSTART.md`](../install/QUICKSTART.md)
- Runtime authority:
  [`docs/HANDOFF_BASEMENT_PHASE.md`](../../HANDOFF_BASEMENT_PHASE.md),
  [`docs/CLI-REFERENCE.md`](../../CLI-REFERENCE.md)
