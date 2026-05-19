<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: PUBLIC_RELEASE_STATUS -->
<!-- DOC_LAST_VERIFIED: 2026-05-19 -->

# GoodQ4All Agent Status

This public status surface is scoped to GoodQ4All 0.1.1 - Epistemic Memory
Preview. It replaces private restart-state detail with a release-safe operator
summary.

## Current Release Posture

- Release identity: GoodQ4All 0.1.1 - Epistemic Memory Preview.
- Supported posture: early local-first, scene-centric memory preview.
- Canonical runtime owner: `cli/run_ingestion.py`.
- Automation surface: Watchdog plus the configured import inbox.
- Truth surfaces: scene manifests, temporal indexes, persisted run artifacts,
  SQLite state, knowledge graph state, and Qdrant vectors when configured.
- API posture: local read/inspection surface on loopback, not a hosted public
  service.
- UI posture: read-only Operator Console v1 plus the Justification Channel,
  both served locally under `/ui/*`; no UI execution authority.

## Operator Boundaries

- ControlAgent and healing are not part of the public preview release surface.
- Optional enrichments may fail, but failures should be visible in artifacts or
  logs rather than silently converted into success.
- Runtime config is raw for runtime consumers, but display/logging/operator
  surfaces must sanitize config-like payloads before output.
- Public release docs must not claim healthcare readiness, autonomous control,
  polished consumer UI maturity, full offline-installer maturity, or post-1.0
  API stability.

## Public First-Run Bias

The first public success loop should prove:

- local bootstrap can prepare the runtime
- one operator-owned input can become scene-level memory
- persisted scene artifacts are inspectable
- local API/CLI surfaces and the read-only Operator Console can inspect that
  state
- uncertainty and limits remain explicit

Use `docs/guides/FIRST_RUN.md` as the first-run entrypoint.

Start with the guided demo in `docs/guides/DEMO.md` when a visual walkthrough is
more useful than reading the command list first.

## Release Watch Items

- Keep optional dataset, eval, reference-bank, and synthetic fixture assets out
  of the base installer unless a selected manifest explicitly clears them.
- Keep private media, fresh witness outputs, runtime databases, logs, local
  machine snapshots, and Seinfeld/test-run memory out of the base release.
- Keep public docs framed as an epistemic memory preview, not as a finished app.
