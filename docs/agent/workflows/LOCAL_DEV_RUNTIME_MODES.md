<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_AGENT_WORKFLOW -->
<!-- DOC_LAST_VERIFIED: 2026-08-01 -->

# Local Dev Runtime Modes

Use this runbook to switch the desktop between GoodQ development work and a
low-GPU-overhead desktop session. It owns the paired `dev_on.bat` and
`dev_off.bat` behavior; it does not authorize ingestion, collection cleanup,
model downloads, or configuration rewrites.

## Dev On

Run `dev_on.bat` from the repository root.

It performs these actions in order:

1. Strictly validates the resolved GoodQ configuration.
2. Starts the canonical vLLM controls and confirms loopback Qdrant is reachable.
3. Replaces stale GoodQ API and watchdog processes, then starts fresh instances.
4. Sets `GOODQ_PREWARM_RETRIEVAL_MODELS=1` only for the new API process.
5. The API preloads the local text, CLIP, and CLAP query encoders once, so the
   first interactive retrieval does not pay model-load latency.

The pre-warm is fail-soft: an unavailable optional encoder is logged and does
not prevent the API from starting. It uses pinned local model caches only.

## Dev Off

Run `dev_off.bat` from the repository root.

It stops the GPU-backed vLLM service, shuts down WSL, and stops the GoodQ API
and watchdog. That terminates the owning processes, which releases their CUDA
allocator caches and VRAM without deleting model files, indexes, or data.

Qdrant intentionally remains running on loopback. It uses no GPU and avoids a
database-service restart when returning to development. It is not a remote
access surface by virtue of remaining local.

Do not use a global GPU reset or kill unrelated desktop processes to reclaim
display-managed VRAM. Those operations can disrupt the active desktop and are
not required to release GoodQ compute memory.

## Model Identity Check

Hermes and the vLLM speed fallback are separate local services. Before changing
a configured model ID, compare the configured value with the live server's
`/v1/models` response and make one tiny completion against the advertised ID.

The current speed fallback is named `Qwen-0.5B-Speed`. Its value is controlled
by `GOODQ_WSL_MODEL_PATH` when supplied; otherwise the configured Qwen local
path is used. A reachable endpoint alone is not sufficient: a stale model ID
causes completion requests to fail even when `/v1/models` succeeds.

## Minimal Verification

After Dev On, verify the API root, Qdrant collection endpoint, and each model
service's `/v1/models` endpoint. Then perform one bounded local retrieval or
one tiny model completion when the affected path changed.

After Dev Off, verify that the API and vLLM endpoints are unavailable. Qdrant
remaining reachable is expected. GPU tools may still report desktop graphics
allocation; distinguish it from GoodQ compute processes before taking action.

## Recovery Rules

- Treat a strict configuration failure as a stop condition; fix the resolved
  local overlay or canonical config before retrying Dev On.
- Treat a reachable model endpoint with a rejected configured ID as model
  identity drift. Update only the stale reference after the advertised ID
  passes a tiny completion.
- Treat unexpected Qdrant exposure beyond loopback as a network-boundary issue,
  not a Dev On/Dev Off optimization.
- Keep model/runtime changes separate from ingestion and epoch work.
