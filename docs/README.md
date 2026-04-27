<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-22 -->

# GoodQ4All Documentation

This is the current landing page for the active GoodQ4All docs surface.

## Current Outcome and Baselines

- Current release checkpoint:
  [`docs/releases/RELEASE_0.1.1.md`](releases/RELEASE_0.1.1.md)
- Current operator baseline:
  [`docs/goodq4all_agent_status.md`](goodq4all_agent_status.md)
- Current system baseline:
  [`docs/SYSTEM_SNAPSHOT.md`](SYSTEM_SNAPSHOT.md)
- Reports and evidence map:
  [`reports/README.md`](../reports/README.md)
- Diagnostics index:
  [`docs/diagnostics/README.md`](diagnostics/README.md)

These operator documents are bounded release-era baselines, not live witness
monitors. Use them to understand the supported runtime surface, then use
released evidence and local reports for deeper proof paths.

Current operator-validated additions on the active line:

- Season 4 long-haul witness is fully banked as the current stress-and-stability proof.
- Season 5 transition and projection smokes prove speaker-aware continuity on fresh material.
- `scene_ingest_results.json`, `scene_manifest.json`, and `temporal_index.json` now align on diarization, emotion, and speaker-truth surfaces.
- The scene API now exposes persisted speaker-truth and continuity fields instead of a thinner compatibility projection.
- Similar-scene search is live on the active API surface and now resolves through multimodal memory, including audio when available.
- The ingest write surface is now a truthful request facade: it stages supported local files into the canonical inbox, returns a request handle, and leaves execution ownership with watchdog plus `cli.run_ingestion`.
- System mutation routes remain intentionally guarded: canonical write surfaces are still CLI, watchdog, and `import_inbox`, while `/api/system/reindex` and `/api/system/reload` stay operator-only.

## Start Here

- Install:
  [`docs/guides/install/INSTALL.md`](guides/install/INSTALL.md)
- Quickstart:
  [`docs/guides/install/QUICKSTART.md`](guides/install/QUICKSTART.md)
- Launch and control:
  [`docs/guides/general/LAUNCH_INSTRUCTIONS.md`](guides/general/LAUNCH_INSTRUCTIONS.md)
- API reference:
  [`docs/reference/API.md`](reference/API.md)
- Quick references:
  [`docs/reference/indexes/QUICK_INDEX.md`](reference/indexes/QUICK_INDEX.md)

## Runtime Authority

- Basement handoff:
  [`docs/HANDOFF_BASEMENT_PHASE.md`](HANDOFF_BASEMENT_PHASE.md)
- System snapshot:
  [`docs/SYSTEM_SNAPSHOT.md`](SYSTEM_SNAPSHOT.md)
- System architecture:
  [`docs/architecture/SYSTEM_ARCHITECTURE.md`](architecture/SYSTEM_ARCHITECTURE.md)
- Architecture diagrams:
  [`docs/architecture/diagrams/`](architecture/diagrams/)
- Watchdog system:
  [`docs/systems/WATCHDOG_SYSTEM.md`](systems/WATCHDOG_SYSTEM.md)
- CLI reference:
  [`docs/CLI-REFERENCE.md`](CLI-REFERENCE.md)
- Shipping profile:
  [`docs/releases/SHIP_PROFILE.md`](releases/SHIP_PROFILE.md)
- Dependencies:
  [`docs/reference/DEPENDENCIES.md`](reference/DEPENDENCIES.md)
- Platform support:
  [`docs/reference/PLATFORM_SUPPORT.md`](reference/PLATFORM_SUPPORT.md)
- WSL audio runtime:
  [`docs/reference/WSL_AUDIO_RUNTIME.md`](reference/WSL_AUDIO_RUNTIME.md)
- GPU capability matrix:
  [`docs/reference/GPU_CAPABILITY_MATRIX.md`](reference/GPU_CAPABILITY_MATRIX.md)

## Operations

- Watchdog:
  [`docs/guides/watchdog/WATCHDOG_INDEX.md`](guides/watchdog/WATCHDOG_INDEX.md)
- Qdrant:
  [`docs/guides/QDRANT_SETUP.md`](guides/QDRANT_SETUP.md)
- GPU, LLM, WSL:
  [`docs/guides/gpu/GPU_LLM_WSL_INDEX.md`](guides/gpu/GPU_LLM_WSL_INDEX.md)

## Release Checkpoint

- Release `0.1.1`:
  [`docs/releases/RELEASE_0.1.1.md`](releases/RELEASE_0.1.1.md)
- Shipping profile:
  [`docs/releases/SHIP_PROFILE.md`](releases/SHIP_PROFILE.md)
- Public changelog:
  [`CHANGELOG.md`](../CHANGELOG.md)

## Important Note

GoodQ4All does not currently ship a supported production UI. The supported
surface is the API, CLI, watchdog, and persisted runtime artifacts.

- UI status:
  [`docs/guides/ui/JUSTIFICATION_UI.md`](guides/ui/JUSTIFICATION_UI.md)

## Historical Material

Historical audits, rollout notes, and legacy implementation artifacts are kept
under [`docs/archive/`](archive/).
