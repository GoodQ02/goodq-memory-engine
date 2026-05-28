<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-19 -->

<p align="center">
  <img src="samples/assets/q-git-square.png" alt="GoodQ4All mark" width="140" />
</p>

# GoodQ4All

<p align="center">
  <a href="https://GoodQ02.github.io/goodq4all/">
    <img src="https://img.shields.io/badge/Ask_GoodQ-Speak_to_Q--Branch_Now-ffb300?style=for-the-badge&logo=microphone&logoColor=ffb300&labelColor=110d1a" alt="Ask GoodQ Voice Agent - Click Here to Speak" height="42" />
  </a>
</p>

<p align="center">
  <a href="https://GoodQ02.github.io/goodq4all/"><img src="https://img.shields.io/badge/Ask_GoodQ-Voice_Agent-ffb300?style=flat-square" alt="Ask GoodQ Voice Agent" /></a>
  <a href="https://github.com/GoodQ02/goodq4all/actions/workflows/ci.yml"><img src="https://github.com/GoodQ02/goodq4all/actions/workflows/ci.yml/badge.svg" alt="ci" /></a>
  <a href="https://github.com/GoodQ02/goodq4all/actions/workflows/doc-drift-lint.yml"><img src="https://github.com/GoodQ02/goodq4all/actions/workflows/doc-drift-lint.yml/badge.svg" alt="doc-drift-lint" /></a>
  <a href="https://github.com/GoodQ02/goodq4all/actions/workflows/codeql.yml"><img src="https://github.com/GoodQ02/goodq4all/actions/workflows/codeql.yml/badge.svg" alt="codeql" /></a>
  <a href="https://github.com/GoodQ02/goodq4all/actions/workflows/dependency-review.yml"><img src="https://github.com/GoodQ02/goodq4all/actions/workflows/dependency-review.yml/badge.svg" alt="dependency-review" /></a>
</p>

GoodQ4All is a local-first multimodal memory system for long-running video, audio, and text intelligence.


It ingests media into scene-level memory, persists what it learns locally, and keeps the proof path visible. The system is built around deterministic Windows-first execution, with CPU-safe baseline behavior and optional GPU / WSL2 acceleration when you want more throughput.

GoodQ4All's thesis is simple: machine memory should earn every claim it makes.

> [!TIP]
> **Have questions? Ask GoodQ!** Try our interactive conversational voice agent at the [GoodQ4All Landing Page](https://GoodQ02.github.io/goodq4all/) to speak with a virtual Q-Branch operator trained on this repository.

> [!IMPORTANT]
> **Supported Host: Windows 11 only.** GoodQ4All is built for Windows-first local execution (CPU-safe baseline by default; GPU and WSL2 are optional). Other platforms are not first-run targets today.

> [!NOTE]
> **GoodQ4All v1.0.0 Sandboxed Windows Installer**:
> GoodQ4All now ships a unified setup installer (`GoodQ4All_Setup_1.0.0.exe`). This installer installs and configures the application (placing binaries under Program Files and data/storage under ProgramData), hydrates a locked embedded Python runtime from a verified offline wheelhouse, and relies on a supervising native Go launcher (`LAUNCH_GOODQ.exe`) to execute readiness checks, manage fallback ports, and start services automatically without PowerShell or external shell dependencies.


## Watch The Guided Demos

Turn raw media into structured multimodal memory locally:

1. **Raw Media Input**: A sample clip of the Apollo 11 moon landing.
2. **Interactive UI Walkthrough**: Ingest the clip, explore the Retro Memory Explorer, and query the local knowledge graph.
3. **Setup Installer (Recommended)**: Download the single-click Setup Installer (`GoodQ4All_Setup_1.0.0.exe`), launch via `LAUNCH_GOODQ.exe`, and start ingesting immediately.

<table width="100%" border="0" cellspacing="0" cellpadding="10">
  <tr>
    <td align="center">
      <h1><b>TURN THIS...</b></h1>
      <br />
      <img src="samples/assets/nasa_descent.gif?raw=true" alt="Raw Moon Landing Input" width="850" style="max-width: 100%; border-radius: 8px;" />
    </td>
  </tr>
  <tr>
    <td align="center">
      <h1><b>USING THIS.</b></h1>
      <p><b>A single-click sandboxed installer. No Conda. No Git. No command line required.</b></p>
      <p>
        <a href="https://github.com/GoodQ02/goodq4all/releases/download/v1.0.0/GoodQ4All_Setup_1.0.0.exe" style="display: inline-block; padding: 12px 24px; background-color: #ffb300; color: #110d1a; font-weight: bold; text-decoration: none; border-radius: 4px; box-shadow: 0 4px 10px rgba(255, 179, 0, 0.3); transition: all 0.2s ease; margin: 10px 0;">
          🚀 Download GoodQ4All Setup v1.0.0.exe
        </a>
      </p>
      <p><a href="docs/guides/install/INSTALL.md">Read Install Guide</a></p>
      <br />
      <a href="https://github.com/GoodQ02/goodq4all/releases/download/v1.0.0/GoodQ4All_Setup_1.0.0.exe">
        <img src="samples/assets/retro_console_preview.png" alt="Retro Memory Explorer Dashboard" width="850" style="max-width: 100%; border-radius: 8px; border: 1px solid #ffb300;" />
      </a>
    </td>
  </tr>
</table>

> [!IMPORTANT]
> **A Mic-Drop Moment for Local-First Media Intelligence** 🎤
>
> GoodQ4All is now a **100% local, zero-dependency, private offline alternative** to major cloud-based media intelligence services. By packaging the isolated Python runtime, Qdrant database, and perception libraries into a single sandboxed executable, we have made private video search and knowledge graph memory as easy to install as any desktop application. No cloud dependencies, no subscription fees, and no data leaks.

## Before You Start

GoodQ4All's supported host is Windows 11. The runtime is local-first and CPU-safe by default; GPU and WSL2 acceleration are optional.

### A. Standalone User Installation (Recommended)
GoodQ4All is packaged as a self-contained sandboxed Windows Installer. Regular users do not need to install Git, Conda, Python, or manage environment variables. Everything is packaged and automated.
* **Operating System**: Windows 11
* **Disk Space**: At least 25 GB free space (to host local database, processing workspace, and model prefetch caches).
* **Optional**: NVIDIA GPU and WSL2 Ubuntu for accelerated lanes.

### B. Developer Workspace Setup (Advanced / CLI Alternate Route)
If you are developing or running from source code and want to use the CLI, ensure you have:
* **Operating System**: Windows 11 with PowerShell
* **Git**: To clone the repository
* **Miniconda or Anaconda**: Available to the current shell
* **Python**: Version 3.10 or newer
* **Disk Space**: At least 25 GB free space.

---

## First Run (Installer Flow)

If you installed GoodQ4All using the sandboxed Windows Installer (`GoodQ4All_Setup_1.0.0.exe`):

1. **Launch the App**: Double-click the **GoodQ4All** shortcut on your Desktop or Start Menu. This launches the native supervisor launcher (`LAUNCH_GOODQ.exe`), which verifies the model manifest signature, spins up the local Qdrant database, and starts the API/Control processes.
2. **View the Dashboard**: The launcher automatically opens your default web browser to the **Retro Memory Explorer** (served locally on port `30000` with a secure localhost session token).
3. **Drop Media**: Click the **Upload Pad** section in the UI header and select or drag-and-drop a video file (like `.mp4`) onto the yellow-dotted helipad circle. It streams it directly into the inbox drop zone and starts ingestion automatically!

---

## Developer Source Installation & CLI Verification (Alternative Route)

For developers and advanced operators running from source code, we preserve the full step-by-step terminal installation workflow:

### 1. Developer Onboarding Video
Watch the terminal and installation walkthrough video to see the bootstrap commands and active Watchdog ingestion in action:

<p align="center">
  <a href="samples/assets/install_walkthrough.mp4">
    <img src="samples/assets/install_walkthrough.gif?raw=true" alt="Watch Terminal & Installation Walkthrough" width="850" style="max-width: 100%; border-radius: 8px;" />
  </a>
</p>

### 2. Step-by-Step Developer Source Setup

| Step | Type or do this | Demo frame |
| --- | --- | --- |
| 1 | Clone the official source:<br>`git clone https://github.com/GoodQ02/goodq4all.git` | <a href="samples/assets/demo-steps/01-clone-official-source.jpg"><img src="samples/assets/demo-steps/01-clone-official-source.jpg" alt="Clone the GoodQ4All repository" width="300" /></a> |
| 2 | Enter the project cabin:<br>`cd goodq4all` | <a href="samples/assets/demo-steps/02-enter-project-cabin.jpg"><img src="samples/assets/demo-steps/02-enter-project-cabin.jpg" alt="Enter the GoodQ4All project folder" width="300" /></a> |
| 3 | Run the bootstrap installer:<br>`python scripts/bootstrap_install.py`<br><sub>CPU-safe first-run variant: `python scripts/bootstrap_install.py --disable-gpu --disable-wsl-audio --skip-model-prefetch`.</sub> | <a href="samples/assets/demo-steps/03-bootstrap-installer.jpg"><img src="samples/assets/demo-steps/03-bootstrap-installer.jpg" alt="Run the bootstrap installer" width="300" /></a> |
| 4 | Customize local config:<br>edit the bootstrap-created `.env.local` when using local model, cache, or provider settings. | <a href="samples/assets/demo-steps/04-env-local-root.jpg"><img src="samples/assets/demo-steps/04-env-local-root.jpg" alt="Place env local configuration in the repo root" width="300" /></a> |
| 5 | Validate the bootstrap:<br>`.\scripts\bootstrap_validate.bat` | <a href="samples/assets/demo-steps/05-bootstrap-validator.jpg"><img src="samples/assets/demo-steps/05-bootstrap-validator.jpg" alt="Run the bootstrap validator" width="300" /></a> |
| 6 | Run the launcher/readiness check:<br>`.\LAUNCH_GOODQ.ps1` | <a href="samples/assets/demo-steps/06-launch-goodq.jpg"><img src="samples/assets/demo-steps/06-launch-goodq.jpg" alt="Launch GoodQ4All readiness checks" width="300" /></a> |
| 7 | Start Watchdog, then copy one small media file into the import inbox zone (defaults to `%USERPROFILE%\GoodQ_Data\import_inbox\`):<br>`conda run --no-capture-output -n goodq_core python -m cli.watchdog` | <a href="samples/assets/demo-steps/07-watchdog-observes.jpg"><img src="samples/assets/demo-steps/07-watchdog-observes.jpg" alt="Watchdog observes the imported media file" width="300" /></a> |
| 8 | Start the API and inspect proof:<br>`conda run --no-capture-output -n goodq_core python -m api.server` | <a href="samples/assets/demo-steps/08-proof-recorded.jpg"><img src="samples/assets/demo-steps/08-proof-recorded.jpg" alt="Ingestion completes and proof is recorded" width="300" /></a> |

## First Success Loop

If you are new here, start by making one memory:

1. Confirm you have installed GoodQ4All (either via the Setup Installer or via the Developer Source Setup).
2. Start the services (either by double-clicking the **GoodQ4All** Desktop shortcut or by running the developer launcher).
3. Drop one small media file (video or audio) into the configured `import_inbox`.
4. Open the local **Retro Memory Explorer** dashboard in your browser.
5. Verify that scene artifacts and manifestations are successfully written to your local data folder.

Guide:

- [`docs/guides/FIRST_RUN.md`](docs/guides/FIRST_RUN.md)

## What This Actually Is

GoodQ4All is not just an ingest runner or a benchmark harness. It is a full local memory stack with five major layers:

- **Perception engine**
  Detects scenes, extracts keyframes, runs OCR and captions, tags objects and faces, transcribes audio, tracks speakers, and generates embeddings across modalities.

- **Interpretation engine**
  Turns raw perception into scene meaning through `scene_context_llm`, epistemic evidence surfaces, arbitration, and Phase 6 multimodal harmonization. Phase 6 is the final harmonization step that turns per-scene outputs into coherent temporal and vector memory.

- **Memory engine**
  Persists scene manifests, temporal indexes, SQLite memory state, knowledge graph state, and Qdrant vectors as durable local memory rather than disposable run logs.

- **Retrieval engine**
  Supports vector search, KG-backed querying, natural-language lookup, and scene-level analysis against persisted memory.

- **Operations layer**
  Exposes bootstrap, validation, watchdog, health, monitoring, and release-evidence surfaces so the system can be run and audited like infrastructure, not just a script.

### Hybrid-Precision Vector Caching (TurboQuant)
GoodQ4All stores baseline float32 truth while using TurboQuant sidecar caches for faster retrieval. High-precision 32-bit floating point (`float32`) embeddings remain the authoritative truth of the system, stored in Qdrant and FAISS. For performance-oriented first-stage candidate retrieval, the system leverages SQLite sidecar caching columns populated via **TurboQuant** (Lloyd-Max Polar Quantization + Johnson–Lindenstrauss residual projections). This guarantees zero accuracy regression on final ranking while providing fast local candidate pre-filtering. See [TURBOQUANT_HYBRID_CACHING.md](docs/architecture/TURBOQUANT_HYBRID_CACHING.md) for details.


## Why This Project Exists

Most media-intelligence stacks are either:

- cloud-dependent
- opaque when they fail
- or impressive in demos but weak under long-running, real-world ingestion

GoodQ4All is trying to be the opposite:

- local-first
- scene-centric
- auditable
- resilient under partial failure

The design goal is simple: a working memory system is more valuable than a clever one.

## What Is Proven Today

Release `0.1.1` is the current supported checkpoint.

What is actually proven, not just intended:

- The canonical runtime is Windows-first and local-first.
- The supported surface is API + CLI + watchdog + persisted runtime artifacts.
- Scene-context interpretation quality is witness-proven, not just anecdotal.
- Phase 6 harmonization is operating cleanly on the proving run.
- Episode-quality scoring now has a local offline eval lane using curated IMDb-backed anchors for audit only.

Post-release operator validation on the current `main` / `public` line additionally proves:

- WSL audio readiness now means real offline diarization loadability, not import-only checks.
- Successful unified audio preserves diarization and emotion sub-step truth instead of hiding partial failures behind a coarse success result.
- Speaker continuity now persists through `scene_ingest_results.json`, `scene_manifest.json`, and `temporal_index.json`.
- Episode-to-episode continuity is proven on fresh Season 5 material, not just on the release-era comparison witness.
- API scene read models now expose persisted speaker-truth and continuity fields instead of thinner legacy projections.
- Similar-scene retrieval is now a real multimodal feature and can fuse text, visual, and audio memory instead of falling back to an empty path.
- Read-only control recurrence reporting can compare witnesses, index durable artifacts, draft deterministic inspection plans, and derive conservative trends from existing JSON reports without healing or mutation.

Current proving run and release proof path:

- [`docs/releases/RELEASE_0.1.1.md`](docs/releases/RELEASE_0.1.1.md)
- [`docs/releases/SHIP_PROFILE.md`](docs/releases/SHIP_PROFILE.md)
- [`reports/README.md`](reports/README.md)

Current eval result on the proving witness:

- `6/6` core beats covered
- `9.0/9.0` salience weight hit

That result comes from the local episode-reference eval lane and is summarized in the release checkpoint and evidence map above.

## Verify It Yourself

### What Runs What

- `LAUNCH_GOODQ.ps1` checks readiness and opens operator monitors.
- Watchdog watches the configured `import_inbox`.
- `cli.run_ingestion` owns actual ingestion.
- The API is a local read and inspection surface.
- Runtime artifacts are the durable proof.

### First Local Run

If you want the shortest honest path to "does this work on this machine?", run
the same first success loop with the actual commands rather than only starting
the API:

1. Clone the repo and enter the project root.
2. Run the bootstrap installer.
3. Run the bootstrap validator.
4. Run the safe launcher/readiness check.
5. Start Watchdog in one terminal.
6. Drop one small media file into the configured `import_inbox`.
7. Start the API in another terminal.
8. Inspect health and local docs.

```powershell
git clone https://github.com/GoodQ02/goodq4all.git
cd goodq4all
python scripts/bootstrap_install.py
.\scripts\bootstrap_validate.bat
.\LAUNCH_GOODQ.ps1
```

`LAUNCH_GOODQ.ps1` checks readiness and opens operator monitors. It does not start ingestion by itself. To launch with background watchdog ingestion enabled:
```powershell
.\LAUNCH_GOODQ.ps1 -StartIngestion
```

The launcher also has `LAUNCH_GOODQ.bat` for double-click or classic Command
Prompt use. Both wrappers reach the same readiness surface.

If you skipped the Qdrant service prompt during bootstrap, the launcher health check will display:
```text
  [!] Qdrant: Not responding
      Attempting to start Qdrant service...
  [!!] Qdrant: Failed to start - manual intervention required
```
- **When is it safe to ignore?** During your first install verify or when running purely CPU-safe dry runs where vector index lookups are not required.
- **When must it be fixed?** Before running active ingestion (`-StartIngestion` or Watchdog importing files) that updates vector stores, or when executing retrieval queries. Fix it by running:
  ```powershell
  .\scripts\qdrant\INSTALL_QDRANT_SERVICE.bat
  ```
  (Requires Administrator shell).

Leave Watchdog running in one terminal:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.watchdog
```

Copy one small media file into the configured inbox, then start the API in
another terminal. `GOODQ_DATA_ROOT` is the base root; the runtime derives the
drop zone as `<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox\`.

```powershell
conda run --no-capture-output -n goodq_core python -m api.server
```

Then open:

- `http://127.0.0.1:30000/api/health/summary`
- `http://127.0.0.1:30000/docs`
- `http://127.0.0.1:30000/ui/operator_console_v1/` (Classic Operator Console)
- `http://127.0.0.1:30000/ui/retro_console_v1/` (Retro Memory Explorer)

The host and port default to `GOODQ_API_HOST=127.0.0.1` and
`GOODQ_API_PORT=30000` and can be overridden in `.env.local`.

Reference:

- [`docs/guides/FIRST_RUN.md`](docs/guides/FIRST_RUN.md)
- [`docs/guides/watchdog/WATCHDOG_QUICKREF.md`](docs/guides/watchdog/WATCHDOG_QUICKREF.md)
- [`docs/bootstrap/INSTALL_BOOTSTRAP.md`](docs/bootstrap/INSTALL_BOOTSTRAP.md)
- [`docs/reference/API.md`](docs/reference/API.md)


## Supported Surface Today

GoodQ4All currently supports:

- local install and bootstrap on Windows
- local API runtime
- read-only local operator console served by the API process
- CLI ingestion
- watchdog-driven long-running ingestion
- SQLite + knowledge graph + Qdrant-backed persisted memory
- CPU-safe baseline execution with optional GPU / WSL acceleration

GoodQ4All now ships two local read-only operator console variants:
- **Classic Operator Console** served at `/ui/operator_console_v1/`. It exposes the Current Scope strip, Flight Deck, proof/evidence status, recurrence reports, and video inventories.
- **Retro Memory Explorer (v1.4.7)** served at `/ui/retro_console_v1/`. A premium cyber-CRT dashboard featuring a four-panel resizable/collapsible layout with floating restore tabs, an entity co-occurrence graph with dynamic spacing zoom and flight transitions, an Inspector panel containing keyframe image/transcript views with resizable logs splitters, and bidirectional timeline checklists.

<p align="center">
  <img src="samples/assets/retro_console_preview.png" alt="Retro Memory Explorer Premium CRT Console Dashboard" width="600" />
</p>

The consoles are inspection surfaces only. They do not trigger ingestion, reindex memory, heal configs, mutate database structures, generate reports, or activate ControlAgent. A polished consumer memory browser and confirmation-gated mutation UI remain future layers.

UI status & details:

- [`docs/guides/ui/JUSTIFICATION_UI.md`](docs/guides/ui/JUSTIFICATION_UI.md)
- [ui/operator_console_v1/README.md](ui/operator_console_v1/README.md)
- [ui/retro_console_v1/README.md](ui/retro_console_v1/README.md)

## What Makes It Different

- **Scene-centric memory**
  Every major interpretation surface is built around scenes as the atomic unit.

- **Full perception-to-memory pipeline**
  The system does not stop at captions or transcripts. It carries perception forward into harmonized scene truth, temporal rollups, graph relationships, and retrieval surfaces.

- **Knowledge graph with conservative identity logic**
  People, concepts, objects, places, speaker patterns, and identity evidence are persisted locally, with promotion rules designed to avoid hallucinated merges.

- **Audit-first quality**
  The system is tuned with witnesses, diagnostics, and reference evals instead of vibes.

- **Local truth boundary**
  Public episode anchors can inform audit and scoring, but they do not overwrite runtime scene evidence.

- **Controlled acceleration**
  GPU and WSL are additive performance layers, not hidden requirements.

- **Failure visibility**
  Optional enrichments may fail without collapsing the whole run, and the failure path is meant to remain visible.

## Architecture at a Glance

- **Host:** Windows 11 is the canonical runtime host
- **Profiles:** `UNSET`, `BASELINE`, `GPU_ENHANCED`
- **Perception:** scene detection, captions, OCR, object signals, face signals, transcription, diarization, emotion, and embeddings
- **Storage:** SQLite + knowledge graph + Qdrant (with TurboQuant hybrid-precision sidecar vector caching)
- **Memory surface:** scene manifests, temporal index, projected run outputs
- **Core interpretation layer:** `scene_context_llm` with `primary_tags`, `contextual_tags`, and `structural_tags`
- **Identity layer:** speaker patterns, voice-pattern matches, identity candidates, supported identities, and evidence edges
- **Fusion layer:** Phase 6 / Phase 6b harmonization
- **Operator surface:** API + CLI + watchdog + validation and diagnostics

If you want the deeper technical picture:

- [`docs/architecture/README.md`](docs/architecture/README.md)
- [`docs/architecture/SYSTEM_ARCHITECTURE.md`](docs/architecture/SYSTEM_ARCHITECTURE.md)
- [`docs/architecture/ARCHITECTURE_REFERENCE.md`](docs/architecture/ARCHITECTURE_REFERENCE.md)
- [`docs/architecture/MEMORY_STORAGE.md`](docs/architecture/MEMORY_STORAGE.md)
- [`docs/architecture/TURBOQUANT_HYBRID_CACHING.md`](docs/architecture/TURBOQUANT_HYBRID_CACHING.md)
- [`docs/architecture/diagrams/`](docs/architecture/diagrams/)
- [`docs/PHASE6_MULTIMODAL_FUSION.md`](docs/PHASE6_MULTIMODAL_FUSION.md)


## Start Here

- Guided demo: [`docs/guides/DEMO.md`](docs/guides/DEMO.md)
- First run: [`docs/guides/FIRST_RUN.md`](docs/guides/FIRST_RUN.md)
- Install: [`docs/guides/install/INSTALL.md`](docs/guides/install/INSTALL.md)
- Quickstart: [`docs/guides/install/QUICKSTART.md`](docs/guides/install/QUICKSTART.md)
- Laptop profile: [`docs/guides/install/LAPTOP.md`](docs/guides/install/LAPTOP.md)
- Clean memory start: [`docs/guides/CLEAN_MEMORY_START.md`](docs/guides/CLEAN_MEMORY_START.md)
- Uninstall / clean-slate: [`docs/guides/install/UNINSTALL.md`](docs/guides/install/UNINSTALL.md)
- Docs landing page: [`docs/README.md`](docs/README.md)
- API reference: [`docs/reference/API.md`](docs/reference/API.md)
- Current release checkpoint: [`docs/releases/RELEASE_0.1.1.md`](docs/releases/RELEASE_0.1.1.md)
- Support and reporting: [`SUPPORT.md`](SUPPORT.md)

## Current Limitations

- While surrounding plugin integrations and helper scripts continue to evolve, the core v1.0.0 release is stable, signed, and fully package-installed.
- The visual UI consoles (Retro Memory Explorer and Classic Operator Console) are fully functional read-only inspection surfaces. A control-mutating dashboard for modifying database structures remains a future roadmap layer.
- Some optional enrichments can still fail on individual scenes without invalidating the whole ingest.
- Audio-vector success is provenance-defined: current-run CLAP/Qdrant coverage requires `clap_meta.status == ok` plus a Qdrant audio payload with matching `run_id` and required provenance fields. Legacy scene-id matches are not current-run proof.
- Context weighting is now strong, but the project still treats some interpretation choices as policy-level texture rather than frozen truth.

## Security and Data Handling

- Secrets belong in `.env.local` only.
- The canonical runtime does not require cloud execution.
- Local storage is the source of truth.
- Public benchmark and eval materials describe outcomes and metrics, not copyrighted transcript dumps.

Reference:

- [`SUPPORT.md`](SUPPORT.md)
- [`SECURITY.md`](SECURITY.md)
- [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)

## For Maintainers & Advanced Operators

These resources are for reviewing release validation reports, agent status logs, system snapshots, and advanced audit trails:

- **Release Proving Witness:** [`docs/releases/RELEASE_0.1.1.md`](docs/releases/RELEASE_0.1.1.md)
- **Active Ship Profile:** [`docs/releases/SHIP_PROFILE.md`](docs/releases/SHIP_PROFILE.md)
- **Agent Status Log:** [`docs/goodq4all_agent_status.md`](docs/goodq4all_agent_status.md)
- **System Snapshot:** [`docs/SYSTEM_SNAPSHOT.md`](docs/SYSTEM_SNAPSHOT.md)
- **Validation Run Reports:** [`reports/README.md`](reports/README.md)
- **Diagnostics Guide:** [`docs/diagnostics/README.md`](docs/diagnostics/README.md)

Historical and superseded material is intentionally preserved under [`docs/archive/`](docs/archive/), but it is not the front door.

## License

MIT. See [`LICENSE`](LICENSE).
