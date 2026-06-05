<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-06-05 -->

# GoodQ4All Subsystems Index & Checklist

This index serves as the master blueprint mapping every core subsystem in GoodQ4All. It provides a structured audit checklist to track quality inspections, path hardening, and validation passes prior to final deployment.

---

## 🗺️ Master Subsystem Map

| Subsystem Name | Key Responsibility | Primary Folder/Files | Audit Status |
| :--- | :--- | :--- | :--- |
| **1. Packaging & Installer** | Offline dependency staging, path alignment, and recursive standard user folder write permission grants. | [scripts/install/](file:///l:/GOODCUBE/projects/goodq4all/scripts/install) | `[x]` Audited |
| **2. Watchdog Ingestion** | Directory polling (`import_inbox`), file locking, safe moves/renaming, and AI Control Agent integration. | [cli/watchdog.py](file:///l:/GOODCUBE/projects/goodq4all/cli/watchdog.py) | `[x]` Audited |
| **3. Ingestion Pipeline** | Orchestration of Phases 0-5 (WebRTC-VAD, Whisper, PySceneDetect, CLIP/DINOv2 embedding batching). | [cli/run_ingestion.py](file:///l:/GOODCUBE/projects/goodq4all/cli/run_ingestion.py) | `[ ]` Pending |
| **4. WSL2 Audio Lane** | Linux-accelerated speaker diarization, voice signature extraction, and speech emotion classification. | [wsl2_audio/](file:///l:/GOODCUBE/projects/goodq4all/wsl2_audio) | `[ ]` Pending |
| **5. Web API Server** | FastAPI server hosting queue management,timeline rendering, search routes, and serving retro UI consoles. | [api/](file:///l:/GOODCUBE/projects/goodq4all/api) | `[ ]` Pending |
| **6. Vector Database & Search** | Qdrant multimodal indexing, FAISS sub-indices integration, and hybrid search weights fusion. | [retrieval/](file:///l:/GOODCUBE/projects/goodq4all/retrieval) | `[ ]` Pending |
| **7. Relational & Graph Memory**| SQLite relational storage, schema upgrades, fact stitching, and temporal knowledge graph queries. | [steps/common/memory_store.py](file:///l:/GOODCUBE/projects/goodq4all/steps/common/memory_store.py) | `[ ]` Pending |
| **8. Control Agent & Healer** | Background LLM-powered diagnostics, config integrity healing, and error analysis recommendations. | [agents/](file:///l:/GOODCUBE/projects/goodq4all/agents) | `[ ]` Pending |

---

## 🔍 Detailed Subsystem Breakdown

### 1. Packaging & Installer Subsystem
- **Files**:
  - Installer Script: [goodq4all_installer.nsi](file:///l:/GOODCUBE/projects/goodq4all/scripts/install/goodq4all_installer.nsi)
  - Go Launcher: [LAUNCH_GOODQ.go](file:///l:/GOODCUBE/projects/goodq4all/scripts/install/LAUNCH_GOODQ.go)
  - Compiler Runner: [build_installer.bat](file:///l:/GOODCUBE/projects/goodq4all/scripts/install/build_installer.bat)
  - Staging Downloader: [sandbox_env_setup.py](file:///l:/GOODCUBE/projects/goodq4all/scripts/install/sandbox_env_setup.py)
- **Role**: Build a zero-dependency setup package bundling a portable Python 3.10 runtime, Qdrant database, and vendored packages. Sets up recursive standard user permissions on `C:\ProgramData\GoodQ4All` using `icacls` with SID `*S-1-5-32-545`.
- **Checklist**:
  - `[x]` NSIS installer aligned on `$APPDATA` with `SetShellVarContext all`.
  - `[x]` Recursive SID-based `icacls` Modify permission grant configured with `/T /C`.
  - `[x]` Go launcher Windows path resolution chains ProgramData and LOCALAPPDATA defensively.
  - `[x]` Startup path vitals logged to console immediately on launch.
  - `[x]` Successful compiler staging and setup packaging verifications.

---

### 2. Watchdog Ingestion Subsystem (Control Plane)
- **Files**:
  - Watchdog Engine: [watchdog.py](file:///l:/GOODCUBE/projects/goodq4all/cli/watchdog.py)
  - Safe Move helper: `safe_move_file` (resolves collisions, fallback copy/unlink across drives).
  - Progress Ledger: [progress_tracker.py](file:///l:/GOODCUBE/projects/goodq4all/steps/common/progress_tracker.py)
- **Role**: Monitors the inbox, checks file stability (stops growing), computes SHA256 hashes, locks records in `watchdog_state.json` to prevent duplicates, and delegates file ingest to `pipelines.direct_ingestion`.
- **Checklist**:
  - `[x]` Audit file stability wait timeouts under fast-write operations.
  - `[x]` Audit safe move collision limits and cross-drive copy fail-safe paths.
  - `[x]` Validate duplicate ingestion requests handling when a previous run failed.
  - `[x]` Test AI Control Agent callback hooks on copy/processing failures.

---

### 3. Phased Segmentation & Ingestion Pipeline
- **Files**:
  - Pipeline Ingestion Orchestrator: [run_ingestion.py](file:///l:/GOODCUBE/projects/goodq4all/cli/run_ingestion.py)
  - Direct Entrypoint: [direct_ingestion.py](file:///l:/GOODCUBE/projects/goodq4all/pipelines/direct_ingestion.py)
  - Phase Modules: [steps/](file:///l:/GOODCUBE/projects/goodq4all/steps) (normalization, WebRTC-VAD, frame visual feature extractors, Wav2Vec).
- **Role**: Coordinate chronological execution of Phase 0 (audio normalization), Phase 1 (WebRTC-VAD voice separation), Phase 3 (smart chunking), Phase 4 (WSL audio), Phase 5 (vectorized GPU scene detection), and Phase 6 (CLIP/DINOv2 visual embeddings and cross-modal fusion).
- **Checklist**:
  - `[ ]` Audit progressive ingestion window index resets (monotonically increasing scene checks).
  - `[ ]` Verify GPU budget mappings across CLIP, DINOv2, and PySceneDetect.
  - `[ ]` Validate scene skip/retry logic when resuming a partial pipeline execution.
  - `[ ]` Verify frame sampling seeking logic via Python-native OpenCV.

---

### 4. WSL2 Audio Lane Subsystem
- **Files**:
  - WSL Diarization step: [wsl_process_audio_diarization.py](file:///l:/GOODCUBE/projects/goodq4all/steps/audio/wsl_process_audio_diarization.py)
  - WSL Script assets: [wsl2_audio/](file:///l:/GOODCUBE/projects/goodq4all/wsl2_audio) (Whisper workers, environment setups).
- **Role**: Bridges Windows hosts to WSL2 Linux environments for accelerated Faster-Whisper transcription, speaker speaker-diarization, and speech emotion classifications.
- **Checklist**:
  - `[ ]` Audit WSL distro detection fallback logic when the target distro is changed.
  - `[ ]` Validate Python subprocess bindings and path translation (Windows roots to WSL mounts).
  - `[ ]` Test offline HuggingFace cache loading behavior in WSL (CRLF refs line endings).
  - `[ ]` Verify Pyannote pipeline load caches are passed explicitly to prevent remote checks.

---

### 5. Web API Server Subsystem
- **Files**:
  - Start Engine: [server.py](file:///l:/GOODCUBE/projects/goodq4all/api/server.py)
  - API Router: [runtime.py](file:///l:/GOODCUBE/projects/goodq4all/api/routes/runtime.py)
  - Main App: [main.py](file:///l:/GOODCUBE/projects/goodq4all/api/main.py)
  - User Console Interface: [retro_console_v1/](file:///l:/GOODCUBE/projects/goodq4all/ui/retro_console_v1)
- **Role**: Host the FastAPI server process serving console layouts, file upload overlays, video timelines, queue stats, and multimodal vector searches.
- **Checklist**:
  - `[ ]` Audit socket binding fallback logic on port conflicts.
  - `[ ]` Audit token redacting filters inside uvicorn log handlers (security/privacy).
  - `[ ]` Verify progress tracker JSON freshness thresholds under slow pipeline steps.
  - `[ ]` Validate upload drag-and-drop panel integrations in retro memory explorer.

---

### 6. Vector Database & Search Subsystem
- **Files**:
  - Ingestion Index: [run_index.py](file:///l:/GOODCUBE/projects/goodq4all/lib/run_index.py)
  - Ingestion Summaries: [run_summary.py](file:///l:/GOODCUBE/projects/goodq4all/lib/run_summary.py)
  - Multimodal Search Engine: [retrieval/](file:///l:/GOODCUBE/projects/goodq4all/retrieval)
- **Role**: Handles vector collection creation and queries in Qdrant (CLIP, DINOv2, Text, Audio CLAP/Wav2Vec) and synchronizes equivalent IndexIDMap2 mappings inside local FAISS files.
- **Checklist**:
  - `[ ]` Validate vector index dimensional compatibility (768 for CLIP, 1024 for DINOv2).
  - `[ ]` Verify FAISS index parity checks and write locks during progressive uploads.
  - `[ ]` Audit hybrid multimodal retrieval fusion weights (text vs visual vs audio).
  - `[ ]` Test vector database connection loss healing routes.

---

### 7. Relational & Graph Memory Subsystem
- **Files**:
  - SQLite Handler: [memory_store.py](file:///l:/GOODCUBE/projects/goodq4all/steps/common/memory_store.py)
  - SQLite DBs: `memory.db` (relational metadata) and `knowledge_graph.db` (semantic connections).
- **Role**: Manage SQLite schema migration, write transaction locking, and query interfaces for scenes, dialogue transcriptions, entity linking, interaction metrics, and temporal facts.
- **Checklist**:
  - `[ ]` Audit SQLite write locks under concurrent ingestion status updates.
  - `[ ]` Audit entity normalization rules and identity stitching ladders.
  - `[ ]` Validate knowledge graph temporal relationship bindings (scene links).
  - `[ ]` Verify database read-only URI mapping when served via API.

---

### 8. Healer & Control Agent Subsystem
- **Files**:
  - Control Agent Engine: [control_agent.py](file:///l:/GOODCUBE/projects/goodq4all/agents/control_agent.py)
  - Command Launcher: [run_control_agent.py](file:///l:/GOODCUBE/projects/goodq4all/scripts/run_control_agent.py)
- **Role**: Monitor pipeline status, analyze failures (e.g. out of memory, file copy blocks) via LLM contexts, recommend healing configs, and compile trend recurrence reports.
- **Checklist**:
  - `[ ]` Audit LLM API connection timeout handling.
  - `[ ]` Verify read-only limitations (preventing unauthorized config adjustments/healing).
  - `[ ]` Validate recurrence trend diagnostics generation from historical JSON run records.
  - `[ ]` Test vLLM vs Ollama fallback switching under VRAM restrictions.
