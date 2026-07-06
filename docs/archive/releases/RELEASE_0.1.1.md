<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-17 -->

# GoodQ4All 0.1.1 Release Checkpoint

This document records the 0.1.1 release checkpoint for the current GoodQ4All
runtime surface.

## Scope

Release `0.1.1` is a pre-1.0 patch release focused on:

- witness-proven scene-context interpretation quality
- additive Phase 6 read-model hardening
- explicit three-tier scene memory contracts
- audit-driven beat coverage against curated episode anchors
- preserving backward compatibility while improving retrieval truth

## What This Release Represents

- `scene_context_llm` now carries an explicit three-tier tag model:
  `primary_tags`, `contextual_tags`, and `structural_tags`.
- `scene_context_arbitration` is now a canonical additive read model in Phase 6
  outputs and projected witness results.
- Transcript-rich scenes no longer flatten critical episode beats into weak
  setting labels when the transcript clearly supports a stronger scene truth.
- Low-signal scenes preserve explicit empty tier arrays instead of `null`,
  tightening the canonical scene-context contract.
- The harmonizer now tolerates malformed legacy tier payloads defensively,
  without weakening the canonical explicit-array write shape.

## Proving Witness

Release `0.1.1` is anchored to the proving witness:

- `reports/fresh_ingest_runs/20260417_163530_season3_feature_ladder/`

Key outcomes:

- `03x10` passed with full Phase 6 completion.
- `03x11` passed with full Phase 6 completion.
- `generic_context_detected = false` on both episodes.
- Phase 6b harmonization completed cleanly on both episodes.

Representative repaired scenes:

- `03x10/24` -> `Kitchen conversation about Steve.`
- `03x10/26` -> `Conversation about Steve Pocatillo.`
- `03x11/5` -> `Kitchen conversation about alternate side.`
- `03x11/23` -> `Living room conversation about rental car.`

## Evaluation Anchors

Release `0.1.1` also formalizes the local episode-reference eval lane:

- `scripts/diagnostics/episode_reference_eval.py`
- `reports/reference_anchors/seinfeld/episodes/`

These curated IMDb-backed anchors are used only for audit and witness scoring.
They do not override runtime scene truth.

On the proving witness, the local eval improved to:

- `6/6` core beats covered
- `9.0/9.0` salience weight hit

This is an improvement over the prior `5/6` and `8.25/9.0` baseline.

## Supported Entry Surface

- Install: `docs/guides/install/INSTALL.md`
- Quickstart: `docs/guides/install/QUICKSTART.md`
- Launch: `docs/guides/general/LAUNCH_INSTRUCTIONS.md`
- API: `docs/reference/API.md`
- Shipping profile: `docs/releases/SHIP_PROFILE.md`

## Truth Boundary

Release `0.1.1` does **not** claim:

- that all contextual memory choices are final
- that public episode anchors may overwrite runtime scene evidence
- that every low-value contextual cue has been removed
- that the system has reached a post-1.0 compatibility freeze

It does claim that the supported interpretation surface is now materially more
accurate, auditable, and contract-consistent while preserving the existing
runtime boundaries.
