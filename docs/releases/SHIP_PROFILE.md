<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-02-12 -->

# GoodQ4All Shipping Profile

**Purpose:** Define the supported, “shippable” surface of GoodQ4All – the commands, environments, and documentation that must remain stable for production use.

**Release stability note:** the current public-facing software version is
`0.1.0`. Treat this shipping profile as a pre-1.0 contract: the supported
bootstrap path and canonical runtime surface are the priority, while APIs and
adjacent helper tooling may still evolve between releases.

---

## Core Runtime Assumptions

- **Platform:** Windows 11 desktop is canonical host; laptop follower is supported.
- **Profiles:** `UNSET` (legacy canonical behavior), `BASELINE` (CPU-safe), `GPU_ENHANCED` (additive acceleration).
- **GPU:** Optional by profile; NVIDIA RTX-class GPU is required only for `GPU_ENHANCED` throughput goals.
- **WSL2 audio:** Optional by profile; required only when WSL audio acceleration is selected.
- **Python/Conda:** Python 3.10 and the `goodq_core` base environment installed.
- **Data Layout:** Project at `<project_root>\` with data root from `GOODQ_DATA_ROOT` (default `<GOODQ_DATA_ROOT>`).

## Profile Contract

- **UNSET:** Preserve legacy canonical behavior.
- **BASELINE:** Force CPU-safe defaults; no GPU/WSL requirement for correctness.
- **GPU_ENHANCED:** Enable existing CUDA-first and WSL acceleration paths for throughput.
- **Strict flags:** `GOODQ_REQUIRE_GPU=1` and `GOODQ_REQUIRE_WSL_AUDIO=1` convert optional acceleration into fail-fast requirements.

---

## Supported Entry Points (Must Not Break)

### Launch & Control

- `LAUNCH_GOODQ.bat` – Primary launcher (API + Command Center + docs).
- `LAUNCH_GOODQ.ps1` – PowerShell launcher for the canonical Windows host.
- `python -m cli.watchdog` – Start automatic ingestion (Watchdog).
- `python scripts/utils/check_watchdog_status.py` – Watchdog status utility.

### Manual Ingestion

- `conda run -n goodq_core python cli/run_ingestion.py ingest <video_path>` – CLI ingestion.

### Health & Readiness

- `python scripts/system_readiness_check.py` – System/env readiness.
- `python scripts/cache_readiness_check.py` – Model/dataset cache readiness.

### LLM & vLLM

- `python scripts/test_llm_client.py` – LLM client/vLLM connectivity.
- WSL2 vLLM scripts under `~/vllm_server/scripts/*.sh` (e.g. `start_llama1b.sh`) – optional throughput stack.

---

## Canonical Documentation (Source of Truth)

### Getting Started & Usage

- `docs/guides/install/QUICKSTART.md` – Public quick start.
- `docs/guides/general/USER_GUIDE.md` – Detailed user guide.
- `docs/reference/indexes/QUICK_INDEX.md` – Index for quickstart/quickref docs.

### Architecture & Status

- `docs/architecture/ARCHITECTURE_REFERENCE.md` – Canonical architecture reference.
- `docs/SYSTEM_SNAPSHOT.md` – Current system snapshot.
- `docs/goodq4all_agent_status.md` – Current agent/runtime status.
- `docs/archive/project-history/CHANGELOG.md` – Historical project timeline.

### Pipeline Phases & Audits

- `docs/archive/phases/PHASE_INDEX.md` – Historical phase reports and milestones.
- `docs/archive/audits/AUDIT_INDEX.md` – Historical audits and diagnostics.

### GPU, LLM, WSL2 & Watchdog

- `docs/guides/gpu/GPU_LLM_WSL_INDEX.md` – GPU + LLM/vLLM + WSL2 + Watchdog index.
- `docs/guides/gpu/GPU_SETUP.md`, `docs/guides/gpu/GPU_MANAGEMENT_GUIDE.md`, `docs/guides/gpu/GPU_OPTIMIZATION_GUIDE.md` – GPU configuration and optimization (`GPU_ENHANCED` tier).
- `docs/guides/llm/LLM_INFRASTRUCTURE.md`, `docs/guides/llm/LLM_CLIENT_GUIDE.md`, `docs/guides/llm/VLLM_SYSTEMD_SETUP.md` – LLM/vLLM infrastructure, client behavior, and advanced operator setup.
- `docs/guides/llm/WSL2_AUDIO_SETUP.md`, `docs/guides/llm/VLLM_SYSTEMD_SETUP.md`, `docs/guides/wsl2/START_HERE_WSL2.md` – optional WSL2 audio acceleration stack and advanced WSL/vLLM operator setup.
- `docs/guides/watchdog/WATCHDOG_INDEX.md`, `docs/guides/watchdog/WATCHDOG_GUIDE.md`, `docs/guides/watchdog/WATCHDOG_QUICKREF.md` – Watchdog usage and architecture.

### Code Cleanup & Legacy Mapping

- `docs/reference/indexes/CODE_CLEANUP_INDEX.md` – Index of lower-usage/legacy scripts for manual review.

### Validation & Release

- `CHANGELOG.md` – Public-facing release milestones and readiness checkpoints.
- `THIRD_PARTY_NOTICES.md` – Public-facing summary of vendored components, model downloads, and upstream licensing caveats.
- `docs/archive/audits/RELEASE_CHECKLIST.md` – Historical pre-release validation checklist.
- Current witness-backed release baseline:
  - `reports/seinfeld_experiment/diagnostics/SEASON1_WITNESS_RUN_2026-03-09.md`
  - `reports/seinfeld_experiment/diagnostics/POST_WITNESS_ANALYTICS_COMPARISON_2026-03-09.md`
  - `reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/`

---

## Environments Considered In-Scope

- Base orchestration: `goodq_core`.
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
