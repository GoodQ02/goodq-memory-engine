<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

# GoodQ4All GPU, LLM, and WSL2 Index

**Purpose:** Single current entrypoint for GPU optimization, local LLM/vLLM
infrastructure, and optional WSL2 audio/operator docs.

---

## Canonical GPU Docs

- `docs/guides/gpu/GPU_SETUP.md` – Base GPU setup and verification.
- `docs/guides/gpu/GPU_MANAGEMENT_GUIDE.md` – GPU management patterns.
- `docs/guides/gpu/GPU_OPTIMIZATION_GUIDE.md` – System-wide GPU optimization.
- `docs/guides/gpu/GPU_QUICK_START.md` – Day-to-day GPU operator quickstart.
- `docs/architecture/components/VISION_PIPELINE.md` – Current vision architecture contract.

Historical vision GPU implementation notes remain useful for background, but
they do not override the current vision pipeline contract or live witness
artifacts.

## Canonical LLM and vLLM Docs

- `docs/guides/llm/LLM_INFRASTRUCTURE.md` – Current local LLM architecture.
- `docs/guides/llm/LLM_CLIENT_GUIDE.md` – Current client contract and usage.
- `docs/guides/llm/VLLM_SYSTEMD_SETUP.md` – Advanced vLLM operator setup for WSL/systemd hosts.

## Current WSL2 Audio Docs

- `docs/reference/WSL_AUDIO_RUNTIME.md` – Canonical WSL audio runtime and bootstrap lane doctrine.
- `wsl2_audio/README.md` – Worker-local setup and runtime notes.
- `docs/guides/wsl2/START_HERE_WSL2.md` – Redirect to current install/bootstrap entrypoints.

Historical WSL2 setup, feasibility, and benchmark notes are useful background
only. They do not override the current WSL audio runtime contract or bootstrap
constraints.

## Related Watchdog Docs

- `docs/guides/watchdog/WATCHDOG_INDEX.md` – Watchdog entrypoint.
- `docs/guides/watchdog/WATCHDOG_GUIDE.md` – Canonical Watchdog guide.
- `docs/guides/watchdog/WATCHDOG_QUICKREF.md` – Watchdog quick reference.
- `docs/guides/watchdog/WATCHDOG_CHANGELOG.md` – Watchdog history.

## Historical Context

These remain useful as archive-only background, not current operator guidance:

- `docs/archive/reports/GPU_CONFIGURATION_REPORT.md`
- `docs/archive/reports/VISION_GPU_OPTIMIZATION_REPORT.md`
- `docs/archive/phases/PHASE2_WSL2_COMPLETE.md`
- `docs/archive/phases/PHASE3_LLM_INTEGRATION_COMPLETE.md`
- `docs/archive/phases/VLLM_INTEGRATION_PLAN.md`
- `docs/archive/phases/WSL2_AUDIO_MIGRATION_GUIDE.md`
- `docs/archive/reports/WSL2_AUDIO_SUMMARY.md`
- `docs/archive/audits/WSL2_COMPLETE_AUDIT_DEC15.md`
- `docs/archive/reports/WATCHDOG_SUMMARY.md`
