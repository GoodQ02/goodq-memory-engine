# Ollama Port Boundaries

> **Status**: Active operator reference  
> **Applies to**: GOOD-CUBE (desktop), downstream installs  
> **Last verified**: v2.5.8-rc2 at 9510473e

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
- Bound by the User-level `OLLAMA_HOST=127.0.0.1:31434` environment variable.
- **Never** the public installer default.
- **Never** silently written or required by the GoodQ installer.
- Allowed in GoodQ only as an explicitly labeled legacy/operator fallback.

## GoodQ Ollama Endpoint Precedence

GoodQ resolves its Ollama endpoint in this order:

1. **`GOODQ_OLLAMA_URL`** — explicit GoodQ-specific override (env var or `.env.local`).
2. **`configs/config.yaml` → `ollama_url`** — per-deployment config override.
3. **`http://127.0.0.1:11434`** — ecosystem default.
4. **`http://127.0.0.1:31434`** — legacy/operator fallback only, with clear log warning.
5. **Unavailable** — neither port responds; pipeline logs a warning and disables LLM features.

If both 11434 and 31434 respond, GoodQ prefers 11434 unless explicitly configured otherwise.

## Environment Variables

### `GOODQ_OLLAMA_URL`

- GoodQ-specific override for the Ollama API endpoint.
- Preferred over `OLLAMA_HOST` for controlling GoodQ behavior.
- Example: `GOODQ_OLLAMA_URL=http://127.0.0.1:11434/v1`

### `OLLAMA_HOST`

- Process/service-level Ollama bind address override.
- Controls which address and port Ollama listens on.
- On GOOD-CUBE, this is currently set to `127.0.0.1:31434` at the User registry level to support Hermes.
- **Avoid relying on this globally for GoodQ.** GoodQ should use `GOODQ_OLLAMA_URL` or config-level overrides instead.
- Future improvement: scope `OLLAMA_HOST` to Hermes launch scripts only, removing it from the persistent User registry so new tools default to 11434.

## Rules

- Do not set `OLLAMA_HOST=127.0.0.1:31434` as a normal install default.
- Do not force new users onto 31434.
- Do not bind Ollama to `0.0.0.0` by default.
- GoodQ installer must not write or require `OLLAMA_HOST`.
- The 31434 Ollama instance is Hermes's responsibility, not GoodQ's.
- GoodQ may detect and use 31434 as a fallback, but must clearly label it as legacy/operator in logs and docs.

## Downstream Installs

On machines without Hermes (e.g., GOOD-SPEED-32, public users):

- Only port 11434 is expected.
- `OLLAMA_HOST` should be unset (Ollama uses its built-in default of 11434).
- GoodQ fallback to 31434 will simply find nothing and move on.
- No action required from the user.
