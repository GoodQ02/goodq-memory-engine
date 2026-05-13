<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-27 -->

# Architecture Documentation Index

This index maps the architecture folder. It does not define a new system and
does not replace the canonical ingestion path. Use it to find the current
runtime contracts, component contracts, visual diagrams, and historical
reference material without treating every file in this folder as equal
authority.

## Organization Rules

| Location | Intended contents |
| --- | --- |
| `docs/architecture/` | System-wide architecture contracts, runtime maps, memory contracts, and cross-component boundaries. |
| `docs/architecture/components/` | Subsystem-specific architecture contracts with narrow ownership. |
| `docs/architecture/diagrams/` | GitHub-renderable architecture diagrams and diagram index. |

Historical reports and old planning notes remain in place for link stability.
They are reference material only unless a current canonical document restates
the same claim.

## Read First

| Document | Role |
| --- | --- |
| [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) | Current high-level system architecture. |
| [ARCHITECTURE_REFERENCE.md](ARCHITECTURE_REFERENCE.md) | Current architecture reference and subsystem orientation. |
| [SYSTEM_MAP_v1.md](SYSTEM_MAP_v1.md) | Current control and memory system map. |
| [INGEST_ORCHESTRATION_CONTRACT.md](INGEST_ORCHESTRATION_CONTRACT.md) | Canonical ingestion ownership and orchestration boundary. |
| [MEMORY_STORAGE.md](MEMORY_STORAGE.md) | Current persisted memory and storage architecture. |
| [CONFIG_LOADING_CONTRACT.md](CONFIG_LOADING_CONTRACT.md) | Current layered config-loading contract. |

## Scene, Memory, and Identity Contracts

| Document | Role |
| --- | --- |
| [IDENTITY_STITCHING_CONTRACT.md](IDENTITY_STITCHING_CONTRACT.md) | Conservative identity stitching rules. |
| [EPISTEMIC_READ_MODEL.md](EPISTEMIC_READ_MODEL.md) | Evidence-aware scene read model. |
| [NON_ACTION_CONTRACT.md](NON_ACTION_CONTRACT.md) | Non-action / absence semantics contract. |
| [VISUAL_PROJECTION_CONTRACT_v1.md](VISUAL_PROJECTION_CONTRACT_v1.md) | Visual projection contract. |
| [../SCENE_MANIFEST_SPECIFICATION.md](../SCENE_MANIFEST_SPECIFICATION.md) | Scene manifest truth surface specification. |

## Agent and Control Boundaries

| Document | Role |
| --- | --- |
| [AGENT_DECISION_PROTOCOL.md](AGENT_DECISION_PROTOCOL.md) | Agent decision and coordination protocol. |
| [LLM_CLIENT_INJECTION_CONTRACT.md](LLM_CLIENT_INJECTION_CONTRACT.md) | LLM client injection boundary. |
| [AGENT_SYSTEM.md](AGENT_SYSTEM.md) | Historical mixed-state agent-system reference, not the active control-agent source of truth. |
| [../CONTROL_AGENT.md](../CONTROL_AGENT.md) | Current control-agent documentation. |
| [../CLI-REFERENCE.md](../CLI-REFERENCE.md) | Active read-only recurrence reporting commands. |

## Sensitive Source Contracts

| Document | Role |
| --- | --- |
| [CANONICAL_SENSITIVE_EVENTS.md](CANONICAL_SENSITIVE_EVENTS.md) | Canonical sensitive-event taxonomy. |
| [VAULT_TOKEN_RESOLVER_CONTRACT.md](VAULT_TOKEN_RESOLVER_CONTRACT.md) | Vault token resolver contract. |

## Subsystems and Diagrams

| Document | Role |
| --- | --- |
| [components/README.md](components/README.md) | Component architecture index. |
| [components/VISION_PIPELINE.md](components/VISION_PIPELINE.md) | Vision pipeline architecture contract. |
| [diagrams/README.md](diagrams/README.md) | Diagram index and GitHub rendering notes. |

## Compatibility and Historical Reference

| Document | Status |
| --- | --- |
| [PIPELINES.md](PIPELINES.md) | Active compatibility reference for historical pipeline definitions. |
| `NEXT_LAYER_IMPLEMENTATION_PLAN_2026-04-12.md` | Historical implementation plan name retained for provenance; not present in the public branch. |
| [narrative_layer.md](narrative_layer.md) | Descriptive narrative-layer reference. |
| [LEGACY_WORKFLOWS.md](LEGACY_WORKFLOWS.md) | Historical workflow reference. |
| [DATA_STRUCTURE.md](DATA_STRUCTURE.md) | Historical data-layout snapshot. |
| [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) | Historical project-layout snapshot. |
| [PORT_ARCHITECTURE_ASSESSMENT.md](PORT_ARCHITECTURE_ASSESSMENT.md) | Historical port/WSL assessment. |
| [DOCUMENTATION_REORGANIZATION_PLAN.md](DOCUMENTATION_REORGANIZATION_PLAN.md) | Historical documentation reorganization plan. |
| [DOCUMENTATION_REORGANIZATION_REPORT.md](DOCUMENTATION_REORGANIZATION_REPORT.md) | Historical documentation reorganization report. |
| [ORGANIZATION_COMPLETE_2025-11-15.md](ORGANIZATION_COMPLETE_2025-11-15.md) | Historical organization completion report. |
