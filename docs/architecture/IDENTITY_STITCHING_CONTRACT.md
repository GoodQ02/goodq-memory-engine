<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-08 -->

# Identity Stitching Contract

**Purpose:** define how GoodQ forms identity from audio, semantics, and scene evidence without hallucinating merges.  
**Scope:** speaker-pattern capture, candidate/support/evidence promotion, and explicit non-action rules.  
**Non-goals:** node merges, retrieval policy, UI behavior, or cross-run ranking logic.

This contract also does not define interaction-ownership fields such as `conversation_owner`. Those signals may summarize who an exchange revolves around, but they must not be treated as visual presence or identity promotion.

---

## Cross-References

- Epistemic evidence language: [EPISTEMIC_READ_MODEL.md](EPISTEMIC_READ_MODEL.md)
- Non-action guardrail language: [NON_ACTION_CONTRACT.md](NON_ACTION_CONTRACT.md)
- Memory integrity and persistence doctrine: [MEMORY_STORAGE.md](MEMORY_STORAGE.md)
- Canonical ingest authority: [INGEST_ORCHESTRATION_CONTRACT.md](INGEST_ORCHESTRATION_CONTRACT.md)

---

## Core Principle

Identity stitching is a convergence layer, not a guessing layer.

GoodQ may record that:
- a voice pattern is recurring
- a person name is recurring
- a face is recurring
- a speaker/person pairing is a candidate
- a conversation appears to revolve around a person

GoodQ must not claim identity merely because entities co-occurred in one scene.

---

## Definitions

### Structural identity

Structural nodes preserve raw modality truth without semantic overclaim:
- anonymous `speaker` nodes
- anonymous `face` nodes
- `speaker_pattern` nodes

These nodes may participate in identity edges, but they are not people.

### Semantic identity

Semantic identity is represented by `person` nodes resolved from transcript or visual entity extraction.

### `speaker_voice_signatures`

Per-speaker pooled voice signatures emitted by the WSL audio worker from diarized speech spans.

### `speaker_pattern`

A recurring voice-pattern node created from normalized speaker signatures when cosine similarity is strong enough to treat multiple scene-local speakers as the same recurring voice pattern.

### `voice_pattern_match`

An edge from a scene-local anonymous speaker node to a `speaker_pattern` node. This records recurring voice-pattern similarity only. It is not a person claim.

### `identity_candidate`

A weak, additive identity edge indicating that a structural node may correspond to a person under a narrow rule.

### `identity_supported`

A stronger additive identity edge indicating that the same candidate pattern repeated across multiple scenes without contradiction.

### `identity_evidence`

The strongest current identity edge in the stitching ladder. It indicates repeated, multi-episode agreement for a `speaker_pattern -> person` mapping without contradiction.

---

## Promotion Ladder

### 1. Voice -> Pattern

The WSL audio worker may emit `speaker_voice_signatures` only when speech is sufficiently stable:
- total voiced audio >= `4.0` seconds
- at least `2` usable segments
- each usable segment >= `0.75` seconds
- at most `4` segments are pooled

If those conditions are not met, the worker must emit:
- `speaker_voice_signatures = []`
- `speaker_voice_signature_meta.status = "skipped"`
- `speaker_voice_signature_meta.reason = "insufficient_diverse_speech"`

When a valid signature exists, GoodQ may:
- create a new `speaker_pattern`, or
- attach to an existing `speaker_pattern`

Current runtime match rule:
- cosine similarity >= `0.92`

This stage records recurring voice-pattern stability only.

### 2. Pattern -> Candidate Person

GoodQ may emit `identity_candidate` for a `speaker_pattern -> person` mapping only when all of the following are true in-scene:
- exactly one named `person` node is present
- exactly one anonymous speaker is present
- no competing named speaker identity is present
- the speaker's own aligned excerpt contains the person name
- the speaker is dominant in the scene

Current runtime dominance rule:
- `dominant_share >= 0.6`

The candidate must carry evidence, not just a label:
- `scene_id`
- `video_id`
- `speaker_label`
- `voice_similarity`
- `voiced_seconds`
- `segment_count`
- `dominant_share`
- `transcript_excerpt`

Face-based candidate edges may also exist, but they remain weak scene-local hints.

### 3. Candidate -> Supported

GoodQ may emit `identity_supported` only after repeated agreement across scenes and only when the source has no conflicting stronger mapping.

Current runtime thresholds:
- scene-local anonymous `speaker` / `face` sources: >= `2` scenes
- `speaker_pattern` sources: >= `3` scenes

The promoted edge must persist:
- `supporting_scene_count`
- `supporting_scene_ids`
- `supporting_video_count`
- `supporting_video_ids`
- `supporting_evidence`
- `candidate_source`
- `evidence_strength`

### 4. Supported -> Evidence

GoodQ may emit `identity_evidence` only for `speaker_pattern -> person` mappings after multi-episode agreement.

Current runtime thresholds:
- >= `5` supporting scenes
- >= `2` supporting episodes
- no conflicting `identity_supported` or `identity_evidence` edge from the same structural source to a different person

This is the first stage that should be treated as durable cross-episode identity evidence, but it is still additive rather than merge-destructive.

---

## Evidence Rules

### Allowed evidence

The stitching layer may rely on:
- aligned speaker transcript excerpts
- repeated person-name alignment
- voice-pattern similarity
- voiced duration and segment diversity
- dominance within a scene
- repeated support across scenes and episodes

### Disallowed evidence

The stitching layer must not promote identity from:
- mere co-presence in a scene
- one-off mentions
- anonymous speaker labels alone
- anonymous face labels alone
- a single strong scene without repetition

### Ledger requirement

Every `identity_supported` and `identity_evidence` edge must be explainable through a scene-level evidence chain. The ledger projection may summarize this chain, but it must not invent missing evidence.

---

## Non-Action Rules

The stitching layer must not act when evidence shape is insufficient.

### No action from one scene alone

One scene may produce:
- `voice_pattern_match`
- `identity_candidate`

One scene must not produce:
- `identity_supported`
- `identity_evidence`

### No action from co-presence alone

If a person is merely present in the scene, but the speaker-aligned excerpt does not support that person name, no speaker identity candidate may be emitted.

### No action under ambiguity

If multiple named people are present and the system cannot isolate the speaking person, it must preserve structural nodes only.

### No action under conflict

If a structural source already has `identity_supported` or `identity_evidence` to a different person, new promotion must stop until contradiction is resolved.

### No action from weak audio shape

If speech is too short or not diverse enough to create a stable signature, the system must emit no speaker-pattern claim.

### No destructive merge

This contract does not authorize:
- replacing anonymous nodes with person nodes
- deleting candidate edges
- collapsing structural nodes into people

Uncertainty must remain visible.

---

## Success Condition

The stitching layer is behaving correctly when:
- `speaker_pattern` and `voice_pattern_match` accumulate before person claims do
- `identity_candidate` appears only in narrow, explainable cases
- `identity_supported` and `identity_evidence` remain zero when evidence is thin
- every promoted mapping can answer "why?" with scene-level support

Zero promotions is a valid outcome.

---

## Runtime Sources

Current runtime implementation lives in:
- `wsl2_audio/process_audio.py`
- `lib/kg_realtime_integration.py`
- `lib/identity_ledger.py`

This document describes the current contract those runtime surfaces are expected to preserve.
