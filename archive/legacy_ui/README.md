# Legacy UI Archive

This directory contains historical UI and UI-adjacent artifacts that were **archived** during the Justification Channel clean-slate reset.

## Why archived

These artifacts were removed from active paths because they are:
- incompatible with `EpistemicReadEnvelope` and `NonActionDecision` as authoritative UI primitives
- not Conduit Pack v1 compliant (they assume direct/raw sources, including transcripts/logs/paths)
- action-leaking (UI-triggerable ingestion/agent/control endpoints)
- drift-prone (hardcoded ports/endpoints and multiple competing UI roots)

## What is here

- `ui_scaffold/` — the old `ui/` HTML+JS scaffold (port drift; not contract-based)
- `web/` — legacy dashboard/scenes HTML pages
- `api/` — legacy UI-adjacent API entrypoints (kept for reference only)
- `tests/` — HTML UI test artifacts (manual/debug)

## Important

Do not revive these as the supported UI surface.  
Justification Channel v1 is the only supported UI direction and must render:
- `EpistemicReadEnvelope`
- `NonActionDecision`
and read only from `_public` conduits (no raw logs/transcripts/paths).

