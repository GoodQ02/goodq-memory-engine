<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: PUBLIC_RELEASE_BOUNDARY -->
<!-- DOC_LAST_VERIFIED: 2026-05-13 -->

# Control Plane Boundary

This public release does not ship an active autonomous control system.

GoodQ4All 0.1.1 - Epistemic Memory Preview keeps control-plane behavior narrow:

- `ControlAgent` is not activated by default.
- Healing is not enabled by default.
- The public preview does not mutate configs through an autonomous agent.
- The public preview does not execute commands from API recommendation routes.
- The public preview does not use LLMs to alter runtime state.
- `cli/run_ingestion.py` remains the canonical ingestion owner.

## Supported Public Surface

The public preview supports operator observability and explicit local execution:

- CLI commands for ingest, status, and inspection.
- Watchdog plus the configured import inbox as the automation surface.
- Local API read surfaces on loopback.
- Persisted artifacts as the source of runtime truth.

Control-plane docs and code may describe internal or future capabilities, but
they are not launch claims for this public preview unless a release note
explicitly promotes them.

## Read-Only Recurrence Boundary

Read-only recurrence reports, when present, are inspection aids. They may read
existing artifacts and produce operator summaries, but they must not:

- activate `ControlAgent`
- enable healing
- mutate configs
- trigger ingestion
- execute commands
- generate reports from the API
- bypass `cli/run_ingestion.py`

## Release Framing

For this release, describe GoodQ4All as a local-first epistemic memory preview.
Do not describe it as a finished product, a medical system, a compliance
platform, a polished UI, or an autonomous operations agent.
