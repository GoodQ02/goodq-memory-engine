# GoodQ4All Agent & Copilot Communications Index

**Purpose:** Explain the role of `docs/agent-communications/` and `docs/copilot_user_communications/` and highlight which documents are guidance vs historical session logs.

---

## What Lives Here

- `docs/agent-communications/` – Agent-facing notes, checklists, cleanup summaries, and session-specific reports generated during development.
- `docs/copilot_user_communications/` – Copilot/user-facing session summaries and overnight work reports.
- `docs/releases/SESSION_SUMMARY.md` – Release-focused session summary.

Most files in these directories are historical snapshots of specific sessions. Canonical technical behavior is defined in the primary architecture, status, platform, WSL, and troubleshooting docs.

---

## Guidance-Oriented Agent Docs

- `docs/agent-communications/README.md`
- `docs/agent-communications/MORNING_CHECKLIST.md`
- `docs/agent-communications/START_HERE_AFTER_WORK.md`
- `docs/agent-communications/NEXT_STEPS.md`
- `docs/agent-communications/WELCOME_BACK.md`
- `docs/agent-communications/MODEL_LOADING_FIXES.md`

---

## Historical Session & Fix Logs (Agent)

These are snapshots, not canonical runtime docs:

- `docs/agent-communications/ALL_ISSUES_RESOLVED.md`
- `docs/agent-communications/CLEANUP_SUMMARY.md`
- `docs/agent-communications/CLEANUP_VISUAL_GUIDE.txt`
- `docs/agent-communications/COMMIT_MESSAGE.md`
- `docs/agent-communications/COMMIT_SUCCESS.md`
- `docs/agent-communications/DEDUPLICATION_COMPLETE.md`
- `docs/agent-communications/DIAGNOSIS_SUMMARY.md`
- `docs/agent-communications/IMPLEMENTATION_COMPLETE.md`
- `docs/agent-communications/LINT_CLEAN_SESSION.md`
- `docs/agent-communications/OVERNIGHT_AUDIT_SUMMARY.md`
- `docs/agent-communications/RECENT_FIXES.md`
- `docs/agent-communications/SCENE_DETECTION_BUG_FIXED.md`
- `docs/agent-communications/SESSION_COMPLETE.txt`
- `docs/agent-communications/SESSION_COMPLETE_20251015.md`
- `docs/agent-communications/SESSION_SUMMARY_2025-10-18.md`
- `docs/agent-communications/TRANSCRIPTION_FIX_APPLIED.md`
- `docs/agent-communications/VALIDATION_AND_NEXT_STEPS.md`
- `docs/agent-communications/WATCHDOG_CLEANUP.md`

For canonical status and current runtime truth, prefer:

- `docs/HANDOFF_BASEMENT_PHASE.md`
- `docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md`
- `docs/architecture/IDENTITY_STITCHING_CONTRACT.md`
- `docs/reference/WSL_AUDIO_RUNTIME.md`
- `docs/SCENE_MANIFEST_SPECIFICATION.md`
- `docs/goodq4all_agent_status.md`
- `docs/SYSTEM_SNAPSHOT.md`
- `docs/architecture/SYSTEM_ARCHITECTURE.md`
- `docs/architecture/ARCHITECTURE_REFERENCE.md`
- `docs/architecture/MEMORY_STORAGE.md`
- `docs/architecture/components/VISION_PIPELINE.md`
- `docs/systems/WATCHDOG_SYSTEM.md`
- `docs/CONTROL_AGENT.md`
- `docs/PHASE6_MULTIMODAL_FUSION.md`
- `docs/CLI-REFERENCE.md`
- `docs/technical/LIB_COMPONENTS.md`
- `CHANGELOG.md`

---

## Copilot/User Communications

- `docs/copilot_user_communications/MORNING_BRIEFING.md`
- `docs/copilot_user_communications/OVERNIGHT_INDEX.md`
- `docs/copilot_user_communications/OVERNIGHT_AUDIT_FINDINGS.md`
- `docs/copilot_user_communications/COMPREHENSIVE_ENHANCEMENT_PLAN.md`
- `docs/copilot_user_communications/OVERNIGHT_WORK_COMPLETE.md`
- `docs/copilot_user_communications/OVERNIGHT_MONITORING_REPORT.md`
- `docs/copilot_user_communications/SESSION_SUMMARY.md`

Release-level session summary:

- `docs/releases/SESSION_SUMMARY.md`

---

## How Agents Should Treat These Docs

- Primary truth first:
  - `docs/HANDOFF_BASEMENT_PHASE.md`
  - `docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md`
  - `docs/architecture/IDENTITY_STITCHING_CONTRACT.md`
  - `docs/reference/WSL_AUDIO_RUNTIME.md`
  - `docs/SCENE_MANIFEST_SPECIFICATION.md`
  - `docs/goodq4all_agent_status.md`
  - `docs/SYSTEM_SNAPSHOT.md`
  - `docs/architecture/SYSTEM_ARCHITECTURE.md`
  - `docs/architecture/ARCHITECTURE_REFERENCE.md`
  - `docs/architecture/MEMORY_STORAGE.md`
  - `docs/architecture/components/VISION_PIPELINE.md`
  - `docs/systems/WATCHDOG_SYSTEM.md`
  - `docs/CONTROL_AGENT.md`
  - `docs/PHASE6_MULTIMODAL_FUSION.md`
  - `docs/CLI-REFERENCE.md`
  - `docs/technical/LIB_COMPONENTS.md`
  - `CHANGELOG.md`
  - the platform / WSL / troubleshooting indexes
- Historical context second:
  - use agent and Copilot communications to understand why earlier decisions were made and how past sessions approached specific fixes
