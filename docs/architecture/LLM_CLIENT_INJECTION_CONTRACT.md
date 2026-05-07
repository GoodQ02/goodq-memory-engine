<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

# LLM Client Injection Contract

Status: binding for runtime modules.

Purpose: keep `lib/llm_client.py` as a pure execution layer while preserving
config authority at runtime entry points.

Rules:
- `lib/llm_client.py` must not read or parse config files.
- Runtime entry points load config once and inject all LLM settings.
- Non-entry modules accept an injected `LLMClient` (or explicit model configs).
- Endpoints, ports, timeouts, and retries are explicit inputs, not defaults.
- This contract is about configuration authority only; behavior is unchanged.

References:
- `docs/architecture/CONFIG_LOADING_CONTRACT.md`
- `docs/architecture/NON_ACTION_CONTRACT.md`
