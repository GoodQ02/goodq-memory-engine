# GoodQ Inspector v0 (Observer‑Only)

GoodQ Inspector v0 is a passive, observer-only diagnostics recorder for the Justification Channel UI.

## What it is

- Records **structured** observations about UI health over time.
- Intended to help diagnose regressions and wiring mistakes by inspection.
- **Never** suggests fixes, never mutates UI state, never performs actions.

## What it records (strictly)

Each JSONL entry may include:
- `ts_utc` (event timestamp)
- `ui_version`
- `event_type`: `initial_render` | `state_transition` | `diagnostics_update`
- `source` (function name)
- counts: candidates / evidence hits / non-action decisions
- diagnostics: `order_fingerprint`, warning **codes only**
- `last_render_ts_utc`

## What it explicitly does NOT record

- Envelope question text or any evidence text
- Evidence payloads / provenance payloads
- File paths (absolute or vault)
- Transcripts
- Raw confidence values

## Storage model

- Append-only **JSONL** file: `inspector_log.jsonl`
- Bounded to the last **500** entries (oldest dropped safely)
- No external storage, no network calls

Note: Browsers do not have direct filesystem write access; file logging is best-effort and will only occur in environments that provide local file write capability (e.g., Node/Electron-like contexts). In all environments, Inspector remains observer-only.

## Enable / disable

Inspector logging is **disabled by default**.

Enable by setting:
- `window.GOODQ_INSPECTOR_ENABLED = true`

Disable by setting:
- `window.GOODQ_INSPECTOR_ENABLED = false`

## Manual inspection

Open `inspector_log.jsonl` in a text editor and search by:
- `event_type`
- `order_fingerprint`
- warning codes

