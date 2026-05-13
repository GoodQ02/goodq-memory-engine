# Vault Token Resolver Contract (v1)

**Status:** ✅ Contract (local-only; no ingestion)  
**Version:** 1

## Purpose

GoodQ uses opaque vault reference tokens (`vaultref:v1/...`) so that raw sensitive content (messages, health records, wearable media) can remain **vault-only** while the rest of the system operates on **derived** artifacts.

This contract defines a **local-only** interface for resolving:
- `content_ref` / `value_ref` / `media_ref` → **absolute local filesystem paths**

## Non‑Negotiable Rules

- Resolution is **local-only**:
  - Never exposed in UI responses, conduits, KG exports, or API payloads.
  - Only available in trusted local execution contexts (CLI, local services).
- Absence is not evidence:
  - A token may resolve to nothing (missing file, disabled vault, moved vault).
  - This must not be interpreted as “no such content existed”.
- Do not log sensitive paths:
  - Never emit resolved absolute paths into `retrieval_events`, public conduits, or user-facing logs.

## Token Grammar (v1)

All vault references are opaque strings with this prefix:

`vaultref:v1/<namespace>/<object_id_or_path>`

Where:
- `<namespace>` is one of: `messages`, `health`, `wearables`
- `<object_id_or_path>` is stable and deterministic (typically the canonical ID).

Examples:
- `vaultref:v1/messages/<message_id>`
- `vaultref:v1/health/<event_id>`
- `vaultref:v1/wearables/<capture_id>`

## Resolver Interface (Python Stub)

Reference implementation (structure only; no I/O side effects):
- `steps/common/vault_token_resolver.py`

Required behavior:
- Parse token → `{schema_version, namespace, object_id_or_path}`
- Given a `vault_root` (absolute), resolve token deterministically to an **absolute path**:
  - By default, return the *vault object root directory* (not necessarily a single file).
  - Return `None` if the token is invalid or the vault root is not configured.

### Vault Root Source (local-only)

The resolver may obtain `vault_root` from:
- `GOODQ_VAULT_ROOT` (environment variable), or
- an explicit argument passed by the caller.

The vault root must never be persisted into public conduits.

## Notes

- This contract does **not** define ingestion/parsing, only resolution of pointers.
- This contract intentionally avoids defining file extensions or raw export formats.

