<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-17 -->

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

## Start Here

- Guided demo:
  [`docs/guides/DEMO.md`](guides/DEMO.md)
- First run:
  [`docs/guides/FIRST_RUN.md`](guides/FIRST_RUN.md)
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

## Paths By Role

- New user: watch the guided demo, then run [`docs/guides/FIRST_RUN.md`](guides/FIRST_RUN.md).
- Operator: use [`docs/guides/general/LAUNCH_INSTRUCTIONS.md`](guides/general/LAUNCH_INSTRUCTIONS.md), then Watchdog and API docs.
- Contributor: read [`CONTRIBUTING.md`](../CONTRIBUTING.md), then the architecture index.
- Support request: read [`SUPPORT.md`](../SUPPORT.md), then choose the
  matching issue template or discussion path.
- Auditor: start with release notes, reports, diagnostics, and the current system snapshot.

## Runtime Authority

- Basement handoff:
  [`docs/HANDOFF_BASEMENT_PHASE.md`](HANDOFF_BASEMENT_PHASE.md)
- System snapshot:
  [`docs/SYSTEM_SNAPSHOT.md`](SYSTEM_SNAPSHOT.md)
- Architecture index:
  [`docs/architecture/README.md`](architecture/README.md)
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

## Documentation Organization

Use this folder as a current-docs surface, not a pile of completion notes. The core handbook routing docs are:

- Documentation authority policy:
  [docs/bootstrap/doc_authority_policy.md](bootstrap/doc_authority_policy.md)
- Curated authority map:
  [docs/bootstrap/doc_authority_map.md](bootstrap/doc_authority_map.md)
- Corpus/reference pack manifest:
  [docs/bootstrap/CORPUS_PACK_MANIFEST.md](bootstrap/CORPUS_PACK_MANIFEST.md)
- Corpus/reference inventory ledger:
  [docs/bootstrap/CORPUS_PACK_INVENTORY_LEDGER.md](bootstrap/CORPUS_PACK_INVENTORY_LEDGER.md)
- Reference Pack v0 selection proposal:
  [docs/bootstrap/REFERENCE_PACK_V0_SELECTION_PROPOSAL.md](bootstrap/REFERENCE_PACK_V0_SELECTION_PROPOSAL.md)
- Reference Pack v0 license review matrix:
  [docs/bootstrap/REFERENCE_PACK_V0_LICENSE_REVIEW_MATRIX.md](bootstrap/REFERENCE_PACK_V0_LICENSE_REVIEW_MATRIX.md)
- Reference Pack v0 source evidence appendix:
  [docs/bootstrap/REFERENCE_PACK_V0_SOURCE_EVIDENCE_APPENDIX.md](bootstrap/REFERENCE_PACK_V0_SOURCE_EVIDENCE_APPENDIX.md)
- Archive plan:
  [docs/bootstrap/doc_archive_plan.md](bootstrap/doc_archive_plan.md)

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
- Public preview release draft:
  [`docs/releases/PUBLIC_PREVIEW_RELEASE_DRAFT.md`](releases/PUBLIC_PREVIEW_RELEASE_DRAFT.md)
- Shipping profile:
  [`docs/releases/SHIP_PROFILE.md`](releases/SHIP_PROFILE.md)
- Control recurrence v0.5 source status:
  [`docs/releases/CONTROL_RECURRENCE_v0.5_STATUS.md`](releases/CONTROL_RECURRENCE_v0.5_STATUS.md)
- Public changelog:
  [`CHANGELOG.md`](../CHANGELOG.md)

## Important Note

GoodQ4All does not currently ship a production operator dashboard. The
supported UI surface is the read-only Justification Channel at
`ui/justification_v1/`; operational control remains API, CLI, watchdog, and
persisted runtime artifacts.

- UI status:
  [`docs/guides/ui/JUSTIFICATION_UI.md`](guides/ui/JUSTIFICATION_UI.md)

## Historical Material

Historical audits, rollout notes, and legacy implementation artifacts are kept
under [`docs/archive/`](archive/).
