<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-27 -->

# Architecture Diagrams

This folder contains GitHub-renderable Markdown and Mermaid diagrams for the
active GoodQ4All architecture.

## Diagrams

- [Pipeline Flow](PIPELINE_FLOW.md)
  - canonical ingestion flow, scene truth, memory layer, audio runtime, control observability, and retrieval
- [Knowledge Graph Architecture](knowledge_graph_architecture.md)
  - epoch-scoped KG schema, identity ladder, edge families, and audit/query flow
- [Watchdog Flow](watchdog_flow.md)
  - import inbox monitoring, queueing, state transitions, and canonical ingestion boundary

## Rendering Notes

- Mermaid blocks use conservative `flowchart` and `sequenceDiagram` syntax for GitHub rendering.
- These diagrams avoid local machine paths and secret-bearing examples.
- Runtime truth still lives in persisted artifacts and canonical docs; diagrams are visual summaries, not replacement contracts.

## Canonical Contracts

- [System Architecture](../SYSTEM_ARCHITECTURE.md)
- [Architecture Reference](../ARCHITECTURE_REFERENCE.md)
- [Ingest Orchestration Contract](../INGEST_ORCHESTRATION_CONTRACT.md)
- [Memory Storage](../MEMORY_STORAGE.md)
- [Identity Stitching Contract](../IDENTITY_STITCHING_CONTRACT.md)
- [Scene Manifest Specification](../SCENE_MANIFEST_SPECIFICATION.md)
