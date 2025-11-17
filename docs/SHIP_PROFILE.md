# GoodQ4All Shipping Profile

**Purpose:** Define the supported, “shippable” surface of GoodQ4All – the commands, environments, and documentation that must remain stable for production use.

---

## Core Runtime Assumptions

- **Platform:** Windows 11 with WSL2 enabled.
- **GPU:** NVIDIA RTX-class GPU with 16 GB VRAM (e.g. RTX 4070 Ti SUPER).
- **Python/Conda:** Python 3.10 and the `goodq_zenml` base environment installed.
- **Data Layout:** Project at `L:\goodq4all\` with data under `L:\_DATA\GoodQ_Data\`.

---

## Supported Entry Points (Must Not Break)

### Launch & Control

- `LAUNCH_GOODQ.bat` – Primary launcher (API + Command Center + docs).
- `START_WATCHDOG.bat` – Start automatic ingestion (Watchdog).
- `MONITOR_WATCHDOG.bat` / `CHECK_WATCHDOG_STATUS.bat` – Watchdog monitoring.

### Manual Ingestion

- `conda run -n goodq_zenml python cli/run_ingestion.py ingest <video_path>` – CLI ingestion.

### Health & Readiness

- `python scripts/system_readiness_check.py` – System/env readiness.
- `python scripts/cache_readiness_check.py` – Model/dataset cache readiness.

### LLM & vLLM

- `python scripts/test_llm_client.py` – LLM client/vLLM connectivity.
- WSL2 vLLM scripts under `~/vllm_server/scripts/*.sh` (e.g. `start_llama1b.sh`) – start primary vLLM models.

---

## Canonical Documentation (Source of Truth)

### Getting Started & Usage

- `docs/user-guides/QUICK_START_CLEAN.md` – Canonical Quick Start.
- `docs/guides/USER_GUIDE.md` – Detailed user guide.
- `docs/reference/QUICK_INDEX.md` – Index for quickstart/quickref docs.

### Architecture & Status

- `docs/ARCHITECTURE_REFERENCE.md` – Canonical architecture reference.
- `docs/COMPREHENSIVE_ARCHITECTURE_RESEARCH_2025-11-15.md` – Deep-dive architecture snapshot.
- `docs/project-history/CHANGELOG.md` – Project timeline (newest entries first).
- `docs/CURRENT_SYSTEM_STATUS.md` – Canonical current system status.

### Pipeline Phases & Audits

- `docs/phases/PHASE_INDEX.md` – All phase reports/milestones.
- `docs/audits/AUDIT_INDEX.md` – Audits, diagnostics, and test reports.

### GPU, LLM, WSL2 & Watchdog

- `docs/GPU_LLM_WSL_INDEX.md` – GPU + LLM/vLLM + WSL2 + Watchdog index.
- `docs/GPU_SETUP.md`, `docs/GPU_MANAGEMENT_GUIDE.md`, `docs/GPU_OPTIMIZATION_GUIDE.md` – GPU configuration and optimization.
- `docs/LLM_INFRASTRUCTURE.md`, `docs/LLM_CLIENT_GUIDE.md`, `docs/vllm-integration-complete.md` – LLM/vLLM infrastructure and client.
- `docs/WSL2_AUDIO_SETUP.md`, `docs/WSL_AGENT_BRIEFING.md`, `docs/wsl2/START_HERE_WSL2.md` – WSL2 + audio stack.
- `docs/WATCHDOG_INDEX.md`, `docs/WATCHDOG_GUIDE.md`, `docs/WATCHDOG_QUICKREF.md` – Watchdog usage and architecture.

### Code Cleanup & Legacy Mapping

- `docs/CODE_CLEANUP_INDEX.md` – Index of lower-usage/legacy scripts for manual review.

---

## Environments Considered In-Scope

- Base orchestration: `goodq_zenml`.
- Vision/audio/text steps: the `goodq_*` step environments documented in:
  - `docs/ENVIRONMENT_INDEX.md`
  - `docs/PHASE_1_GPU_FINAL_SUMMARY.md`
  - `docs/GPU_SETUP.md`

Environments not referenced in these docs, or clearly marked as experimental, are considered out-of-scope for the shipping profile.

---

## Out-of-Scope / Historical Material

The following are **not** part of the shippable surface, though they are preserved for history:

- Anything under `_ARCHIVE/` (for example `_ARCHIVE/goodq4all_docs/...`).
- Legacy READMEs and early quickstarts superseded by the canonical docs listed above.
- Older GPU/LLM/phase/audit planning documents explicitly labeled as “Historical” in their index files.

When making changes for a release, prefer:

- Updating the canonical docs and commands listed here.
- Keeping historical docs intact or moving them to `_ARCHIVE` instead of editing them.
