<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-08-16 -->

<p align="center">
  <img src="samples/assets/q-git-square.png" alt="GoodQ4All Logo" width="130" />
</p>

<h1 align="center">GoodQ4All: Local-First Multimodal AI Memory & Video Intelligence Stack</h1>

<p align="center">
  <strong>Offline Video Search, Scene Segmentation, Speech Transcription (Whisper), Object Detection, Visual Embeddings (DINOv2/CLIP), and SQLite + Qdrant Semantic Search on Windows 11</strong>
</p>

<p align="center">
  <a href="https://askgoodq.com/">
    <img src="https://img.shields.io/badge/Ask_GoodQ-Speak_to_Q--Branch_Now-ffb300?style=for-the-badge&logo=microphone&logoColor=ffb300&labelColor=110d1a" alt="Ask GoodQ Voice Agent - Click Here to Speak" height="42" />
  </a>
  <br />
  <sub style="color: #a39cb0;">(Note: The optional Ask GoodQ voice agent is a hosted extension using ElevenLabs APIs. The core GoodQ4All memory system itself is 100% local and offline.)</sub>
</p>

<p align="center">
  <a href="https://github.com/GoodQ02/goodq4all/actions/workflows/ci.yml"><img src="https://github.com/GoodQ02/goodq4all/actions/workflows/ci.yml/badge.svg" alt="CI Status" /></a>
  <a href="https://github.com/GoodQ02/goodq4all/actions/workflows/doc-drift-lint.yml"><img src="https://github.com/GoodQ02/goodq4all/actions/workflows/doc-drift-lint.yml/badge.svg" alt="Doc Drift Linter" /></a>
  <a href="https://github.com/GoodQ02/goodq4all/actions/workflows/dependency-review.yml"><img src="https://github.com/GoodQ02/goodq4all/actions/workflows/dependency-review.yml/badge.svg" alt="Dependency Review" /></a>
  <a href="https://context7.com/goodq02/goodq4all"><img src="https://img.shields.io/badge/Context7-Verified-059669?style=flat" alt="Context7 Verified" /></a>
</p>

---

## ⚡ The Local-First Multimodal Memory Stack

GoodQ4All is a **100% private, offline alternative** to cloud-based media intelligence services. It ingests video, audio, and text files into queryable, structured scene-level memories, persisting the knowledge graph and vector representations locally on your computer.

Following a strict **"proof-backed" system doctrine**, GoodQ4All documents every perception step, tracks evidence manifests, and logs a comprehensive audit trail so that every memory claim can be verified.

---

### 🎬 From Media to Memory

*   **Get This Level of Local Control (Unified Operator UI):**
    <p align="center">
      <a href="samples/assets/ui_onboarding_walkthrough.mp4">
        <img src="samples/assets/ui_onboarding_walkthrough.gif" alt="UI Onboarding Walkthrough" width="850" style="max-width: 100%; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);" />
      </a>
      <br />
      <em>Click the preview above to watch the high-fidelity onboarding video.</em>
    </p>

*   **From Video Quality as Low as This: (Raw Media Inputs):**
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

*   **Using This All-in-One Installer (Unified Windows Offline Installer):**
    <p align="center">
      <a href="https://github.com/GoodQ02/goodq-memory-engine/releases" style="display: inline-block; padding: 16px 32px; background-color: #ffb300; color: #110d1a; font-size: 1.15em; font-weight: bold; text-decoration: none; border-radius: 6px; box-shadow: 0 4px 15px rgba(255, 179, 0, 0.4); transition: all 0.2s ease; margin: 10px 0;">
        🚀 Download GoodQ4All v3.0.0 Offline Release
      </a>
    </p>
    
    > [!IMPORTANT]
    > **System Requirement: Windows 11 (64-bit).** GoodQ4All is a standalone, local-first system that runs 100% offline without external cloud dependencies.
    >
    > *   **Available Profiles:**
    >     - **CPU Baseline (`PUBLIC_CPU_BASELINE`)**: Lightweight CPU execution requiring ~35 GB free disk space.
    >     - **GPU Enhanced (`PUBLIC_GPU_ENHANCED`)**: High-performance multimodal pipeline accelerated by NVIDIA CUDA 12.1 (requires 8GB+ VRAM and ~160 GB free disk space during installation).
    > *   **Bundle Contents:** Each release includes `GoodQ4All_Setup_2.5.8.exe`, `LAUNCH_GOODQ.exe`, signed payload packs (`payloads/*.zip`), and the release manifest (`GoodQ4All_Setup_2.5.8.release_manifest.json`).
    > *   **SmartScreen & Elevation:** Windows SmartScreen may present an "Unknown Publisher" prompt for self-signed releases. Click **More info** → **Run anyway**. Administrator rights are required for the default install location (`Program Files\GoodQ4All`).
    > *   **Checksum Verification:** Verify asset integrity prior to installation using PowerShell:
    >     ```powershell
    >     Get-FileHash GoodQ4All_Setup_2.5.8.exe -Algorithm SHA256
    >     ```
 
    <p align="center">
      <a href="https://github.com/GoodQ02/goodq-memory-engine/releases">
        <img src="samples/assets/one_click_installer_mockup.png" alt="GoodQ4All One-Click Setup Installer" width="550" style="max-width: 100%; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.15);" />
      </a>
    </p>

---

## 🛡️ Core Capabilities & Architecture

### 1. Proof-Backed Ingestion & Hardened API Facade
Machine memory should earn every claim it makes. GoodQ4All generates step-by-step logs (`step_runs.jsonl`), scene manifests, and intermediate features for every ingested file.
*   **Single-Use Confirmation Tokens**: Ingestion submission routes are protected by a server-generated token handshake with single-use nonce validation, preventing unauthenticated/out-of-bounds execution.
*   **Epistemic Verification**: Ingestion is tracked using verifiable manifests and SQLite-backed relational schemas.
*   **No Silent Failures**: The Control Agent and Watchdog processes bubble errors directly to the operator consoles, providing absolute visibility into the execution stack.

### 2. Local Model Governance & VRAM Budgeting
To run large-parameter local models safely on consumer hardware (e.g. RTX 4060 / 4070 Ti SUPER) without Out-of-Memory (OOM) crashes, GoodQ4All implements strict VRAM and execution controls:
*   **Model Lifecycle Manager**: A specialized context manager (`lib/model_lifecycle.py`) that audits free VRAM using PyTorch and `nvidia-smi` before loading models, dynamically evicting idle networks from GPU memory and providing automatic CPU fallback for memory-constrained visual embeddings.
*   **Local Agent Stack (`MiniAgentClient`)**: Gated LLM reasoning and local tool execution through zero-dependency policy enforcement middleware, loading schemas, policies, and contracts dynamically from the version-controlled `agents/stack/` directory.
*   **Endpoint Fallback Orchestration**: Automatically falls back from the primary local vLLM server (`prefer_speed`, running Qwen2.5) to a local Ollama service (`prefer_quality`, running Phi-4) or a CPU-safe model variant when VRAM thresholds are breached.

### 3. TurboQuant Hybrid Vector Caching
High-precision 32-bit floating point embeddings are persisted in Qdrant and FAISS. For rapid candidate filtering, GoodQ4All uses **TurboQuant**—an SQLite sidecar caching technology employing Lloyd-Max Polar Quantization and Johnson-Lindenstrauss residual projections.
*   **Performance:** Achieves sub-millisecond candidate pre-filtering.
*   **Accuracy:** 100% search accuracy is maintained by performing the final rank scoring on the uncompressed raw float32 vectors.

> [!NOTE]
> **Hybrid Precision Caching Model**:
> GoodQ4All uses an additive **sidecar vector cache** architecture. High-precision 32-bit floating point (`float32`) embeddings remain the authoritative truth of the system, stored in Qdrant and FAISS. Performance-oriented query pre-filtering is handled via lightweight **TurboQuant** fields (Lloyd-Max Polar Quantization + Johnson–Lindenstrauss residual corrections) stored in SQLite. This ensures zero data loss, guarantees rollback capability, and cuts memory usage.

### 4. Adaptive Hardware Profiles
The pipeline dynamically adjusts its computational needs to match your system specs:
*   `BASELINE` (CPU-safe): Fully operational, offline-ready execution on standard CPU hardware. Bypasses GPU requirements gracefully.
*   `GPU_ENHANCED`: Activates local NVIDIA GPU (CUDA 12.1) acceleration for rapid video segmentation, object detection, DINOv2 / CLIP visual embeddings, and CLAP audio embedding.

---

## ⚙️ Setup Paths

### Route A: Standalone User Installation (Recommended)
GoodQ4All provides an isolated embedded Python runtime, native Qdrant vector database, FFmpeg/Poppler/Tesseract binaries, and pre-staged model packs in a single managed installer:
1.  **Download & Extract:** Download the release bundle for your desired profile (`PUBLIC_CPU_BASELINE` or `PUBLIC_GPU_ENHANCED`) from [GitHub Releases](https://github.com/GoodQ02/goodq-memory-engine/releases). Ensure the `payloads/` directory sits alongside `GoodQ4All_Setup_2.5.8.exe`.
2.  **Install:** Run `GoodQ4All_Setup_2.5.8.exe` (or execute `GoodQ4All_Setup_2.5.8.exe /S` for a silent install). The installer extracts dependencies, verifies payload cryptographic signatures, and registers runtime paths.
3.  **Launch:** Double-click the **GoodQ4All** desktop shortcut or run `LAUNCH_GOODQ.exe`.
4.  **Explore & Ingest:** Open the **Retro Memory Explorer** in your browser at `http://127.0.0.1:30000/ui/retro_console_v1/`. Drag-and-drop video/audio files onto the **Upload Pad** to begin local offline ingestion.

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
| 7 | Start Watchdog, then copy one small media file into the import inbox zone (defaults to %USERPROFILE%\GoodQ_Data\import_inbox\):<br>`conda run --no-capture-output -n goodq_core python -m cli.watchdog` | <a href="samples/assets/demo-steps/07-watchdog-observes.jpg"><img src="samples/assets/demo-steps/07-watchdog-observes.jpg" alt="Watchdog observes the imported media file" width="300" /></a> |
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
*   Install: [`docs/bootstrap/INSTALL_BOOTSTRAP.md`](docs/bootstrap/INSTALL_BOOTSTRAP.md)
*   Historical quickstart: [`docs/archive/guides/install/QUICKSTART.md`](docs/archive/guides/install/QUICKSTART.md)
*   Clean memory start: [`docs/guides/CLEAN_MEMORY_START.md`](docs/guides/CLEAN_MEMORY_START.md)
*   Historical privacy guide: [`docs/archive/guides/general/PRIVACY.md`](docs/archive/guides/general/PRIVACY.md)

### Technical Details
*   Architecture: [`docs/architecture/SYSTEM_ARCHITECTURE.md`](docs/architecture/SYSTEM_ARCHITECTURE.md)
*   Memory Storage: [`docs/architecture/MEMORY_STORAGE.md`](docs/architecture/MEMORY_STORAGE.md)
*   Hybrid Caching: [`docs/architecture/TURBOQUANT_HYBRID_CACHING.md`](docs/architecture/TURBOQUANT_HYBRID_CACHING.md)
*   Current Agent State: [`docs/agent/CURRENT_STATE.md`](docs/agent/CURRENT_STATE.md)
*   RAG Context Pack: [`docs/GOODQ_RAG_CONTEXT_PACK.md`](docs/GOODQ_RAG_CONTEXT_PACK.md)

---

## 📄 License

MIT. See [`LICENSE`](LICENSE).
