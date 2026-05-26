<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: REFERENCE_ONLY -->
<!-- DOC_CANONICAL_POINTER: docs/architecture/SYSTEM_MAP_v1.md -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

# Narrative Layer (Read-Only)

Status: descriptive, non-authoritative

## Purpose

The narrative layer renders a human-readable description of a single run based
only on existing observability artifacts. It is a presentation layer, not an
execution layer.

## Boundaries

- Narrative output does not alter logs, execution, or control flow.
- Narrative output is not a substitute for raw logs or run artifacts.
- Narrative output must remain read-only and non-authoritative.

## Determinism Requirement

Given the same run_summary input, narrative output must be stable in:

- sentence ordering
- field naming
- wording and tense

No inference or enrichment is permitted beyond the summary fields.

## Evidence Lineage

Narratives must be derived solely from:

- run_summary fields
- run_summary.evidence entries

If data is missing, the narrative must state "unknown" or "not observed."

## Exposure Rules (Future)

Any CLI or API exposure of narrative output must preserve:

- stdout-only narrative text
- stderr-only errors
- no writes or side effects
