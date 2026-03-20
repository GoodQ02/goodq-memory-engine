<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-03-20 -->

# GoodQ4All 0.1.0 Release Checkpoint

This document records the first public-facing release checkpoint for the
current GoodQ4All runtime surface.

## Scope

Release `0.1.0` is a pre-1.0 checkpoint focused on:

- deterministic Windows-first bootstrap
- CPU-safe `BASELINE` behavior
- optional GPU/WSL acceleration without breaking correctness
- truthful public documentation and release surfaces
- witness-backed runtime validation rather than aspirational claims

## What This Release Represents

- Fresh-machine bootstrap is now a supported path through
  `python scripts/bootstrap_install.py`.
- The canonical local API contract is aligned around `127.0.0.1:30000`.
- Qdrant is treated consistently as a Windows service-first dependency.
- The supported surface is now clearly the API, CLI, watchdog, bootstrap, and
  persisted runtime artifacts.
- Historical UI scaffolding, legacy launch helpers, and obsolete phase/operator
  surfaces have been retired or archived from the active support surface.

## Validation Anchors

- Local CI-equivalent baseline passed on both active branches:
  `python -m pytest -q`
- Active doc-governance lint passed:
  `python scripts/docs/doc_drift_lint.py`
- Fresh Windows laptop bootstrap succeeded after the current bootstrap
  hardening pass.
- Forced ingest sanity rerun succeeded after the Windows audio fallback repair.
- Season 1 witness baseline remains the principal published runtime evidence:
  - `reports/seinfeld_experiment/diagnostics/SEASON1_WITNESS_RUN_2026-03-09.md`
  - `reports/seinfeld_experiment/diagnostics/POST_WITNESS_ANALYTICS_COMPARISON_2026-03-09.md`

## Supported Entry Surface

- Install: `docs/guides/install/INSTALL.md`
- Quickstart: `docs/guides/install/QUICKSTART.md`
- Launch: `docs/guides/general/LAUNCH_INSTRUCTIONS.md`
- API: `docs/reference/API.md`
- Shipping profile: `docs/releases/SHIP_PROFILE.md`

## Truth Boundary

Release `0.1.0` does **not** claim:

- a supported production UI
- multi-node/distributed deployment
- zero-fault operation in every optional enrichment path
- full retirement of all historical documents in the repository

It does claim that the supported release surface is now materially coherent,
portable, and grounded in current runtime behavior.
