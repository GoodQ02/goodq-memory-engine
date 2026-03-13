# GoodQ4All GPU, LLM, and WSL2 Index

**Purpose:** Single entrypoint for GPU optimization, LLM/vLLM integration, and WSL2/audio infrastructure documentation.

---

## GPU & Performance

### Canonical GPU Docs

- `docs/GPU_SETUP.md` – Base GPU setup and configuration.
- `docs/GPU_MANAGEMENT_GUIDE.md` – GPU management API and usage patterns.
- `docs/GPU_OPTIMIZATION_GUIDE.md` – Detailed GPU optimization strategies (system-wide).
- `docs/GPU_QUICK_START.md` – GPU quickstart for day-to-day use.
- `docs/GPU_PHASE_1_COMPLETE.md` / `docs/GPU_PHASE_1_TEST_RESULTS.md` – Phase 1 GPU validation.
- `docs/PHASE_1_GPU_FINAL_SUMMARY.md` – Phase 1 GPU final summary.
- `docs/VISION_GPU_OPTIMIZATION.md` / `docs/VISION_GPU_OPTIMIZATION_REPORT.md` – Vision-specific GPU optimization.
- `docs/AUDIO_GPU_IMPLEMENTATION_SUMMARY.md` – Audio GPU implementation overview.
- `docs/AUDIO_GPU_OPTIMIZATION.md` – Audio-specific GPU optimization details.
- `docs/VAD_AND_GPU_OPTIMIZATION_COMPLETE.md` – Combined VAD + GPU optimization summary.

### Historical GPU Fixes & Progress (Reference)

- `_ARCHIVE/goodq4all_docs/gpu/GPU_ALLOCATION_FIX.md` – Allocation bug fix details (superseded by optimization guides).
- `docs/GPU_FIX_SUMMARY.md` – Summary of early GPU-related fixes.
- `docs/GPU_REFACTOR_PROGRESS.md` – GPU refactor progress notes.
- `docs/GPU_SCENE_DETECTION_IMPLEMENTATION.md` – GPU scene detection internals (pre-final implementations).
- `docs/GPU_MONITORING_COMPLETE.md` – GPU monitoring implementation status.
- `_ARCHIVE/goodq4all_docs/gpu/GPU_OPTIMIZATION_SUMMARY.md` – Older high-level optimization outcomes.

---

## LLM & vLLM Integration

### Canonical LLM Stack Docs

- `docs/LLM_INFRASTRUCTURE.md` – Overall LLM stack design and architecture.
- `docs/LLM_CLIENT_GUIDE.md` – Production LLM client usage and behavior.
- `docs/LLM_PHASE1_COMPLETION_REPORT.md` – Phase 1 LLM integration completion.
- `docs/LLM_STATUS.md` – Current LLM integration status snapshot.
- `docs/VLLM_SYSTEMD_SETUP.md` – Advanced vLLM operator setup for WSL/systemd hosts.
- `docs/PHASE3_LLM_INTEGRATION_COMPLETE.md` – Phase 3 LLM integration in the wider pipeline.

### Historical Plans & Analyses (Reference)

- `docs/LLM_IMPLEMENTATION_PLAN_PHASE1.md` – Initial implementation plan (superseded by completion reports).
- `docs/LLM_INTEGRATION_ANALYSIS.md` – Early integration analysis and gap assessment.
- `docs/LLM_INTEGRATION_COMPLETE.md` – LM Studio-focused integration completion (pre-vLLM).
- `docs/VLLM_INTEGRATION_PLAN.md` – vLLM integration design plan (historical design reference; superseded by the current LLM infrastructure and operator setup docs).

---

## WSL2 & Audio Infrastructure

- `docs/wsl2/START_HERE_WSL2.md` – Primary WSL2 entrypoint
- `docs/WSL2_AUDIO_SETUP.md` – WSL2 audio setup guide
- `docs/WSL2_AUDIO_MIGRATION_GUIDE.md` – Migration from legacy audio setups
- `docs/wsl2/WSL2_AUDIO_FEASIBILITY_ANALYSIS.md` – Feasibility analysis
- `docs/wsl2/WSL2_AUDIO_SUMMARY.md` – Summary of WSL2 audio work
- `docs/wsl2/WSL2_BENCHMARKS.md` – Benchmarks for WSL2 audio/GPU
- `docs/VLLM_SYSTEMD_SETUP.md` – WSL vLLM service setup and advanced operator reference
- `docs/PHASE2_WSL2_COMPLETE.md` – Phase 2 WSL2 completion report

---

## Watchdog & Automation (Related Operational Context)

- `docs/WATCHDOG_INDEX.md` – Watchdog docs index and entrypoint.
- `docs/WATCHDOG_GUIDE.md` – Canonical Watchdog user guide.
- `docs/WATCHDOG_QUICKREF.md` – Quick reference for Watchdog commands.
- `docs/WATCHDOG_SUMMARY.md` – High-level Watchdog implementation summary.
- `docs/WATCHDOG_CHANGELOG.md` – Watchdog-specific changelog and history.
