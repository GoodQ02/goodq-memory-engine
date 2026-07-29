<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-29 -->

# R22 Hermes Routing Port — 2026-07-29

## Objective

Port only the verified Hermes routing contract from the historical R22 branch
into current private development, without carrying its superseded identity
history.

## Contract

- Preserve configured Ollama endpoints; endpoint selection never probes and
  silently redirects to a different local port.
- Select the configured Hermes chat model for `GPU_ENHANCED`.
- Apply model request defaults per attempt, with explicit caller options taking
  precedence and no option leakage across failover.
- Do not send local Ollama tags to Hugging Face bootstrap.

## Verification

| Gate | Result |
|---|---|
| Hermes contract tests | 30 passed, 2 existing Pydantic warnings |
| Combined LLM, model, runtime, configuration, and temporal guard suite | 164 passed, 4 existing Pydantic warnings |
| Local model inventory | The configured Hermes model is present at the configured local endpoint. |
| Native one-token witness | Completed with visible output in approximately 0.65 seconds. |
| Client witness, realistic budget | Selected `hermes-gemma4-64k:12b` and returned visible output through the OpenAI-compatible client path. |
| Post-merge guard | 164 passed after making the portable-baseline test explicitly set `GOODQ_HOST_PROFILE=UNSET`; `.env.local` otherwise restores the workstation profile by design. |

## Quality Boundary

An eight-token OpenAI-compatible request may finish with no visible content for
this reasoning-capable model. That is an insufficient output budget, not a
service failure: the same model completes natively and through the product
client when given a realistic response budget. The port does not change caller
token budgets.

## Scope Exclusions

- No API restart, runtime configuration write, corpus change, or model download.
- No historical R-08 identity commits were merged.
- No claim is made about arbitrary prompt quality beyond the bounded local
  completion witness.

## Integration Governance Note

The remote accepted this verified integration but reported that `dev` is
intended to remain linear. The resulting shared history is preserved; no
history rewrite is authorized by this checkpoint. Future bounded ports must use
the linear integration path documented in the agent workflow.
