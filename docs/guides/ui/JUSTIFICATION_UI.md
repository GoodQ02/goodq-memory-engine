<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_NOTE -->
<!-- DOC_LAST_VERIFIED: 2026-03-19 -->

# GoodQ4All UI Status

GoodQ4All does not currently ship a supported production UI.

## Current Runtime Truth

- The supported release surface is the local API, CLI, watchdog, manifests, and
  persisted memory artifacts.
- The API process does not serve a supported browser UI at `GET /`.
- Historical UI scaffold and rollout notes have been archived and should not be
  treated as current operator guidance.

## What Still Exists

- `ui/justification_v1/` remains in the repository as an experimental scaffold.
- That scaffold is not part of the supported bootstrap, launch, or release
  contract.
- If future UI work resumes, it must bind to the canonical API surface rather
  than reintroduce a separate runtime contract.

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
