<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-11-06 -->
<!-- INSTRUCTION_REVIEW: documentation only; no runtime qualification -->

# GoodQ4All Agent Guidance

GoodQ4All is a local-first, persistent multimodal memory system. Scenes are its
atomic memory unit; SQLite, the knowledge graph, manifests and configured vector
stores hold durable state. Useful, traceable evidence from the user's media is
the goal. Implemented code or a healthy service alone does not prove acceptance.

## Authority and scope

- Private `JoesDomingo/goodq4all` on `dev` owns product development. Functional
  fixes land there before the downstream `GoodQ02/goodq-memory-engine` public
  `main` release mirror. GOOD-CUBE is the canonical workstation; followers do
  not redefine product authority.
- Follow the user's current task and existing authorization. `PROJECT.md` owns
  the bounded checkpoint; the [roadmap](docs/releases/ROADMAP.md#personal-daily-use-completion-2026-10-07)
  owns completion gates and work order. Neither authorizes later work by itself.
- Inspect branch, local changes and relevant source before editing. Preserve
  unrelated work and staging; keep the patch reviewable and reversible. Do not
  reconcile, reset or clean other worktrees as a startup step.
- For unfamiliar, cross-component or authority-sensitive work, read
  [orientation](docs/agent/PROJECT_ORIENTATION.md). Use the
  [repository map](docs/architecture/REPOSITORY_MAP.md) only to locate needed
  source, contracts and tests. Reuse established context; ordinary edits do not
  require a full reading stack, plan, skill chain or system audit.

## Personal-use completion standard

- Address a demonstrated defect, approved requirement, applicable quality check
  or proven redundancy. Keep unrelated refactoring, renaming and formatting
  separate. Retire superseded paths deliberately rather than leaving competing
  implementations; do not manually clean bundled dependencies or generated output.
- Behavioral repairs need original-failure evidence and verification through the
  affected production caller. Choose the smallest meaningful regression and
  integration checks; helper tests alone do not establish supported-path behavior.
  Reuse passing evidence on unchanged source unless a new failure, changed
  contract, explicit request or release gate requires a rerun.
- Current ingestion acceptance needs fresh source-to-consumer evidence bound to
  revision, resolved configuration, input hash, run and epoch. Existing media can
  prove historical output and current consumer compatibility. Consumer-only,
  UI and documentation changes do not inherently require re-ingestion.
- For pipeline acceptance, account for every selected stage, including
  orchestration and materialization outside the capability registry: intended
  purpose, applicable sample, persisted evidence and consumer or justified
  retention purpose. Distinguish supported absence, disabled, failed,
  unavailable and unverified. Optional failure may preserve core operation but
  cannot pass full-feature acceptance. The roadmap owns the detailed gates.
- Use existing applicable lint, format, type, test and validation commands.
  Report actual scope and existing versus introduced failures. Final acceptance
  requires resolution or a specifically explained, explicitly approved exception.
  Do not weaken checks, suppress failures, fabricate success or add tooling to
  redefine clean. After authorized cleanup, rerun affected acceptance checks.
- Report the outcome, checks and evidence, material limits and next bounded step.
  Keep verification separate from recovery commands, labeled
  **UNDO ONLY - not a verification step.**

## Runtime routing and safety

- Use the [operator skill](.agents/skills/goodq4all-operator/SKILL.md) for GoodQ
  runtime diagnosis, ingestion validation, approved cleanup and follower checks.
  Specialized behavior belongs in its owning contract/runbook. Canonical UCF
  source is `scripts/ucf/`, not historical agent-run copies.
- Destructive operations, ingestion, large re-ingestion, dependency/global
  environment changes, persistent architecture or contract changes, retirement
  affecting supported behavior or data compatibility, public publication, tags,
  branch deletion and destructive checkout reconciliation require authorization
  covering the action. Honor existing approval; ask only for a missing boundary.
- Resolve exact data targets and preserve recovery before mutation. A prefix,
  age, path name or historical receipt never makes data disposable. Prefer
  isolated test stores and existing project environments and runtime entrypoints.
- Live evidence owns current runtime claims. History, model output and memory
  are neither current proof nor permission. Generated state must be regenerated
  from its evidence source, never hand-edited or redated to imply fresh health.
- Keep secrets in the approved environment-backed store; never print or commit
  them. Preserve PII/PHI boundaries and local control; add no telemetry or
  phone-home behavior. Use environment abstractions instead of machine drive
  roots in portable docs/config. Critical failures must stay observable.
- `AUTO_LEARN` may read code/config but write only approved knowledge-workspace
  lessons, checklists and templates. It must not rewrite runtime policy, source,
  contracts or config, or independently commit/push product changes. Development
  changes remain explicit, static and reviewable.
