<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_OPERATOR_REFERENCE -->
<!-- DOC_LAST_VERIFIED: 2026-09-23 -->

# Ollama Port Boundaries

> **Status**: Active operator reference  
> **Applies to**: GoodQ installs and optional operator inference lanes
> **Last verified**: source behavior at the public update

## Port Assignments

### 11434 — GoodQ / Default Lane

- Ollama ecosystem default port.
- GoodQ product default for all installer tiers (Baseline, CPU-Only, GPU-Enhanced).
- Public installer and new-user expectation.
- Embedding models (embeddinggemma, qwen3-embedding, llama3.2) typically run here.
- GoodQ `configs/config.yaml` points here by default.

### 31434 — Hermes / Operator Lane

- Reserved for the Hermes agent runtime on GOOD-CUBE.
- Runs operator-grade reasoning models (hermes-gemma4-64k:12b, gemma4:12b, phi4).
- Configured via `%SystemDrive%\Tools\hermes-runtime\config.yaml`.
- If used, bind this lane only in its launcher process; do not set a persistent
  User-level `OLLAMA_HOST` that changes unrelated GoodQ launches.
- **Never** the public installer default.
- **Never** silently written or required by the GoodQ installer.
- Allowed in GoodQ only through an explicitly configured operator model or override.

## GoodQ Ollama Endpoint Precedence

For `lib/llm_client.py` model endpoints, the precedence is:

1. **`GOODQ_OLLAMA_URL`** — explicit GoodQ-specific full-URL override.
2. **`OLLAMA_HOST`** — process-level host-and-port override, if present.
3. **The model's configured base URL and port.** The default configuration
   points to `http://127.0.0.1:11434/v1`.

Endpoint selection does not probe or silently switch between 11434 and 31434.
Reachability is checked separately. An operator model may explicitly use 31434.

## Environment Variables

### `GOODQ_OLLAMA_URL`

- GoodQ-specific override for the Ollama API endpoint.
- Preferred over `OLLAMA_HOST` for controlling GoodQ behavior.
- Example: `GOODQ_OLLAMA_URL=http://127.0.0.1:11434/v1`

### `OLLAMA_HOST`

- Process/service-level Ollama bind address override.
- Controls which address and port Ollama listens on.
- Avoid setting this persistently for all applications. A process-level value
  overrides the model's configured GoodQ endpoint.

## Rules

- Do not set `OLLAMA_HOST=127.0.0.1:31434` as a normal install default.
- Do not force new users onto 31434.
- Do not bind Ollama to `0.0.0.0` by default.
- GoodQ installer must not write or require `OLLAMA_HOST`.
- The 31434 Ollama instance is Hermes's responsibility, not GoodQ's.
- GoodQ may use 31434 only through an explicitly configured operator model or override.

## Downstream Installs

On machines without an operator inference lane:

- Only port 11434 is expected.
- `OLLAMA_HOST` should be unset (Ollama uses its built-in default of 11434).
- GoodQ does not require the 31434 operator lane.
- No action required from the user.
