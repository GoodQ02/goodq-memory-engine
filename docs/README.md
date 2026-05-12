<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-09 -->

# GoodQ4All Documentation

This is the current landing page for the active GoodQ4All docs surface.

Machine memory should earn every claim it makes.

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
- Read-only control recurrence now includes durable artifact indexing, API access, deterministic recommendation drafts, and conservative trend summaries from existing JSON reports. It does not heal, mutate configs, trigger ingestion, or activate `ControlAgent`.
- Audio-vector success is now provenance-defined: current-run CLAP/Qdrant coverage requires `clap_meta.status == ok` plus a Qdrant audio payload with matching `run_id` and required provenance fields. Legacy scene-id matches are not current-run proof.

## Start Here

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

- New user: start with [`docs/guides/FIRST_RUN.md`](guides/FIRST_RUN.md).
- Operator: use [`docs/guides/general/LAUNCH_INSTRUCTIONS.md`](guides/general/LAUNCH_INSTRUCTIONS.md), then Watchdog and API docs.
- Contributor: read [`CONTRIBUTING.md`](../CONTRIBUTING.md), then the architecture index.
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
- Audio vector provenance contract:
  [`docs/architecture/AUDIO_VECTOR_PROVENANCE_CONTRACT.md`](architecture/AUDIO_VECTOR_PROVENANCE_CONTRACT.md)
- GPU capability matrix:
  [`docs/reference/GPU_CAPABILITY_MATRIX.md`](reference/GPU_CAPABILITY_MATRIX.md)

## Documentation Organization

Use this folder as a current-docs surface, not a pile of completion notes.
GoodQ docs should converge toward one durable contract or specification per
system, plus operational guides that point to those contracts.

Authority and organization rules:

- Documentation authority policy:
  [`docs/bootstrap/doc_authority_policy.md`](bootstrap/doc_authority_policy.md)
- Curated authority map:
  [`docs/bootstrap/doc_authority_map.md`](bootstrap/doc_authority_map.md)
- Docs forensics index:
  [`docs/reference/indexes/DOCS_FORENSICS_INDEX.md`](reference/indexes/DOCS_FORENSICS_INDEX.md)
- Corpus/reference pack manifest:
  [`docs/bootstrap/CORPUS_PACK_MANIFEST.md`](bootstrap/CORPUS_PACK_MANIFEST.md)
- Corpus/reference inventory ledger:
  [`docs/bootstrap/CORPUS_PACK_INVENTORY_LEDGER.md`](bootstrap/CORPUS_PACK_INVENTORY_LEDGER.md)
- Reference Pack v0 selection proposal:
  [`docs/bootstrap/REFERENCE_PACK_V0_SELECTION_PROPOSAL.md`](bootstrap/REFERENCE_PACK_V0_SELECTION_PROPOSAL.md)
- Reference Pack v0 license review matrix:
  [`docs/bootstrap/REFERENCE_PACK_V0_LICENSE_REVIEW_MATRIX.md`](bootstrap/REFERENCE_PACK_V0_LICENSE_REVIEW_MATRIX.md)
- Reference Pack v0 source evidence appendix:
  [`docs/bootstrap/REFERENCE_PACK_V0_SOURCE_EVIDENCE_APPENDIX.md`](bootstrap/REFERENCE_PACK_V0_SOURCE_EVIDENCE_APPENDIX.md)
- Archive plan:
  [`docs/bootstrap/doc_archive_plan.md`](bootstrap/doc_archive_plan.md)

Folder roles:

- `architecture/`: runtime contracts, system maps, and cross-component
  boundaries.
- `architecture/components/`: subsystem-specific architecture contracts.
- `bootstrap/`: install, bootstrap, offline bundle, and documentation
  governance contracts.
- `reference/`: stable API, dependency, platform, WSL, and operator reference
  material.
- `guides/`: task-oriented operator guides.
- `systems/`: current system runbooks and daemon/service doctrine.
- `technical/`: implementation notes and technical contracts; historical notes
  must be marked.
- `testing/` and `diagnostics/`: witness evidence, audits, and targeted
  validation notes.
- `releases/`: release-scoped notes.
- `archive/`: historical material only; not current runtime authority.

Avoid adding new "final", "complete", "phase", or task-summary documents for
ordinary fixes. Prefer updating the existing contract when behavior changes,
the release note when a phase closes, or a status snapshot when operator state
changes.

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
