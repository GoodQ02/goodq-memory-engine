<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_POINTER -->
<!-- DOC_LAST_VERIFIED: 2026-11-04 -->

# GoodQ4All Agent & Copilot Communications Index

**Purpose:** Explain archived agent/Copilot records and route agents to the current bounded mission.

---

## What Lives Here

- `docs/archive/agent-comms/` – Historical agent-facing notes, checklists, cleanup summaries, Copilot/user-facing session summaries, and overnight work reports.
- `docs/archive/releases/SESSION_SUMMARY.md` – Historical release-focused session summary.

The former active agent-communications and Copilot communications directories have been retired. Treat archived files as historical snapshots only. Canonical technical behavior is defined in the primary architecture, status, platform, WSL, and troubleshooting docs.

## Current Resume Point

Start with the [agent office entrypoint](../../agent/README.md) and its reading
order; [PROJECT.md](../../../PROJECT.md) owns the current checkpoint and resume
seam. Generated `CURRENT_STATE.md` and `current_state.json` are dated evidence
projections or an explicitly unconfigured public template, not the active task
handoff. Use this index only to interpret archived agent/Copilot notes. Do not
route fresh agents through archived communications or the sealed basement
handoff before the current entrypoint. The
[next-session checkpoint](../../../PROJECT.md#next-session-checkpoint) records
what is closed, what remains unverified and the smallest unfinished step.
Do not create another handoff document or reopen old repairs to restate it.

The current checkpoint records published engineering fixes, passing hosted CI,
remaining audio quality findings and a read-only new-chat orientation scope.
`PROJECT.md` owns exact results, gates and deployment state. The October 24 OCR
checkpoint and October 13 full-rebuild draft are historical references, not the
current handoff or permission to restart implementation. Passing engineering
checks do not close independent quality or personal-use acceptance.

---

## Guidance-Oriented Agent Docs

- `docs/archive/agent-comms/README.md`
- `docs/archive/agent-comms/MORNING_CHECKLIST.md`
- `docs/archive/agent-comms/START_HERE_AFTER_WORK.md`
- `docs/archive/agent-comms/NEXT_STEPS.md`
- `docs/archive/agent-comms/WELCOME_BACK.md`
- `docs/archive/agent-comms/MODEL_LOADING_FIXES.md`

---

## Historical Session & Fix Logs (Agent)

These are snapshots, not canonical runtime docs:

- `docs/archive/agent-comms/ALL_ISSUES_RESOLVED.md`
- `docs/archive/agent-comms/CLEANUP_SUMMARY.md`
- `docs/archive/agent-comms/CLEANUP_VISUAL_GUIDE.txt`
- `docs/archive/agent-comms/COMMIT_MESSAGE.md`
- `docs/archive/agent-comms/COMMIT_SUCCESS.md`
- `docs/archive/agent-comms/DEDUPLICATION_COMPLETE.md`
- `docs/archive/agent-comms/DIAGNOSIS_SUMMARY.md`
- `docs/archive/agent-comms/IMPLEMENTATION_COMPLETE.md`
- `docs/archive/agent-comms/LINT_CLEAN_SESSION.md`
- `docs/archive/agent-comms/OVERNIGHT_AUDIT_SUMMARY.md`
- `docs/archive/agent-comms/RECENT_FIXES.md`
- `docs/archive/agent-comms/SCENE_DETECTION_BUG_FIXED.md`
- `docs/archive/agent-comms/SESSION_COMPLETE.txt`
- `docs/archive/agent-comms/SESSION_COMPLETE_20251015.md`
- `docs/archive/agent-comms/SESSION_SUMMARY_2025-10-18.md`
- `docs/archive/agent-comms/TRANSCRIPTION_FIX_APPLIED.md`
- `docs/archive/agent-comms/VALIDATION_AND_NEXT_STEPS.md`
- `docs/archive/agent-comms/WATCHDOG_CLEANUP.md`

Use only the references relevant to the current task; captured-state files and
historical reports below do not prove live runtime health:

- `docs/agent/README.md` for the reading order
- `PROJECT.md` for the bounded resume point
- `docs/agent/CURRENT_STATE.md` for dated evidence or the public template
- `docs/agent/current_state.json` for the matching evidence source
- `docs/agent/workflows/CLEAN_MEMORY_START.md`
- `docs/agent/workflows/EVIDENCE_FIRST_RUNTIME_REPAIR.md`
- `docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md`
- `docs/architecture/IDENTITY_STITCHING_CONTRACT.md`
- `docs/reference/WSL_AUDIO_RUNTIME.md`
- `docs/architecture/SCENE_MANIFEST_SPECIFICATION.md`
- `docs/goodq4all_agent_status.md`
- `docs/SYSTEM_SNAPSHOT.md`
- `docs/architecture/SYSTEM_ARCHITECTURE.md`
- `docs/architecture/ARCHITECTURE_REFERENCE.md`
- `docs/architecture/MEMORY_STORAGE.md`
- `docs/architecture/components/VISION_PIPELINE.md`
- `docs/systems/WATCHDOG_SYSTEM.md`
- `docs/agent/CONTROL_AGENT.md`
- `docs/architecture/PHASE6_MULTIMODAL_FUSION.md`
- `docs/reference/CLI-REFERENCE.md`
- `docs/technical/LIB_COMPONENTS.md`
- `docs/archive/HANDOFF_BASEMENT_PHASE.md` only as sealed historical basement record
- `CHANGELOG.md`

---

## Copilot/User Communications

- `docs/archive/agent-comms/MORNING_BRIEFING.md`
- `docs/archive/agent-comms/OVERNIGHT_INDEX.md`
- `docs/archive/agent-comms/OVERNIGHT_AUDIT_FINDINGS.md`
- `docs/archive/agent-comms/COMPREHENSIVE_ENHANCEMENT_PLAN.md`
- `docs/archive/agent-comms/OVERNIGHT_WORK_COMPLETE.md`
- `docs/archive/agent-comms/OVERNIGHT_MONITORING_REPORT.md`
- `docs/archive/agent-comms/SESSION_SUMMARY.md`

Release-level session summary:

- `docs/archive/releases/SESSION_SUMMARY.md`

---

## How Agents Should Treat These Docs

- Current scope and source first:
  - `docs/agent/README.md`
  - `PROJECT.md`
  - `docs/architecture/REPOSITORY_MAP.md`
  - `docs/releases/ROADMAP.md`
  - `docs/agent/workflows/CLEAN_MEMORY_START.md`
  - `docs/agent/workflows/EVIDENCE_FIRST_RUNTIME_REPAIR.md`
  - `docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md`
  - `docs/architecture/IDENTITY_STITCHING_CONTRACT.md`
  - `docs/reference/WSL_AUDIO_RUNTIME.md`
  - `docs/architecture/SCENE_MANIFEST_SPECIFICATION.md`
  - `docs/goodq4all_agent_status.md`
  - `docs/SYSTEM_SNAPSHOT.md`
  - `docs/architecture/SYSTEM_ARCHITECTURE.md`
  - `docs/architecture/ARCHITECTURE_REFERENCE.md`
  - `docs/architecture/MEMORY_STORAGE.md`
  - `docs/architecture/components/VISION_PIPELINE.md`
  - `docs/systems/WATCHDOG_SYSTEM.md`
  - `docs/agent/CONTROL_AGENT.md`
  - `docs/architecture/PHASE6_MULTIMODAL_FUSION.md`
  - `docs/reference/CLI-REFERENCE.md`
  - `docs/technical/LIB_COMPONENTS.md`
  - `CHANGELOG.md`
  - the platform / WSL / troubleshooting indexes
- Dated evidence when relevant: `docs/agent/CURRENT_STATE.md` and
  `docs/agent/current_state.json`; their capture time limits current-state claims.
- Historical context second:
  - use agent and Copilot communications to understand why earlier decisions were made and how past sessions approached specific fixes
