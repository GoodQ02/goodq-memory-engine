<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: PUBLIC_RELEASE_SNAPSHOT -->
<!-- DOC_LAST_VERIFIED: 2026-05-19 -->

# System Snapshot

This public snapshot describes the supported release posture for
GoodQ4All 0.1.1 - Epistemic Memory Preview. It is not a live workstation
inventory, not a hardware audit, and not proof that any specific private host
state should be copied into a public release.

## Release Host Contract

- Primary supported host: Windows 11.
- Runtime model: local-first, loopback-first, and CPU-safe by default.
- Optional acceleration: NVIDIA GPU and WSL2 audio paths may improve capability
  or speed when explicitly configured, but they are not required for the base
  preview posture.
- Required network posture: local services bind to loopback unless an operator
  deliberately overrides that setting.

## Supported Preview Surface

- CLI: canonical ingest and operator utilities.
- Watchdog/import inbox: supported automation surface for local file intake.
- API: local read/inspection surface, not a public cloud service.
- Operator Console v1: local read-only inspection cockpit served under
  `/ui/operator_console_v1/`.
- Justification Channel: local read-only envelope renderer served under
  `/ui/justification_v1/`.
- Durable evidence: scene manifests, temporal indexes, run summaries, SQLite
  state, knowledge graph state, and Qdrant vector state when configured.

## Explicit Non-Claims

- This is not a finished consumer application.
- This is not a healthcare, clinical, compliance, or emergency-response
  product.
- This is not a polished consumer memory browser release; current UI surfaces
  are read-only local operator inspection surfaces.
- This is not an autonomous control-agent or self-healing release.
- This is not a full offline installer release.
- This does not ship private memory, witness outputs, runtime databases, raw
  media, private home media, or Seinfeld/test-run memory as base memory.

## Packaging Boundary

The base release should create fresh local memory from operator-owned inputs.
Optional model caches, reference banks, corpus packs, synthetic debug fixtures,
and evaluation assets are separate packaging decisions. They must be reviewed
through the corpus/reference-pack docs before any payload movement.

Relevant docs:

- `docs/bootstrap/CORPUS_PACK_MANIFEST.md`
- `docs/bootstrap/CORPUS_PACK_INVENTORY_LEDGER.md`
- `docs/bootstrap/REFERENCE_PACK_V0_SELECTION_PROPOSAL.md`
- `docs/bootstrap/REFERENCE_PACK_V0_LICENSE_REVIEW_MATRIX.md`
- `docs/bootstrap/REFERENCE_PACK_V0_SOURCE_EVIDENCE_APPENDIX.md`

## First-Run Proof Path

The intended public proof path is narrow:

1. watch the guided demo or read `docs/guides/DEMO.md`
2. install/bootstrap the local runtime
3. start local services on loopback
4. ingest an operator-owned file through the supported local path
5. inspect generated scene artifacts and local API read surfaces
6. confirm failures remain visible rather than silently hidden

Use `docs/guides/FIRST_RUN.md` for the public first-run path.
