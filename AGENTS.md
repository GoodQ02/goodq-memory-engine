<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-09-26 -->
<!-- INSTRUCTION_REVIEW: 2026-09-25 -->

# GoodQ4All Agent Guidance

## Mission and identity

GoodQ4All is a local-first, persistent multimodal memory and intelligence system. Scenes are its primary memory unit. SQLite, the knowledge graph, scene manifests, and configured vector stores preserve durable state.

Prefer correctness, observability, portability, and recoverability over novelty. Optional enrichments may fail without making the core pipeline unusable.

## Authority

- `JoesDomingo/goodq4all` is the private development authority. Its canonical product branch is `dev`.
- `GoodQ02/goodq-memory-engine` is a downstream public release mirror whose canonical product branch is `main`.
- Functional corrections belong in private `dev` before public release.
- Public publication, tags, branch deletion, or destructive checkout reconciliation require explicit approval.
- Use live repository/runtime evidence for current state. Historical reports and handoffs are evidence, not present-state authority.

GOOD-CUBE is the canonical development workstation. Follower systems align from the canonical source rather than redefining it.

## Work proportionately

Make the smallest coherent change that solves the requested problem.

Preserve unrelated working behavior. Do not perform opportunistic refactors, broad cleanup, architecture changes, or full-system reruns unless the task requires them.

Read only the documentation needed for the current scope. Do not preload the whole documentation tree.

For unfamiliar, cross-component, or authority-sensitive GoodQ work, start with `docs/agent/PROJECT_ORIENTATION.md`. Then read only the relevant current-state document, workflow, contract, or subsystem reference.

Validate at the smallest useful scope first. Pipeline repairs should progress from focused evidence and scene-level validation toward broader witnesses only when justified.

## Operational routing

Use `.agents/skills/goodq4all-operator/SKILL.md` for repository runtime operations including ingestion validation, clean-memory work, evidence-first runtime repair, local fallback/audio repair, follower validation, and operator-facing documentation truth.

Use the relevant tracked architecture contract or workflow for specialized subsystem behavior rather than duplicating that doctrine here.

The canonical UCF implementation lives under `scripts/ucf/`; ignored or historical agent-run copies are not runtime authority.

## Safety and system integrity

- Require explicit approval for destructive operations, large re-ingestion, dependency or global-environment changes, public release actions, and changes that alter persistent architecture or contracts.
- Prefer existing project-local environments and established runtime entry points.
- Secrets belong in the approved environment-backed store and must never be printed, committed, or copied into documentation.
- Preserve privacy boundaries for PII/PHI and do not add telemetry or phone-home behavior.
- Do not introduce literal machine-specific drive roots into active portable documentation or configuration when an environment abstraction exists.
- Fail visibly: critical failures must remain observable and attributable rather than silently suppressed.

## AUTO_LEARN boundary

`AUTO_LEARN` may not rewrite runtime policy, source code, contracts, or configuration autonomously.

Automated lesson-learning agents may read repository code and configuration but may write only to the approved Agent Knowledge Workspace for lessons, checklists, and templates.

They must never independently commit or push product source changes. Changes to code, contracts, or policy remain explicit, static, reviewable development actions.

## Working rule

When existing evidence, a tracked skill, and a detailed reference already answer the question, reuse them rather than creating another instruction layer.