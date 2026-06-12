<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-05 -->

# GoodQ ExecPlan Protocol

This document defines the GoodQ version of an execution plan, or ExecPlan.
An ExecPlan is a self-contained operator plan for work that is too large,
risky, or restart-sensitive to live only in chat history.

This protocol is subordinate to `AGENTS.md` and the canonical runtime
contracts. If this document conflicts with `AGENTS.md`,
`docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md`, or another canonical
runtime contract, the stricter GoodQ safety rule wins.

## Purpose

Use a GoodQ ExecPlan when a future agent or human must be able to restart a
task from the plan alone and still preserve GoodQ doctrine.

The goal is not ceremony. The goal is continuity without drift: one file that
states the purpose, evidence, boundaries, exact work, validation, decisions,
and remaining risks clearly enough that a new operator can continue safely.

## When To Use One

Create or maintain a GoodQ ExecPlan for:

- offline bundle rebuilds or installer packaging
- multi-session bootstrap or portability work
- risky cleanup involving large generated artifacts
- schema or contract work that affects multiple consumers
- long witness campaigns that need durable monitoring instructions
- migrations that must be resumable after interruption
- public/private branch alignment where omissions can mislead future agents

Do not require an ExecPlan for:

- a single focused unit-test patch
- a small documentation correction
- a read-only audit that reports and stops
- a trivial typo or broken link fix

When unsure, write a short plan. A small accurate plan is better than a large
stale one.

## Non-Negotiable Boundaries

A GoodQ ExecPlan must not authorize:

- bypassing `cli/run_ingestion.py`
- creating a second ingestion engine
- activating `ControlAgent`
- enabling healing or config mutation unless the user explicitly approves that
  exact scope
- changing model versions or package lanes without a dedicated audit
- broad ingestion reruns before targeted proof
- backfilling Qdrant or mutating old vectors without explicit approval
- hiding optional enrichment failures
- treating public references as runtime truth overrides
- staging generated reports, local scratch artifacts, or secrets

The plan may describe future possibilities, but it must label them as future
work and keep them outside the current execution boundary.

## Relationship To GoodQ Contracts

Every GoodQ ExecPlan must name the contracts it relies on. Common anchors are:

- `AGENTS.md`
- `docs/architecture/AGENT_DECISION_PROTOCOL.md`
- `docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md`
- `docs/architecture/SCENE_MANIFEST_SPECIFICATION.md`
- `docs/architecture/PHASE6_MULTIMODAL_FUSION.md`
- `docs/reference/WSL_AUDIO_RUNTIME.md`
- `docs/architecture/AUDIO_VECTOR_PROVENANCE_CONTRACT.md`
- `docs/architecture/OUTPUT_SCHEMA_INVENTORY.md`
- `docs/agent/CONTROL_AGENT.md`

Do not repeat every contract in full. Do restate the exact rule that matters
for the current work.

## Required Qualities

A GoodQ ExecPlan must be:

- **Self-contained:** a new operator can understand the task without chat
  history.
- **Evidence-based:** the plan states the artifacts, logs, tests, or audits
  that justify the work.
- **Scoped:** the plan names what can be touched and what must not be touched.
- **Observable:** success is proven by concrete commands, artifacts, or
  outputs.
- **Restartable:** progress and decisions are updated as work proceeds.
- **Idempotent where possible:** repeated steps should be safe or have a clear
  recovery path.
- **Conservative:** when evidence is incomplete, the plan pauses or narrows
  rather than widening silently.

## Required Sections

Use these sections unless there is a strong reason to add a more specific one.
Keep the document prose-first, but use checkboxes in `Progress`.

### Status

State whether the plan is:

- `DRAFT`
- `ACTIVE`
- `SEALED`
- `DEFERRED`
- `RETIRED`

Also state the current branch, expected working tree state, and whether the
plan is private-only or public-safe.

### Purpose / Operator Outcome

Explain what changes after the work is complete. Phrase this in operator terms:
what can someone do, inspect, run, or trust that they could not before?

### Scope Lock

List allowed files, directories, commands, and systems. Then list forbidden
ones. This section must be explicit enough to prevent accidental cleanup,
ingestion, package upgrades, or public/private leakage.

### Current Evidence

Summarize the facts that justify the plan. Name the local artifacts, tests,
logs, run roots, or docs that were inspected. If evidence is historical or may
be stale, say so.

### Progress

Use checkboxes and timestamps. Every stopping point must leave the plan
restartable.

Example:

- [x] 2026-05-05T12:00Z - Audited old offline bundle root and identified stale
  WSL cu128 lane evidence.
- [ ] Rebuild staged payload from current `main`.
- [ ] Validate new bundle without creating packaged installer artifacts.

### Surprises & Discoveries

Record unexpected facts and short evidence snippets. This is where the next
operator learns why a seemingly obvious shortcut was avoided.

Example:

- Observation: Old bundle contained four copies of the same stale payload
  generation.
  Evidence: size audit showed staged payload, installer payload, archive, and
  self-extracting installer each present.

### Decision Log

Record decisions in this shape:

- Decision: ...
  Rationale: ...
  Date/Author: ...

Decisions must explain the why, not only the what.

### Plan Of Work

Describe the sequence of work in milestones. Each milestone should have:

- what changes
- why it is safe
- what files or systems it touches
- what command proves it
- what would cause the milestone to stop

### Concrete Commands

List exact commands and the working directory. Prefer commands that are safe to
rerun. Use environment variables or repository-relative paths; do not add
machine-specific drive roots to active docs.

For destructive operations, include the prior containment check and the exact
target list. Never use wildcard deletion as the documented first path.

### Validation And Acceptance

State what success looks like. Use behavior, not vibes.

Good examples:

- `python -m pytest tests/unit/test_bootstrap_install_wsl.py` passes.
- `git grep` finds no approved/candidate cu128 WSL audio language.
- a generated report contains no local drive-root paths.
- a recurrence report parses as JSON and classifies recovered optional retries
  as non-blocking.

Bad examples:

- "looks good"
- "code added"
- "should work"

### Idempotence And Recovery

Explain how to safely rerun the plan or recover from interruption. If a step is
destructive, state what was preserved and what must be regenerated.

### Public / Private Handling

If public branch work is possible, state whether the plan is public-safe.

Public-safe work must not include:

- private run roots
- local reports
- secrets or token files
- machine-specific paths
- private media names unless already intentionally public

### Commit And Push Plan

Commits must be scoped to sealed seams. Do not use `git add -A`.

Each commit plan must list:

- exact files to stage
- validation already run
- commit message
- branch to push
- whether public also needs a matching change

Frequent commits are allowed only when each commit is independently coherent,
validated, and reversible. Do not commit simply because time passed.

### Outcomes & Retrospective

At seal or deferral, summarize:

- what was actually achieved
- what was intentionally not changed
- validation evidence
- remaining watch items
- next recommended move

## Prototype Rules

Prototypes are allowed only when they reduce risk and remain bounded.

A GoodQ prototype must:

- be labeled as a prototype
- avoid canonical ingestion unless explicitly approved
- avoid persistence mutation unless the prototype is specifically about
  persistence and has an approved temp target
- write to temp fixtures or scratch paths only
- include a retirement rule

Parallel implementations are allowed only as temporary adapters or experiments.
They must not become a second runtime authority.

## Deletion And Cleanup Rules

Cleanup can be part of an ExecPlan, but only after audit.

Before deletion, the plan must identify:

- exact paths
- resolved containment root
- approximate size
- why the item is obsolete
- what will be preserved
- how to verify removal

Deletion commands must use exact literal paths. Do not document wildcard
deletion as the safe path.

## Offline Bundle Addendum

Offline bundle work is especially sensitive because stale payloads can
reintroduce old runtime doctrine.

Any offline bundle ExecPlan must prove:

- source branch and commit used for the staged repo
- WSL audio bootstrap lane and constraints file included
- wheelhouse contents match current doctrine or are explicitly labeled missing
- model cache excludes incomplete downloads unless intentionally retained
- token-like files are excluded
- generated installer artifacts are created only after the staged payload passes
  validation
- old bundles are removed from circulation rather than saved as active legacy
  references

## Recommended Skeleton

Copy this skeleton when creating a new GoodQ ExecPlan:

    # <Short GoodQ ExecPlan Title>

    Status: DRAFT
    Branch: <branch>
    Public-safe: yes/no

    This ExecPlan is subordinate to `AGENTS.md` and the canonical GoodQ runtime
    contracts. It must be updated as work proceeds.

    ## Purpose / Operator Outcome

    <What this enables and how an operator can see it working.>

    ## Scope Lock

    Allowed:
    - <paths/commands/systems>

    Forbidden:
    - <paths/commands/systems>

    ## Current Evidence

    <Audit facts and source artifacts.>

    ## Progress

    - [ ] <timestamp> - <step>

    ## Surprises & Discoveries

    - Observation: ...
      Evidence: ...

    ## Decision Log

    - Decision: ...
      Rationale: ...
      Date/Author: ...

    ## Plan Of Work

    <Milestones in prose.>

    ## Concrete Commands

    <Exact commands and working directory.>

    ## Validation And Acceptance

    <Expected behavior and test commands.>

    ## Idempotence And Recovery

    <Safe rerun or recovery path.>

    ## Public / Private Handling

    <Branch and artifact handling.>

    ## Commit And Push Plan

    <Exact staged files and commit message after validation.>

    ## Outcomes & Retrospective

    <Filled at seal or deferral.>

## Final Rule

A GoodQ ExecPlan is a leash, not a steering wheel. It preserves context and
discipline, but it does not grant new authority. Runtime authority still lives
in the canonical contracts and the user's explicit approval.
