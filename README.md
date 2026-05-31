<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-30 -->

<p align="center">
  <img src="samples/assets/q-git-square.png" alt="GoodQ4All Logo" width="130" />
</p>

<h1 align="center">GoodQ4All</h1>

<p align="center">
  <strong>Local-First Multimodal Epistemic Memory & Private AI Intelligence for Windows 11</strong>
</p>

<p align="center">
  <a href="https://GoodQ02.github.io/goodq4all/">
    <img src="https://img.shields.io/badge/Ask_GoodQ-Speak_to_Q--Branch_Now-ffb300?style=for-the-badge&logo=microphone&logoColor=ffb300&labelColor=110d1a" alt="Ask GoodQ Voice Agent - Click Here to Speak" height="42" />
  </a>
  <br />
  <sub style="color: #a39cb0;">(Note: The optional Ask GoodQ voice agent is a hosted extension using ElevenLabs APIs. The core GoodQ4All memory system itself is 100% local and offline.)</sub>
</p>

<p align="center">
  <a href="https://github.com/GoodQ02/goodq4all/actions/workflows/ci.yml"><img src="https://github.com/GoodQ02/goodq4all/actions/workflows/ci.yml/badge.svg" alt="CI Status" /></a>
  <a href="https://github.com/GoodQ02/goodq4all/actions/workflows/doc-drift-lint.yml"><img src="https://github.com/GoodQ02/goodq4all/actions/workflows/doc-drift-lint.yml/badge.svg" alt="Doc Drift Linter" /></a>
  <a href="https://github.com/GoodQ02/goodq4all/actions/workflows/dependency-review.yml"><img src="https://github.com/GoodQ02/goodq4all/actions/workflows/dependency-review.yml/badge.svg" alt="Dependency Review" /></a>
</p>

---

## ⚡ The Local-First Multimodal Memory Stack

GoodQ4All is a **100% private, offline alternative** to cloud-based media intelligence services. It ingests video, audio, and text files into queryable, structured scene-level memories, persisting the knowledge graph and vector representations locally on your computer.

Following a strict **"proof-backed" system doctrine**, GoodQ4All documents every perception step, tracks evidence manifests, and logs a comprehensive audit trail so that every memory claim can be verified.

---

### 🎬 The Visual Hook: From Media to Memory

*   **Get This (Unified Operator UI):**
    <p align="center">
      <a href="samples/assets/ui_onboarding_walkthrough.mp4">
        <img src="samples/assets/ui_onboarding_walkthrough.gif" alt="UI Onboarding Walkthrough" width="850" style="max-width: 100%; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);" />
      </a>
      <br />
      <em>Click the preview above to watch the high-fidelity onboarding video.</em>
    </p>

*   **From This (Raw Media Inputs):**
    <table width="100%" border="0" cellspacing="0" cellpadding="10">
      <tr>
        <td align="center" width="50%" style="border: none;">
          <img src="samples/assets/nasa_descent.gif" alt="Neil Armstrong Descent" style="max-width: 100%; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.2);" /><br />
          <small><em>Apollo 11 Moon Walk (nasa_descent.gif)</em></small>
        </td>
        <td align="center" width="50%" style="border: none;">
          <img src="samples/assets/nasa_launch.gif" alt="Rocket Launch" style="max-width: 100%; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.2);" /><br />
          <small><em>Saturn V Launch (nasa_launch.gif)</em></small>
        </td>
      </tr>
    </table>

*   **Using This (Unified Windows Installer):**
    <p align="center">
      <a href="https://github.com/GoodQ02/goodq4all/releases/download/v1.0.0/GoodQ4All_Setup_1.0.0.exe" style="display: inline-block; padding: 16px 32px; background-color: #ffb300; color: #110d1a; font-size: 1.15em; font-weight: bold; text-decoration: none; border-radius: 6px; box-shadow: 0 4px 15px rgba(255, 179, 0, 0.4); transition: all 0.2s ease; margin: 10px 0;">
        🚀 Download GoodQ4All Setup v1.0.0.exe
      </a>
    </p>
    
    > [!IMPORTANT]
    > **System Requirement: Windows 11 only.** GoodQ4All is built for Windows-first local execution. It requires at least **25 GB** of free space to store local database structures, models, and cache files.
    
    <p align="center">
      <a href="https://github.com/GoodQ02/goodq4all/releases/download/v1.0.0/GoodQ4All_Setup_1.0.0.exe">
        <img src="samples/assets/one_click_installer_mockup.png" alt="GoodQ4All One-Click Setup Installer" width="550" style="max-width: 100%; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.15);" />
      </a>
    </p>

---

## 🛡️ Core Capabilities & Architecture

### 1. Proof-Backed Ingestion & Witness Audit Trail
Machine memory should earn every claim it makes. GoodQ4All generates step-by-step logs (`step_runs.jsonl`), scene manifests, and intermediate features for every ingested file.
*   **Epistemic Verification:** Ingestion is tracked using verifiable manifests and SQLite-backed relational schemas.
*   **No Silent Failures:** The Control Agent and Watchdog processes bubble errors directly to the operator consoles, providing absolute visibility into the execution stack.
*   **Science & Witness Ratings:** Ingestion runs produce verifiable evidence checkpoints, letting you inspect and audit model perceptions.

### 2. TurboQuant Hybrid Vector Caching
High-precision 32-bit floating point embeddings are persisted in Qdrant and FAISS. For rapid candidate filtering, GoodQ4All uses **TurboQuant**—an SQLite sidecar caching technology employing Lloyd-Max Polar Quantization and Johnson-Lindenstrauss residual projections.
*   **Performance:** Achieves sub-millisecond candidate pre-filtering.
*   **Accuracy:** 100% search accuracy is maintained by performing the final rank scoring on the uncompressed raw float32 vectors.

### 3. Adaptive Hardware Profiles
The pipeline dynamically adjusts its computational needs to match your system specs:
*   `BASELINE` (CPU-safe): Fully operational, offline-ready execution on standard CPU hardware. Bypasses GPU requirements gracefully.
*   `GPU_ENHANCED`: Activates local NVIDIA GPU (CUDA 12.1) and WSL2 accelerated audio processing paths for fast, high-volume ingestion.

---

## ⚙️ Setup Paths

### Route A: Standalone User Installation (Recommended)
GoodQ4All compiles the isolated Python environment, the Qdrant database, and perception libraries into a single executable wrapper:
1.  Download and run `GoodQ4All_Setup_1.0.0.exe`.
2.  Launch **GoodQ4All** from the desktop shortcut.
3.  Open the local **Retro Memory Explorer** dashboard at `http://127.0.0.1:30000/ui/retro_console_v1/`.
4.  Drag-and-drop video/audio files onto the yellow-dotted **Upload Pad** to begin automatic ingestion.

### Route B: Developer Source Setup (Advanced)
If you are developing, customizing the pipeline, or running from source:

<details>
<summary><b>Developer Source Setup Steps (Advanced)</b></summary>
<br />

#### 1. Developer Onboarding Video
<p align="center">
  <a href="samples/assets/install_walkthrough.mp4">
    <img src="samples/assets/install_walkthrough.gif" alt="Developer Onboarding Walkthrough" width="850" style="max-width: 100%; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.25);" />
  </a>
</p>

#### 2. Step-by-Step Developer Installation

| Step | Type or do this | Demo frame |
| --- | --- | --- |
| 1 | Clone the official source:<br>`git clone https://github.com/GoodQ02/goodq4all.git` | <a href="samples/assets/demo-steps/01-clone-official-source.jpg"><img src="samples/assets/demo-steps/01-clone-official-source.jpg" alt="Clone the GoodQ4All repository" width="300" /></a> |
| 2 | Enter the project cabin:<br>`cd goodq4all` | <a href="samples/assets/demo-steps/02-enter-project-cabin.jpg"><img src="samples/assets/demo-steps/02-enter-project-cabin.jpg" alt="Enter the GoodQ4All project folder" width="300" /></a> |
| 3 | Run the bootstrap installer:<br>`python scripts/bootstrap_install.py`<br><sub>CPU-safe first-run variant: `python scripts/bootstrap_install.py --disable-gpu --disable-wsl-audio --skip-model-prefetch`.</sub> | <a href="samples/assets/demo-steps/03-bootstrap-installer.jpg"><img src="samples/assets/demo-steps/03-bootstrap-installer.jpg" alt="Run the bootstrap installer" width="300" /></a> |
| 4 | Customize local config:<br>edit the bootstrap-created `.env.local` when using local model, cache, or provider settings. | <a href="samples/assets/demo-steps/04-env-local-root.jpg"><img src="samples/assets/demo-steps/04-env-local-root.jpg" alt="Place env local configuration in the repo root" width="300" /></a> |
| 5 | Validate the bootstrap:<br>`.\scripts\bootstrap_validate.bat` | <a href="samples/assets/demo-steps/05-bootstrap-validator.jpg"><img src="samples/assets/demo-steps/05-bootstrap-validator.jpg" alt="Run the bootstrap validator" width="300" /></a> |
| 6 | Run the launcher/readiness check:<br>`.\LAUNCH_GOODQ.ps1` | <a href="samples/assets/demo-steps/06-launch-goodq.jpg"><img src="samples/assets/demo-steps/06-launch-goodq.jpg" alt="Launch GoodQ4All readiness checks" width="300" /></a> |
| 7 | Start Watchdog, then copy one small media file into the import inbox zone (defaults to %USERPROFILE%\GoodQ_Data\import_inbox\):<br>`conda run --no-capture-output -n goodq_core python -m cli.watchdog` | <a href="samples/assets/demo-steps/07-watchdog-notes.jpg"><img src="samples/assets/demo-steps/07-watchdog-observes.jpg" alt="Watchdog observes the imported media file" width="300" /></a> |
| 8 | Start the API and inspect proof:<br>`conda run --no-capture-output -n goodq_core python -m api.server` | <a href="samples/assets/demo-steps/08-proof-recorded.jpg"><img src="samples/assets/demo-steps/08-proof-recorded.jpg" alt="Ingestion completes and proof is recorded" width="300" /></a> |

</details>

---

## 📺 User Interfaces

GoodQ4All ships with two local operator console variants:
*   **Classic Operator Console** (served at `/ui/operator_console_v1/`): Exposes the current scope strip, flight deck, proof/evidence status, recurrence reports, and video inventories.
*   **Retro Memory Explorer (v1.4.7)** (served at `/ui/retro_console_v1/`): A premium cyber-CRT dashboard featuring a four-panel resizable/collapsible layout with floating restore tabs, an entity co-occurrence graph with dynamic zoom and flight transitions, an Inspector panel containing keyframe image/transcript views, and bidirectional timeline checklists.

---

## 📖 Authoritative Documentation

### Start Here
*   Guided demo: [`docs/guides/DEMO.md`](docs/guides/DEMO.md)
*   First run: [`docs/guides/FIRST_RUN.md`](docs/guides/FIRST_RUN.md)
*   Install: [`docs/guides/install/INSTALL.md`](docs/guides/install/INSTALL.md)
*   Quickstart: [`docs/guides/install/QUICKSTART.md`](docs/guides/install/QUICKSTART.md)
*   Clean memory start: [`docs/guides/CLEAN_MEMORY_START.md`](docs/guides/CLEAN_MEMORY_START.md)

### Technical Details
*   Architecture: [`docs/architecture/SYSTEM_ARCHITECTURE.md`](docs/architecture/SYSTEM_ARCHITECTURE.md)
*   Memory Storage: [`docs/architecture/MEMORY_STORAGE.md`](docs/architecture/MEMORY_STORAGE.md)
*   Hybrid Caching: [`docs/architecture/TURBOQUANT_HYBRID_CACHING.md`](docs/architecture/TURBOQUANT_HYBRID_CACHING.md)
*   Current Agent State: [`docs/agent/CURRENT_STATE.md`](docs/agent/CURRENT_STATE.md)

---

## 📄 License

MIT. See [`LICENSE`](LICENSE).
