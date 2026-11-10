<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-11-06 -->
<!-- INSTRUCTION_REVIEW: documentation only; no runtime qualification -->

# Agent Decision Protocol

This protocol preserves pipeline truth during repair. `AGENTS.md` owns general
engineering/authorization rules; the [evidence-first repair workflow](../agent/workflows/EVIDENCE_FIRST_RUNTIME_REPAIR.md)
owns diagnosis and validation. Use the subsystem's runtime contract if it requires
more specific evidence. No automatic full-episode rerun or parallel-agent sequence
is required by this document.

## Invariants

- Scenes remain the atomic ingestion unit. Keep artifacts attributable to their
  scene boundary. Start ingestion diagnosis at the smallest useful scope; expand
  only when the tested behavior and authorization require it.
- Preserve persistence and Phase 6 validation contracts. A change to supported
  shapes/compatibility needs the explicit contract/retirement gate in `AGENTS.md`;
  avoid leaving competing implementations without a justified transition.
- Verify the actual caller and durable output. Evaluation may score output but
  cannot redefine runtime truth or grant promotion authority.
- External anchors (for example cast lists or transcripts) may score coverage,
  salience or hallucination. They must not overwrite canonical scene evidence,
  inject web facts into memory or outrank local transcript/audio/visual evidence.
- Keep an active witness's source/config stable. Independent evidence work must
  not mutate its runtime lane or mix fixes before attribution is established.

Owning contracts: [ingest orchestration](INGEST_ORCHESTRATION_CONTRACT.md),
[scene manifests](SCENE_MANIFEST_SPECIFICATION.md),
[Phase 6](PHASE6_MULTIMODAL_FUSION.md) and
[identity stitching](IDENTITY_STITCHING_CONTRACT.md).
