# Legacy Test Archive

**Purpose:** Historical test and validation harnesses  
**Status:** Archived, non-canonical  
**Last Verified:** 2026-03-20

This directory preserves one-off build verifiers, manual probes, and path-specific harnesses that are no longer part of the maintained test contract.

## Current Layout

- `tests/legacy/root_harnesses/` - old root-level `test_*.py` and ad hoc pipeline checks
- `tests/legacy/integration_harnesses/` - historical ingestion, scene, and embedding probes
- `tests/legacy/utilities/` - one-off validation helpers and environment checks
- existing top-level legacy files - earlier archived diagnostics

## Canonical Test Contract

Do not use this directory as the default validation surface.

Use:

- `pytest.ini`
- `tests/unit`
- `tests/integration/test_watchdog.py` for the maintained manual watchdog check

## Why These Were Archived

- They are not collected by the default `pytest` configuration.
- Many rely on historical path assumptions or workstation-specific fixtures.
- Several were created to validate intermediate implementation phases rather than the current release surface.
