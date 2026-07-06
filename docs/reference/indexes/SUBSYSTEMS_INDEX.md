<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-06-05 -->

# GoodQ4All Subsystems Index & Checklist

This index serves as the master blueprint mapping every core subsystem in GoodQ4All. It provides a structured audit checklist to track quality inspections, path hardening, and validation passes prior to final deployment.

---

## 🗺️ Master Subsystem Map

| Subsystem Name | Key Responsibility | Primary Folder/Files | Audit Status |
| :--- | :--- | :--- | :--- |
| **1. Packaging & Installer** | Offline dependency staging, path alignment, and recursive standard user folder write permission grants. | [scripts/install/](../../../scripts/install/) | `[x]` Audited |
| **2. Watchdog Ingestion** | Directory polling (`import_inbox`), file locking, safe moves/renaming, and AI Control Agent integration. | [cli/watchdog.py](../../../cli/watchdog.py) | `[x]` Audited |
| **3. Ingestion Pipeline** | Orchestration of Phases 0-5 (WebRTC-VAD, Whisper, PySceneDetect, CLIP/DINOv2 embedding batching). | [cli/run_ingestion.py](../../../cli/run_ingestion.py) | `[x]` Audited |
| **4. WSL2 Audio Lane** | Linux-accelerated speaker diarization, voice signature extraction, and speech emotion classification. | [wsl2_audio/](../../../wsl2_audio/) | `[x]` Audited |
| **5. Web API Server** | FastAPI server hosting queue management,timeline rendering, search routes, and serving retro UI consoles. | [api/](../../../api/) | `[x]` Audited |
| **6. Vector Database & Search** | Qdrant multimodal indexing, FAISS sub-indices integration, and hybrid search weights fusion. | [retrieval/](../../../retrieval/) | `[x]` Audited |
| **7. Relational & Graph Memory**| SQLite relational storage, schema upgrades, fact stitching, and temporal knowledge graph queries. | [steps/common/memory_store.py](../../../steps/common/memory_store.py) | `[x]` Audited |
| **8. Control Agent & Healer** | Background LLM-powered diagnostics, config integrity healing, and error analysis recommendations. | [agents/](../../../agents/) | `[x]` Audited |

---

## 🔍 Detailed Subsystem Breakdown

### 1. Packaging & Installer Subsystem
- **Files**:
  - Installer Script: [goodq4all_installer.nsi](../../../scripts/install/goodq4all_installer.nsi)
  - Go Launcher: [LAUNCH_GOODQ.go](../../../scripts/install/LAUNCH_GOODQ.go)
  - Compiler Runner: [build_installer.bat](../../../scripts/install/build_installer.bat)
  - Staging Downloader: [sandbox_env_setup.py](../../../scripts/install/sandbox_env_setup.py)
- **Role**: Build a zero-dependency setup package bundling a portable Python 3.10 runtime, Qdrant database, and vendored packages. Sets up recursive standard user permissions on `%PROGRAMDATA%\GoodQ4All` using `icacls` with SID `*S-1-5-32-545`.
- **Checklist**:
  - `[x]` NSIS installer aligned on `$APPDATA` with `SetShellVarContext all`.
  - `[x]` Recursive SID-based `icacls` Modify permission grant configured with `/T /C`.
  - `[x]` Go launcher Windows path resolution chains ProgramData and LOCALAPPDATA defensively.
  - `[x]` Startup path vitals logged to console immediately on launch.
  - `[x]` Successful compiler staging and setup packaging verifications.

---

### 2. Watchdog Ingestion Subsystem (Control Plane)
- **Files**:
  - Watchdog Engine: [watchdog.py](../../../cli/watchdog.py)
  - Safe Move helper: `safe_move_file` (resolves collisions, fallback copy/unlink across drives).
  - Progress Ledger: [progress_tracker.py](../../../steps/common/progress_tracker.py)
- **Role**: Monitors the inbox, checks file stability (stops growing), computes SHA256 hashes, locks records in `watchdog_state.json` to prevent duplicates, and delegates file ingest to `pipelines.direct_ingestion`.
- **Checklist**:
  - `[x]` Audit file stability wait timeouts under fast-write operations.
  - `[x]` Audit safe move collision limits and cross-drive copy fail-safe paths.
  - `[x]` Validate duplicate ingestion requests handling when a previous run failed.
  - `[x]` Test AI Control Agent callback hooks on copy/processing failures.

---

### 3. Phased Segmentation & Ingestion Pipeline
- **Files**:
  - Pipeline Ingestion Orchestrator: [run_ingestion.py](../../../cli/run_ingestion.py)
  - Direct Entrypoint: [direct_ingestion.py](../../../pipelines/direct_ingestion.py)
  - Phase Modules: [steps/](../../../steps/) (normalization, WebRTC-VAD, frame visual feature extractors, Wav2Vec).
- **Role**: Coordinate chronological execution of Phase 0 (audio normalization), Phase 1 (WebRTC-VAD voice separation), Phase 3 (smart chunking), Phase 4 (WSL audio), Phase 5 (vectorized GPU scene detection), and Phase 6 (CLIP/DINOv2 visual embeddings and cross-modal fusion).
- **Checklist**:
  - `[x]` Audit progressive ingestion window index resets (monotonically increasing scene checks).
  - `[x]` Verify GPU budget mappings across CLIP, DINOv2, and PySceneDetect.
  - `[x]` Validate scene skip/retry logic when resuming a partial pipeline execution.
  - `[x]` Verify frame sampling seeking logic via Python-native OpenCV.

---

### 4. WSL2 Audio Lane Subsystem
- **Files**:
  - WSL Diarization step: [process_audio.py](../../../wsl2_audio/process_audio.py)
  - WSL Script assets: [wsl2_audio/](../../../wsl2_audio/) (Whisper workers, environment setups).
- **Role**: Bridges Windows hosts to WSL2 Linux environments for accelerated Faster-Whisper transcription, speaker speaker-diarization, and speech emotion classifications.
- **Checklist**:
  - `[x]` Audit WSL distro detection fallback logic when the target distro is changed.
  - `[x]` Validate Python subprocess bindings and path translation (Windows roots to WSL mounts).
  - `[x]` Test offline HuggingFace cache loading behavior in WSL (CRLF refs line endings).
  - `[x]` Verify Pyannote pipeline load caches are passed explicitly to prevent remote checks.

---

### 5. Web API Server Subsystem
- **Files**:
  - Start Engine: [server.py](../../../api/server.py)
  - API Router: [runtime.py](../../../api/routes/runtime.py)
  - Main App: [main.py](../../../api/main.py)
  - User Console Interface: [retro_console_v1/](../../../ui/retro_console_v1/)
- **Role**: Host the FastAPI server process serving console layouts, file upload overlays, video timelines, queue stats, and multimodal vector searches.
- **Checklist**:
  - `[x]` Audit socket binding fallback logic on port conflicts.
  - `[x]` Audit token redacting filters inside uvicorn log handlers (security/privacy).
  - `[x]` Verify progress tracker JSON freshness thresholds under slow pipeline steps.
  - `[x]` Validate upload drag-and-drop panel integrations in retro memory explorer.

---

### 6. Vector Database & Search Subsystem
- **Files**:
  - Ingestion Index: [run_index.py](../../../lib/run_index.py)
  - Ingestion Summaries: [run_summary.py](../../../lib/run_summary.py)
  - Multimodal Search Engine: [retrieval/](../../../retrieval/)
- **Role**: Handles vector collection creation and queries in Qdrant (CLIP, DINOv2, Text, Audio CLAP/Wav2Vec) and synchronizes equivalent IndexIDMap2 mappings inside local FAISS files.
- **Checklist**:
  - `[x]` Validate vector index dimensional compatibility (768 for CLIP, 1024 for DINOv2).
  - `[x]` Verify FAISS index parity checks and write locks during progressive uploads.
  - `[x]` Audit hybrid multimodal retrieval fusion weights (text vs visual vs audio).
  - `[x]` Test vector database connection loss healing routes.

---

### 7. Relational & Graph Memory Subsystem
- **Files**:
  - SQLite Handler: [memory_store.py](../../../steps/common/memory_store.py)
  - SQLite DBs: `memory.db` (relational metadata) and `knowledge_graph.db` (semantic connections).
- **Role**: Manage SQLite schema migration, write transaction locking, and query interfaces for scenes, dialogue transcriptions, entity linking, interaction metrics, and temporal facts.
- **Checklist**:
  - `[x]` Audit SQLite write locks under concurrent ingestion status updates.
  - `[x]` Audit entity normalization rules and identity stitching ladders.
  - `[x]` Validate knowledge graph temporal relationship bindings (scene links).
  - `[x]` Verify database read-only URI mapping when served via API.

---

### 8. Healer & Control Agent Subsystem
- **Files**:
  - Control Agent Engine: [control_agent.py](../../../agents/control_agent.py)
  - Command Launcher: [run_control_agent.py](../../../scripts/run_control_agent.py)
- **Role**: Monitor pipeline status, analyze failures (e.g. out of memory, file copy blocks) via LLM contexts, recommend healing configs, and compile trend recurrence reports.
- **Checklist**:
  - `[x]` Audit LLM API connection timeout handling.
  - `[x]` Verify read-only limitations (preventing unauthorized config adjustments/healing).
  - `[x]` Validate recurrence trend diagnostics generation from historical JSON run records.
  - `[x]` Test vLLM vs Ollama fallback switching under VRAM restrictions.
