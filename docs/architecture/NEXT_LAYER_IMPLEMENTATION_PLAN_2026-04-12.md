<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-12 -->

# Next Layer Implementation Plan (2026-04-12)

## Purpose

Freeze the next implementation order after the validated Season 3 treatment campaign.

This memo is prework only. It does not authorize runtime changes by itself.

## Scope

This plan covers three follow-on capabilities that are already partially scaffolded in the repo:

1. self-auditing cognition
2. memory arbitration
3. episode and season consolidation

This memo does not promote identity expansion, world-model sandboxes, counterfactual memory, or forgetting logic.

## Why These Three

The current system now has a validated additive interpretation layer (`scene_context_llm`) and a validated additive self-audit surface (`scene_context_epistemic`).

The next safe move is not to add more interpretation. The next safe move is to:

- explain how scene conclusions were formed
- preserve disagreements instead of flattening them
- consolidate stable scene truth into higher-level memory only after that explanation surface exists

This preserves the current authority order:

- canonical scene truth first
- additive interpretation second
- abstraction third

## Existing Connection Points

### 1. Self-Auditing Cognition

Current scaffold already exists in:

- [cross_modal_harmonizer.py](../../steps/video/cross_modal_harmonizer.py)
- [epistemic_formatter.py](../../steps/common/epistemic_formatter.py)
- [non_action_contract.py](../../steps/common/non_action_contract.py)
- [EPISTEMIC_READ_MODEL.md](EPISTEMIC_READ_MODEL.md)
- [PHASE6_MULTIMODAL_FUSION.md](PHASE6_MULTIMODAL_FUSION.md)
- [SCENE_MANIFEST_SPECIFICATION.md](SCENE_MANIFEST_SPECIFICATION.md)

Relevant live surfaces already present:

- `scene_context_llm`
- `scene_context_epistemic`
- `segments_with_scene_context_epistemic`
- `top_scene_context_epistemic_states`
- `top_scene_context_epistemic_dominant_evidence`

### 2. Memory Arbitration

Current scaffold already exists in:

- [memory_router.py](../../steps/common/memory_router.py)
- [memory_context_writer.py](../../steps/common/memory_context_writer.py)
- [memory.py](../../steps/common/memory.py)
- [memory_manager.py](../../steps/common/memory_manager.py)
- [EPISTEMIC_READ_MODEL.md](EPISTEMIC_READ_MODEL.md)

Relevant current signals already present:

- transcript-backed scene context
- visual caption and object evidence
- audio emotion
- dominance and conversation owner
- `scene_context_epistemic.conflict_detected`
- `scene_context_epistemic.dominant_evidence`

### 3. Episode / Season Consolidation

Current scaffold already exists in:

- [identity_ledger.py](../../lib/identity_ledger.py)
- [narrative_layer.md](narrative_layer.md)
- [SEASON3_FIVE_EPISODE_CAMPAIGN_MEMO_2026-04-12.md](../testing/SEASON3_FIVE_EPISODE_CAMPAIGN_MEMO_2026-04-12.md)
- [SEASON3_EPISODE_FORENSIC_AUDIT_03x05_2026-04-12.md](../diagnostics/SEASON3_EPISODE_FORENSIC_AUDIT_03x05_2026-04-12.md)

Relevant existing mechanics:

- episode directory walking
- scene-to-episode mapping
- cross-scene identity evidence aggregation
- stable read-only narrative contract

## Recommended Build Order

### Phase A. Strengthen Self-Auditing Cognition

#### Goal

Make per-scene interpretation explain itself in a stable, retrievable way.

#### Scope

Additive only. No canonical truth overwrite.

#### Implementation Targets

1. Extend `scene_context_epistemic` conservatively.
2. Expose explicit explanation fields where the evidence is already known.
3. Keep all outputs descriptive, not gating.

#### Candidate Additions

- `evidence_family`
- `transcript_dominant`
- `visual_dominant`
- `audio_dominant`
- `low_signal_fallback`
- `conflict_detected`
- `limits`
- `next_steps`

#### Connection Points

- `_derive_scene_context_epistemic(...)` in [cross_modal_harmonizer.py](../../steps/video/cross_modal_harmonizer.py)
- epistemic vocabulary in [epistemic_formatter.py](../../steps/common/epistemic_formatter.py)
- scene manifest and temporal index rollups in [SCENE_MANIFEST_SPECIFICATION.md](SCENE_MANIFEST_SPECIFICATION.md)

#### Acceptance Criteria

- per-scene epistemic payload remains additive
- no canonical truth surfaces are modified by the new explanation fields
- rollups remain stable under full-episode reruns
- sample audits can answer "why did this scene say this?" from scene artifacts alone

### Phase B. Add Memory Arbitration

#### Goal

Preserve structured disagreement between evidence families instead of flattening scenes into one forced interpretation.

#### Scope

Additive only. Arbitration is read-model metadata, not canonical overwrite.

#### Implementation Targets

1. Introduce a scene-level arbitration payload.
2. Record when transcript, visual, audio, and identity signals disagree.
3. Preserve ranked hypotheses only when disagreement is real.

#### Candidate Additions

- `scene_context_arbitration`
- `hypotheses`
- `evidence_conflicts`
- `resolved_by`
- `unresolved_axes`

#### Connection Points

- scene-level evidence already assembled in [cross_modal_harmonizer.py](../../steps/video/cross_modal_harmonizer.py)
- persistence path in [memory_context_writer.py](../../steps/common/memory_context_writer.py)
- routing in [memory_router.py](../../steps/common/memory_router.py)

#### Acceptance Criteria

- arbitration never mutates `scene_manifest` truth fields in place
- conflicts are visible in scene artifacts and temporal indexes
- no regression in `phase6_complete`, `qdrant_ok`, or current scene-context gates

### Phase C. Episode / Season Consolidation

#### Goal

Lift stable scene-level truth into higher-order episode and season memory without breaking provenance.

#### Scope

Derived read-only outputs first. No destructive compaction.

#### Implementation Targets

1. Build episode-level motif and topic rollups.
2. Build season-level recurring topic and location summaries.
3. Keep provenance pointers back to scenes.

#### Candidate Outputs

- episode motif summaries
- recurring locations
- recurring topics
- stable social dynamics
- season-level topic clusters

#### Connection Points

- `scene_episode_map` and aggregation logic in [identity_ledger.py](../../lib/identity_ledger.py)
- read-only narrative discipline in [narrative_layer.md](narrative_layer.md)
- campaign witnesses and audits under `docs/testing/` and `docs/diagnostics/`

#### Acceptance Criteria

- consolidated outputs must point back to supporting scenes
- higher-order summaries must remain reversible to scene evidence
- no new authority surface is introduced without an explicit contract

## What To Defer

These are not the next move:

- identity-engine expansion beyond the current conservative stitching ladder
- counterfactual or prospective memory
- world-model sandboxing
- forgetting or pruning logic

These may become appropriate only after self-audit and arbitration are stable.

## Batch Discipline

Implementation should proceed in separate batches:

1. self-auditing cognition batch
2. memory arbitration batch
3. episode and season consolidation batch

Do not mix those with unrelated pipeline tuning.

## Validation Strategy

For each batch:

1. add focused unit tests
2. run one scene-level debug witness when applicable
3. run one untouched full-episode witness
4. publish a short audit memo before promoting the batch as validated

## Summary

The repo already contains the right skeleton for the next layer.

The correct path is not to invent a new cognition system. The correct path is to extend the existing epistemic and memory surfaces in order:

1. explain scene cognition
2. preserve disagreement
3. consolidate stable truth upward

That keeps GoodQ honest while making it smarter.
