<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_NOTE -->
<!-- DOC_LAST_VERIFIED: 2026-05-21 -->

# GoodQ4All UI Status

GoodQ4All ships local read-only UI surfaces for inspection. The current primary
surface is the Operator Console v1 under `ui/operator_console_v1/`; the
Justification Channel v1 remains available under `ui/justification_v1/` for
literal envelope rendering.

## Current Runtime Truth

- The supported release surface is the local API, CLI, watchdog, manifests, and
  persisted memory artifacts.
- The API process serves supported read-only browser surfaces under `/ui/*`.
- `GET /` remains JSON discovery, not a browser shell.
- The Operator Console reads only local API routes and persisted artifacts. It
  is the current scope / Flight Deck / proof / retrieval / storage /
  recurrence / timeline inspection cockpit.
- The Justification Channel may load only explicit read-only sources: bundled
  example data, a user-selected local JSON file, or `GET /api/read/envelope`
  through an explicit API base.
- UI surfaces have no mutation path, no ingestion trigger, no reindex trigger,
  no config healing trigger, no report-generation trigger, and no ControlAgent
  activation.

## Supported UI Surface

- `ui/operator_console_v1/index.html`
- Operator console local route:
  `http://127.0.0.1:30000/ui/operator_console_v1/`
- Operator console contract:
  [`docs/guides/ui/OPERATOR_CONSOLE_V1.md`](OPERATOR_CONSOLE_V1.md)
- `ui/justification_v1/index.html`
- Golden render smoke:
  `ui/justification_v1/static/js/test_render.js`
- Optional inspector mode:
  `ui/justification_v1/inspector/inspector.js`
## Not Supported

- No browser shell is served from the API root.
- No polished consumer memory browser is shipped yet.
- No UI surface may rerun ingestion, reindex memory, mutate memory, heal
  configs, generate recurrence reports, or activate ControlAgent.
- Archived UI notes are historical only and should not override this page.

## Before Future UI Work

- Consume UI-safe conduits and read-only API routes only.
- Keep every source explicit to the operator.
- Do not introduce a second runtime contract or hidden execution path.
- Keep control/mutation routes out of browser UI unless a separate
  control-surface design is approved.

## UI Audit Snapshot

Last checked: 2026-05-21.

- The operator console is active as a read-only local inspection surface.
- The Current Scope strip is the top-level context surface for API base,
  latest run, run source, temporal scope, strict audio proof, browsing target,
  selected scene, and read-only mode.
- Keep future UI work observer-only until a separate control-surface design is
  approved.
- Use `docs/architecture/OUTPUT_SCHEMA_INVENTORY.md` and
  `docs/architecture/MEMORY_STORAGE.md` as the schema and data-hygiene
  boundary.
- Treat optional synthetic-fixture and release-asset polish as roadmap work, not
  prerequisites for the existing read-only UI surfaces.

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
