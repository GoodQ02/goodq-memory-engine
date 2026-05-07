<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_EXECPLAN -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

# Docs And Root Forensics ExecPlan

Status: ACTIVE
Branch: main
Public-safe: yes

This ExecPlan is subordinate to `AGENTS.md` and the canonical GoodQ runtime
contracts. It must be updated as work proceeds.

## Purpose / Operator Outcome

Create a project-wide map of documentation and root-level surfaces so future
operators can tell what is current, historical, duplicated, unclear, stale, or
unknown without relying on chat history.

## Scope Lock

Allowed:
- Read repo-root files and directories.
- Read every file under `docs/`.
- Use git metadata, file metadata, headings, badges, links, and internal text
  evidence to build a timeline and risk map.
- Create or update this ExecPlan only while the audit is active.

Forbidden:
- No ingestion.
- No package installation or environment mutation.
- No config mutation.
- No ControlAgent activation or healing.
- No generated recurrence reports or witness artifacts.
- No deletion, archive pruning, or broad cleanup.
- No treating archived docs as current runtime authority.
- No staging local reports, scratch artifacts, secrets, or machine-specific
  paths.

## Current Evidence

- `docs/architecture/GOODQ_EXECPLAN_PROTOCOL.md` requires restartable plans for
  broad, multi-session, drift-sensitive work.
- Full inventory after creating this ExecPlan found 610 files under `docs/`: 583
  markdown files, 20 text files, 5 JSON files, 1 PowerShell file, and 1
  backup-suffixed file.
- Active/archive split: 202 active docs outside `docs/archive/`, 408 archived
  docs under `docs/archive/`.
- Active link/title hygiene is strong: no broken active relative links found
  and no duplicate active H1 title groups found in this pass.
- Active metadata hygiene needs a follow-up pass: 124 active docs have no
  `DOC_STATUS`, 29 older active docs predate March 2026 without a status marker,
  and one canonical active doc lacks `DOC_LAST_VERIFIED`.
- Root inventory shows active source, generated/local temp folders, runtime
  data/report folders, and several potential hygiene surfaces that need
  classification rather than immediate cleanup.
- Prior restart-doc memory says the most fragile surfaces are restart/handoff
  docs and missing linked witness/support docs.

## Progress

- [x] 2026-05-07 - Read `GOODQ_EXECPLAN_PROTOCOL.md` and confirmed this work
  deserves a restartable plan.
- [x] 2026-05-07 - Captured initial root and `docs/` inventory.
- [x] 2026-05-07 - Read and classify active docs outside `docs/archive/`.
- [x] 2026-05-07 - Read and classify archived docs for timeline and stale-claim
  handling.
- [x] 2026-05-07 - Cross-check links, local path leaks, TODO/stale language, duplicate
  titles, and root-level unknowns.
- [x] 2026-05-07 - Produce a concise findings report with risk classes and next surgical
  actions.
- [x] 2026-05-07 - Began docs organization cycle by strengthening the existing
  documentation authority spine instead of moving files.
- [x] 2026-05-07 - Rebadged `CONFIG_LOADING_CONTRACT.md` as current canonical
  authority and added verification metadata to `INSTALL_BOOTSTRAP.md`.
- [x] 2026-05-07 - Updated docs governance and the landing page with durable
  folder roles and a rule against new task-completion docs for ordinary fixes.
- [x] 2026-05-07 - Added explicit authority metadata to current contract docs
  that were already used as active architecture, read-model, sensitive-source,
  and scene-manifest truth surfaces.
- [x] 2026-05-07 - Marked key index surfaces as operational and marked
  `SCRIPT_REGISTRY.md` as a generated snapshot rather than runtime authority.
- [x] 2026-05-07 - Reclassified stale WSL audio setup/feasibility/GPU
  implementation notes as historical/reference material and corrected the
  GPU/LLM/WSL index so only current WSL runtime surfaces are presented as
  current authority.
- [x] 2026-05-07 - Removed workstation-specific GPU hardware claims from active
  GPU setup and optimization guides.
- [x] 2026-05-07 - Marked environment discovery/reconciliation files as
  generated snapshots and marked the old runtime authority memo as historical
  reference so it cannot outrank the current authority map.
- [x] 2026-05-07 - Reclassified older vision GPU implementation notes as
  historical/reference material and pointed current GPU navigation at the
  active vision pipeline contract.

## Surprises & Discoveries

- Observation: `docs/archive/` contains most of the historical mass and must be
  treated as timeline evidence, not current doctrine.
  Evidence: initial file inventory shows hundreds of archive documents across
  audits, phase reports, fix reports, and status reports.

- Observation: Active docs have good structural link hygiene but uneven
  authority metadata.
  Evidence: active relative link check returned zero broken links; active H1
  duplicate check returned zero duplicate title groups; active metadata scan
  found 124 blank status values.

- Observation: `docs/architecture/CONFIG_LOADING_CONTRACT.md` reads normative
  but still labels itself as a proposal and has no `DOC_STATUS`.
  Evidence: first heading is "Canonical Runtime Configuration Loading Contract
  (Proposal)" while the body defines current config authority expectations.

- Observation: WSL audio lane doctrine appears clean after the recent
  documentation work.
  Evidence: active docs contain `WSL_AUDIO_LANE_OBSERVED_FUNCTIONAL_DRIFT_CU128`
  and do not contain the rejected candidate/approved cu128 labels.

- Observation: Several tracked backup files live beside active step modules.
  Evidence: `steps/audio_diarize/step.py.backup_before_chunking`,
  `steps/audio_diarize/step.py.backup_pre_gpu_refactor`, and
  `steps/audio_transcribe/step.py.backup_pre_gpu_refactor` are tracked source-tree
  files outside `docs/archive/`.

- Observation: Local workspace artifacts remain present and intentionally
  unstaged.
  Evidence: untracked recurrence artifacts remain under
  `reports/control_recurrence/`, and this ExecPlan is the only untracked docs
  file created by the audit.

## Decision Log

- Decision: Run active docs before archive docs.
  Rationale: Current operator-facing truth must be protected before historical
  material is used to reconstruct project evolution.
  Date/Author: 2026-05-07 / Codex

- Decision: Treat this pass as read-only except for this ExecPlan.
  Rationale: The first goal is discovery and classification; corrections should
  be separate surgical follow-up seams.
  Date/Author: 2026-05-07 / Codex

- Decision: Do not move or rename documentation files in the first organization
  cycle.
  Rationale: The docs folder has been reorganized several times already; first
  stabilize authority and folder-role rules, then make evidence-backed moves in
  smaller follow-up commits.
  Date/Author: 2026-05-07 / Codex

## Plan Of Work

Milestone 1: Build machine-readable inventory.

- What changes: none beyond this ExecPlan.
- Why safe: metadata and text reads only.
- Touches: repo root and `docs/`.
- Proof: inventory counts, file age buckets, and authority-marker summaries.
- Stop if: unreadable files, unexpected binary files, or private path leakage is
  detected in active docs.

Milestone 2: Classify active documentation.

- What changes: none.
- Why safe: active docs are read and classified before any remediation.
- Touches: docs outside `docs/archive/`.
- Proof: every active doc has a category, authority status, last-verified
  status, and risk note when applicable.
- Stop if: a canonical doc contradicts another canonical doc on runtime
  authority, bootstrap lanes, ingestion ownership, or control-agent boundaries.

Milestone 3: Classify archive and timeline evidence.

- What changes: none.
- Why safe: archived docs are used only to understand evolution.
- Touches: `docs/archive/`.
- Proof: timeline buckets and duplicate/stale patterns.
- Stop if: archive material is linked from active docs without clear historical
  labeling.

Milestone 4: Root unknowns and final report.

- What changes: none.
- Why safe: root-level findings are classification only.
- Touches: root files and directories.
- Proof: root surface map with known, generated, local-only, source, docs,
  runtime data, and unknown buckets.
- Stop if: tracked source appears to depend on an unknown or obsolete root
  artifact.

## Concrete Commands

Run from repo root:

```powershell
git status --short --branch
rg --files docs
Get-ChildItem docs -Recurse -File
git ls-files
git log --name-status -- docs
```

Use repo-local test wrapper only if this plan later touches validation scripts:

```powershell
.\scripts\dev\run_pytest.ps1 <targeted tests> -q
```

## Validation And Acceptance

This plan is accepted when:

- Every file under `docs/` has been inventoried and classified.
- Active docs are separated from historical/archive docs.
- Known stale, duplicate, unclear, unconfigured, and unknown surfaces are listed
  with exact paths.
- A project timeline is reconstructed from docs and git evidence.
- No code, config, ingestion, package, ControlAgent, healing, report artifact,
  or public/private branch mutation occurs during the audit.

## Idempotence And Recovery

The audit can be rerun from this plan. If interrupted, resume from the first
unchecked item in `Progress`. Do not delete or move any discovered files without
a separate cleanup ExecPlan and explicit approval.

## Public / Private Handling

The plan is public-safe because it uses repository-relative paths only and does
not include private media names, local reports, secrets, or machine-specific
drive roots.

## Commit And Push Plan

No commit is required for a read-only audit report unless the operator approves
keeping this ExecPlan as a tracked artifact.

If approved later:

- Stage: `docs/superpowers/plans/2026-05-07-docs-root-forensics.md`
- Commit message: `docs: add docs root forensics execplan`
- Public: mirror only if no private findings are added.

## Outcomes & Retrospective

Pending audit completion.
