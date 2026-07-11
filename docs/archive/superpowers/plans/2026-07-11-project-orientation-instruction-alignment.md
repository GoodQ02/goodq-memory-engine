<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_CANONICAL_POINTER: ../../../agent/PROJECT_ORIENTATION.md -->
<!-- DOC_ARCHIVED_ON: 2026-07-11 -->

> **Archived completion record:** This plan produced
> [PROJECT_ORIENTATION.md](../../../agent/PROJECT_ORIENTATION.md). It is
> non-canonical historical evidence and must not be re-executed. Unchecked boxes
> preserve the plan's original authoring state; completion is established by the
> verified orientation checkpoint, not by rewriting historical checklist marks.

# Timeless Project Orientation and Instruction Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Do not delegate this plan; the operator requested one coordinating agent.

**Status:** COMPLETED AND VERIFIED. Do not re-execute this plan. It is retained
as the reviewable implementation record for the instruction-alignment pass.

**Execution note:** A clean documentation worktree was attempted and immediately
removed when its baseline lint revealed that it lacked the main checkout's
already-in-progress archival reclassification. With explicit operator approval,
the documented non-overlapping edits were applied to the active tree instead;
the R02 worktree and public checkout remained untouched.

**Goal:** Create one timeless GoodQ project orientation and align active agent instruction surfaces so new agents understand the multi-root project, resolve conflicting evidence correctly, and do not repeat completed work.

**Architecture:** `docs/agent/PROJECT_ORIENTATION.md` becomes the operational first-read explanation for the whole project. Existing `AGENTS.md` files retain scoped rules and point to that overview instead of duplicating it. Worktree snapshots, public mirrors, upstream repositories, session histories, and cheat sheets remain classified evidence rather than being rewritten as authority.

**Tech Stack:** Markdown, JSON-backed documentation governance, PowerShell verification, existing GoodQ documentation lint tools.

## Global Constraints

- Documentation-only change; do not modify runtime code, data, services, model configuration, or Git branch topology.
- Preserve every pre-existing working-tree change and patch only non-overlapping documentation seams.
- Do not add live epoch names, counts, ports, process state, branch hashes, or current service status to the timeless overview.
- Repository documentation must use environment-relative aliases rather than literal drive roots.
- Do not edit the in-progress R02 worktree instruction snapshot or the downstream public checkout during this pass.
- Do not rewrite upstream-owned instruction files inside third-party source repositories.
- Historical Antigravity sessions, cheat sheets, archives, and chat summaries remain evidence only.

---

### Task 1: Create the timeless project orientation

**Files:**
- Create: `docs/agent/PROJECT_ORIENTATION.md`

**Interfaces:**
- Consumes: root `AGENTS.md`, documentation authority policy/map, canonical architecture contracts, GoodQ operator workflows, and the verified multi-root audit.
- Produces: one operational first-read document defining project topology, evidence authority, no-repeat preflight, component boundaries, worktree rules, and handoff practice.

- [ ] **Step 1: Write the orientation document**

Include these exact durable sections:

1. purpose and non-goals
2. one project, multiple roots
3. logical path aliases and how to resolve them
4. question-scoped authority ladder
5. durable truth versus transient state
6. pipeline, persistence, and agent/control-plane relationships
7. component write boundaries
8. mandatory no-repeat preflight
9. worktree, branch, and release-mirror doctrine
10. common false inferences
11. incoming-shift checklist
12. outgoing-shift handoff template

- [ ] **Step 2: Verify the document is timeless**

Run:

```powershell
Get-Content docs/agent/PROJECT_ORIENTATION.md |
  Select-Object -Skip 3 |
  rg -n "epoch_20|[0-9]{4}-[0-9]{2}-[0-9]{2}|127\.0\.0\.1|localhost|[A-Z]:[/\\]"
```

Expected: no live epoch, date, port, host, or literal-drive matches other than examples explicitly expressed through environment aliases.

### Task 2: Make the overview discoverable in repository authority surfaces

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/agent/README.md`
- Modify: `.agents/skills/goodq4all-operator/SKILL.md`
- Modify: `docs/agent/skills/goodq4all-operator/SKILL.md`
- Modify: `docs/bootstrap/doc_authority_map.md`
- Modify: `gemini.md`

**Interfaces:**
- Consumes: `docs/agent/PROJECT_ORIENTATION.md`.
- Produces: one consistent first-read order without replacing current-state or canonical contract documents.

- [ ] **Step 1: Patch the repository protocol**

Add the overview before current-state documents in the documentation reading order, resolve the knowledge workspace through the stable workstation shortcut instead of its backing drive, and correct the basement handoff pointer to `docs/archive/HANDOFF_BASEMENT_PHASE.md`.

- [ ] **Step 2: Patch the Agent Office index**

Describe the overview as timeless orientation and keep current-state files explicitly transient.

- [ ] **Step 3: Patch the authority map**

Add the overview under operational index surfaces. Preserve all pre-existing uncommitted authority-map edits.

### Task 3: Align workstation and Codex global instructions

**Files:**
- Modify: `%USERPROFILE%\AGENTS.md`
- Modify: `%USERPROFILE%\.codex\AGENTS.md`
- Modify: `%SYSTEMDRIVE%\Tools\AGENTS.md`
- Modify: `%SYSTEMDRIVE%\Tools\README.md`

**Interfaces:**
- Consumes: official Codex `AGENTS.md` discovery rules and the project orientation.
- Produces: a coherent global-to-project instruction chain that Codex actually loads.

- [ ] **Step 1: Add the primary-project and no-repeat rule to workstation guidance**

State that GOOD-CUBE development surfaces form one GoodQ project, while ordinary personal-computing tasks remain outside project scope.

- [ ] **Step 2: Make Codex global guidance self-sufficient**

Replace the unsupported assumption that Codex automatically loads `%USERPROFILE%\AGENTS.md` with a concise embedded set of mandatory workstation agreements. Consolidate the duplicate Context7 MCP/CLI procedures into one MCP-first rule with CLI fallback.

- [ ] **Step 3: Reclassify the tools root**

Define `%SYSTEMDRIVE%\Tools` as the machine-specific GoodQ control plane. Preserve nested upstream repository rules while preventing them from becoming independent product authorities.

### Task 4: Align active GoodQ integration instructions

**Files:**
- Modify: `%SYSTEMDRIVE%\Tools\hermes-runtime\AGENTS.md`
- Modify: `%SYSTEMDRIVE%\Tools\goodq-hermes-rag\AGENTS.md`
- Modify: `%SYSTEMDRIVE%\Tools\goodq-mini-agent-mcp\AGENTS.md`
- Modify: `%SYSTEMDRIVE%\Tools\hermes-ollama-gemma4\AGENTS.md`
- Modify: `%SYSTEMDRIVE%\Tools\openviking-runtime\AGENTS.md`

**Interfaces:**
- Consumes: repository orientation and each component's existing hard boundary.
- Produces: local component instructions that point to project authority without gaining new mutation power.

- [ ] **Step 1: Align Hermes authority and knowledge-workspace resolution**

Differentiate intended behavior authority from observed runtime truth, point GoodQ work to the project orientation, and resolve `_AGENT` through `%SYSTEMDRIVE%\Tools\AGENT_TRAINING.lnk`.

- [ ] **Step 2: Align bridge and governor semantics**

State that the RAG context pack is operational context that must match live configured stores, not independent canonical truth. State that the packaged governor is advisory and must be compared with the repository-embedded contract before upgrades.

- [ ] **Step 3: Align model and memory component roles**

State that the model runtime supplies inference but not pipeline authority, and that OpenViking memory supplies recall but not project truth or policy.

### Task 5: Align the shared Agent Knowledge Workspace

**Files:**
- Modify: `<agent_knowledge_root>/AGENT_HIERARCHY.md`
- Modify: `<agent_knowledge_root>/README_FOR_AGENTS.md`

**Interfaces:**
- Consumes: the workspace policy, repository orientation, and verified shortcut/junction resolution.
- Produces: a portable hierarchy that describes active authority without assuming mirrors are byte-identical.

- [ ] **Step 1: Patch the hierarchy**

Use logical root aliases, classify `%SYSTEMDRIVE%\Tools` as the integrated control plane, add portable-agent/governor roles, classify worktree instructions as branch snapshots, and classify the public checkout as a downstream release mirror rather than a byte-identical authority.

- [ ] **Step 2: Patch the workspace authority order**

Differentiate live evidence for actual state from code/contracts for intended behavior, and add the no-repeat preflight requirement.

- [ ] **Step 3: Run the Agent Knowledge Workspace verifier**

Run:

```powershell
$shell = New-Object -ComObject WScript.Shell
$agentRoot = $shell.CreateShortcut(
  "$env:SystemDrive\Tools\AGENT_TRAINING.lnk"
).TargetPath
conda run --no-capture-output -n goodq_core python "$agentRoot\verify_agent_workspace.py"
```

Expected: workspace verification passes with no conflict/native-document findings.

### Task 6: Validate instruction cohesion without touching runtime state

**Files:**
- Verify all files changed in Tasks 1-5.

**Interfaces:**
- Consumes: completed documentation changes.
- Produces: evidence that active instruction surfaces agree and existing implementation work remains untouched.

- [ ] **Step 1: Run repository documentation checks**

Run:

```powershell
conda run --no-capture-output -n goodq_core python scripts/docs/doc_drift_lint.py
git diff --check -- AGENTS.md docs/agent/PROJECT_ORIENTATION.md docs/agent/README.md docs/bootstrap/doc_authority_map.md
```

Expected: documentation lint passes; targeted diff check reports no new whitespace errors.

- [ ] **Step 2: Verify first-read and authority links**

Run:

```powershell
rg -n "PROJECT_ORIENTATION|CURRENT_STATE|doc_authority_map|HANDOFF_BASEMENT_PHASE" AGENTS.md docs/agent/README.md docs/bootstrap/doc_authority_map.md
```

Expected: the orientation precedes current-state documents, the authority map classifies it as operational, and the basement pointer targets `docs/archive/`.

- [ ] **Step 3: Verify external instruction convergence**

Run bounded searches confirming:

- `%SYSTEMDRIVE%\Tools` is called the GoodQ control plane.
- `_AGENT` resolves through the stable shortcut or logical alias.
- RAG context is not called canonical store truth.
- OpenViking memory is not project authority.
- the Codex overlay contains one Context7 procedure.

- [ ] **Step 4: Confirm no implementation state was added**

Compare targeted Git status with the pre-change baseline. Expected: only the planned documentation files are newly changed; the R02 worktree retains its original status count and is not modified.
