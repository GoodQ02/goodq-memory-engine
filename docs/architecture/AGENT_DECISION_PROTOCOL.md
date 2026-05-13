<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-17 -->

# Agent Decision Protocol

This document captures the repair behavior that has proven effective for
GoodQ4All pipeline work. It is intentionally narrow: correctness, traceability,
and witness quality matter more than speed or cleanup.

## Purpose

Use this protocol when:

- repairing pipeline seams
- correcting scene truth drift
- hardening Phase 6 contracts
- iterating on witness quality
- evaluating whether a runtime change is ready to widen from scene-first checks

This protocol is not a replacement for runtime contracts. It governs how agents
change the system without destabilizing it.

## Core Repair Loop

Follow this exact loop:

1. Identify a single concrete seam.
2. Trace the seam to a specific code path or contract violation.
3. Propose the smallest possible fix.
4. Implement only that fix.
5. Validate locally on targeted scenes or focused contract tests.
6. Only then expand to an untouched full-episode witness.

If the seam survives, repeat the loop. Do not widen scope mid-pass.

## Negative Constraints

Do not:

- fix multiple issues in one pass
- refactor unrelated code during seam repair
- perform cleanup on adjacent systems "while there"
- rerun a full witness before scene-first validation
- change persistence shapes casually
- bypass Phase 6 validation
- use public references as runtime truth overrides

## Scene-First Invariant

All repair work must preserve the scene-first invariant:

- scenes remain the atomic unit of ingest
- scene-first debug comes before full-episode reruns
- per-scene artifacts remain attributable to one scene boundary
- persistence contracts are not altered unless the seam requires it

When a seam is ambiguous, prefer one scene-level debug pass over a wider rerun.

## Contract-Preserving Principle

Agent changes must preserve existing contracts whenever possible.

That means:

- additive keys are preferred over replacement keys
- compatibility surfaces should remain available during transition
- Phase 6 and persistence boundaries should not be widened casually
- eval layers may score runtime output, but they do not redefine runtime truth

## Eval Anchor Rule

External references such as curated IMDb-backed episode anchors are allowed only
as audit and scoring inputs.

They may:

- check beat coverage
- measure salience alignment
- expose hallucination or flattening seams

They may not:

- overwrite runtime scene truth
- inject web-derived facts into canonical scene memory
- outrank local transcript, audio, or visual evidence at runtime

## Safe Parallelism

Parallel work is encouraged only when it does not interfere with the active
runtime lane.

Safe examples:

- code-path audit in a parallel agent
- transcript and anchor analysis in a parallel agent
- docs and status updates while a witness is live

Unsafe examples:

- editing runtime code while the active witness may still import it
- altering persistence or config contracts during a live witness
- mixing multiple runtime fixes before identifying a single seam

## Proven Effective Pattern (Witness 2026-04-16 / 2026-04-17)

The recent repair cycle succeeded because:

- scope stayed restricted to one seam at a time
- patches stayed small and explicit
- validation was scene-first before full reruns
- unrelated systems were left alone
- eval work ran in parallel without interfering with the witness
- public reference anchors were used to judge salience, not to override truth

This pattern should be reused for future pipeline fixes.

## Decision Order

When choosing the next action, prefer this order:

1. inspect the current witness or canonical artifact
2. isolate one seam
3. inspect the exact code path
4. patch minimally
5. validate locally
6. rerun the smallest witness that can prove the change
7. only then widen to a larger witness

## Relationship to Other Contracts

This protocol works with, and does not replace:

- `docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md`
- `docs/SCENE_MANIFEST_SPECIFICATION.md`
- `docs/PHASE6_MULTIMODAL_FUSION.md`
- `docs/architecture/IDENTITY_STITCHING_CONTRACT.md`

If this protocol and a runtime contract appear to disagree, the runtime
contract wins and the repair loop must adapt.
