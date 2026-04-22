# Canonical Sensitive Events (High-Sensitivity Source Wiring Pack v1)

**Status:** ✅ Contract (schema-only, no ingestion)  
**Version:** 1

## Purpose

GoodQ must support high-sensitivity sources (chat logs, health exports, wearable streams) without accidental privacy leakage.

This contract defines:
- Canonical event schemas (structure only; raw content is vault-only).
- A local vault boundary layout (path conventions only; do not populate here).
- UI-safe reserved conduits that are allowed to be surfaced (derived, whitelisted fields only).

## Non‑Negotiable Safety Rules

- Raw content is **vault-only** by default:
  - No raw message text
  - No raw health measurements at individual-record granularity
  - No raw wearable audio/video frames
- Raw content must **not** appear in:
  - UI conduits
  - Knowledge graph tables
  - Embedding payloads / vector stores
- UI access must go through **derived conduits** only:
  - whitelisted fields only
  - token/path sanitized (no absolute filesystem paths)
  - pseudonymous participant identifiers by default
- Any “training export” (even derived) requires:
  - an explicit vault build manifest
  - explicit human approval

## Vault Boundary Layout (Path Conventions Only)

Recommended local vault layout (do not populate as part of this wiring pack):

```
vault/
  messages/
    raw/...
  health/
    raw/...
  wearables/
    raw/...
  index/...
  manifests/...
```

Rules:
- Vault paths **must never** appear in public conduits (including repo-relative or absolute paths).
- Public conduits may store **tokens only** (e.g., `content_ref`, `value_ref`, `media_ref`) which are resolved by a local-only vault resolver.

## Token Conventions (Vault Pointers)

Vault pointers are opaque, stable strings that reference vault content without exposing paths.

Recommended convention (v1):
- `content_ref`: `vaultref:v1/messages/<message_id>`
- `value_ref`: `vaultref:v1/health/<event_id>`
- `media_ref`: `vaultref:v1/wearables/<capture_id>`

Rules:
- Tokens must be deterministic and stable.
- Tokens must not embed absolute paths (Windows drive roots or `/mnt/...` paths).
- Tokens do not imply content exists; absence is not evidence.

## Canonical Event Schemas (v1)

### 1) CanonicalMessageEvent (CME)

Represents one message in a thread **without** raw message text.

Required fields:
- `schema_version`: `1`
- `message_id`: stable hash/UUID (content-independent if needed)
- `thread_id`: stable thread identifier
- `platform`: `imessage|sms|fb|ig|whatsapp|signal|telegram|other`
- `timestamp_utc`: ISO8601 UTC timestamp
- `direction`: `in|out`
- `participant_ids`: pseudonymous participant IDs (stable within platform scope)
- `content_ref`: vault pointer token (not text)

Optional derived fields (may be null/absent):
- `entity_ids`: list of linked entity IDs
- `sentiment_summary`: coarse label/summary (no raw text)
- `topic_tags`: topic/tag list

### 2) CanonicalHealthEvent (CHE)

Represents a health observation without exposing raw granular values by default.

Required fields:
- `schema_version`: `1`
- `event_id`: stable hash/UUID
- `source`: `apple_health|google_fit|garmin|oura|other`
- `timestamp_utc`: ISO8601 UTC timestamp (single instant)
- `category`: `sleep|activity|heart|nutrition|mood|other`
- `measurement_type`: e.g. `steps|hrv|resting_hr|sleep_duration|calories|other`
- `value_ref`: vault pointer token (not raw value)

Optional fields:
- `start_ts_utc`, `end_ts_utc`: ISO8601 UTC timestamps for interval events
- Derived (safe-to-surface):
  - `daily_aggregate_bucket`: coarse bucket (e.g., `low|normal|high`)
  - `trend_delta`: relative change marker (unitless / contextual)
  - `anomaly_flags`: list of non-identifying flags

### 3) CanonicalWearableEvent (CWE)

Represents wearable captures (e.g., Ray-Ban Meta) without raw media by default.

Required fields:
- `schema_version`: `1`
- `capture_id`: stable hash/UUID
- `device`: `rayban_meta|other`
- `timestamp_utc`: ISO8601 UTC timestamp
- `modality`: `image|video|audio|sensor`
- `media_ref`: vault pointer token (not a path)

Optional derived fields:
- `scene_id`: link to a GoodQ scene if aligned
- `entity_ids`: list of linked entity IDs
- `transcription_ref`: vault pointer token (not transcript text)
- `summary_ref`: vault pointer token (not full summary text)

## UI‑Safe Reserved Conduits

This wiring pack adds empty, UI-safe conduit tables (derived-only; whitelisted fields) in `memory.db`:

Messages:
- `thread_index_public`
- `message_activity_daily_public`
- `entity_thread_mentions_public`

Health:
- `health_activity_daily_public`
- `health_trends_public`
- `health_anomalies_public` (flags only)

Wearables:
- `wearable_capture_index_public`
- `wearable_timeline_public`
- `wearable_entity_mentions_public`

These conduits may store stable tokens and pseudonymous IDs, but must not store raw content.

## Vault Token Resolution (Local‑Only)

Vault tokens are resolved to local absolute paths **only** in trusted local contexts.

- Contract: `docs/architecture/VAULT_TOKEN_RESOLVER_CONTRACT.md`
- Reference hook (structure only): `steps/common/vault_token_resolver.py`

## Sensitive Ingest Staging (Contract)

Sensitive sources must be staged out of the vault before ingestion:

- **Must:** stage from `vault/…` into `cfg['paths']['processing']` (workspace processing area).
- **Must not:** run ingestion steps directly on vault paths.
- **Must not:** write sidecar files into the vault (some steps write adjacent artifacts next to the input path).
- Optional validator hook (no staging implementation): `steps/common/sensitive_staging.py`

## Derived‑Only Output Enforcement (Contract)

Allowed derived outputs (safe by default):
- Embeddings/vectors (no raw text/frames embedded in payloads)
- Tags, entities, and KG references (non-identifying by default)
- Aggregates and rollups (daily buckets, counts, trend markers)
- Vault pointer tokens (`content_ref` / `value_ref` / `media_ref`) only

Forbidden outputs (must remain vault-only by default):
- Raw message text
- Raw health measurements at individual-record granularity
- Raw transcripts (including full diarized text) and raw OCR text
- Raw wearable audio/video frames or images
- Absolute filesystem paths (including vault paths and Windows/WSL roots)

### CME → Allowed Memory / KG Fields

- Allowed: `message_id`, `thread_id`, `platform`, `timestamp_utc`, `direction`, `participant_ids`, `content_ref`
- Allowed (derived): `entity_ids`, `sentiment_summary`, `topic_tags`
- Forbidden: raw text in any DB/conduit payload

### CHE → Allowed Memory / KG Fields

- Allowed: `event_id`, `source`, `timestamp_utc`, `category`, `measurement_type`, `value_ref`
- Allowed (derived): `daily_aggregate_bucket`, `trend_delta`, `anomaly_flags`, (`start_ts_utc`/`end_ts_utc` when interval-based)
- Forbidden: raw per-record measurement values in any DB/conduit payload

### CWE → Allowed Memory / KG Fields

- Allowed: `capture_id`, `device`, `timestamp_utc`, `modality`, `media_ref`
- Allowed (derived): `scene_id`, `entity_ids`, `transcription_ref`, `summary_ref`
- Forbidden: raw media frames/audio and raw transcript/summary text in any DB/conduit payload

## Basement Phase Summary (v1)

- Schema contracts for CME/CHE/CWE are defined (structure-only; no ingestion).
- UI-safe reserved conduits for messages/health/wearables exist in `memory.db` (empty by default).
- Health Auto Export has a schema-first adapter (`steps/health_auto_export/adapter.py`) that supports dry-run parsing only; ingestion remains explicitly opt-in.
