<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_AGENT_WORKFLOW -->
<!-- DOC_LAST_VERIFIED: 2026-09-07 -->

# Local Dev Runtime Modes

Use this runbook to switch the desktop between GoodQ development work and a
low-GPU-overhead desktop session. It owns the paired `dev_on.bat` and
`dev_off.bat` behavior; it does not authorize ingestion, collection cleanup,
model downloads, or configuration rewrites.

The user's workstation target includes GoodQ, Hermes, both intentional Ollama
lanes, and the supporting compute services. Dev Off should drain their work and
release development/AI allocations for gaming or other GPU work. That complete
target is not yet qualified. R-19 in the sole roadmap owns the remaining gates.
The caller changes below are isolated repair source; live shortcuts and core
environment selection remain unchanged.

## Dev On

Run `dev_on.bat`; it binds its working directory to its own checkout.

It performs these actions in order:

1. Requires `GOODQ_WSL_DISTRO` from the process environment or the checkout's
   environment file. It must not select an unrelated distro by discovery order.
2. Uses `start_goodq_dev.ps1 -CheckStart` to reject existing owners before
   compute startup, and validates config using the same core interpreter binding.
3. Synchronizes only the three versioned WSL audio worker files when their
   deployed hashes differ, then fails closed unless every deployed hash matches.
4. Starts the canonical vLLM controls, waits up to 90 seconds for its advertised
   loopback models endpoint to respond, and confirms loopback Qdrant is reachable.
5. Runs the existing `start_goodq_dev.ps1 -Supervise` owner in the foreground.
   That owner starts the API before Watchdog, binds exact process/job identities,
   and owns readiness, restart/backoff, and drain receipts. There are no separate
   shell-wrapped API/Watchdog launches or termination by port/name.
6. Enables `GOODQ_PREWARM_RETRIEVAL_MODELS=1` for that supervised invocation. The
   API and any replacement API use the same optional encoder pre-warm policy.
7. Preserves a failed supervisor result as a nonzero caller result. Normal return
   means the supervised runtime has stopped; it is not a new readiness claim.

The pre-warm is fail-soft: an unavailable optional encoder is logged and does
not prevent the API from starting. It uses pinned local model caches only.

The WSL worker gate is not a general deployment or model installation step. It
owns only `setup_cuda_env.sh`, `process_audio.py`, and `model_cache.py`; matching
files are not rewritten. This prevents a strict audio run from accepting an
importable but stale worker deployment.

### Operator Receipt

Dev On displays its prerequisite checks, then the canonical supervisor's output.
Keep that supervisor window open and use Dev Off for an orderly stop. Per-attempt
logs and receipts are under the printed `%TEMP%/goodq-startup-<invocation>` path.
Process liveness, HTTP response, model readiness, and successful scene work are
separate observations. A blocked node or nonzero owner result remains a failure.

Only the owning component's dated receipt establishes its outcome. Console color
or an old startup message cannot establish current whole-workstation readiness.

## Dev Off

Run `dev_off.bat`; it binds its working directory to its own checkout.

It first calls `start_goodq_dev.ps1 -StopCurrent`. The owner is discovered from
existing invocation receipts and live Windows job membership, not the newest
file's timestamp. Explicit stop validation still checks repository, protocol,
PID, creation time and event/job binding. The caller waits for `stopped` with
`drain_verified=true`, empty role jobs, and absence of remaining GoodQ owners.
An already absent runtime needs no stop. Ambiguity, unknown owners, failed
supervision or timeout preserve dependencies and return failure.

A supervisor that is starting its first child or waiting to restart both roles
still owns future work. Its existing PID/birth receipt blocks both Dev Off
release and competing Dev On startup during that gap; no child is not proof of
an absent stack. Retry after recovery or inspect the owner's terminal receipt.

Only after that gate may the existing vLLM stop control run and the explicitly
configured GoodQ distro be terminated. Other WSL distros are separate owners;
the caller no longer invokes a global WSL shutdown. No model files, indexes,
or canonical data are deleted.

The vLLM batch entrypoint delegates to `scripts/stop_vllm_servers.ps1`. It checks
the systemd stop result and service state, Linux processes/listeners, actual
Windows connection refusal, and both Linux/Windows keepalive absence. A timeout
or HTTP error is not endpoint-absence evidence. It signals only the exact
configured-distro sleep anchor; it does not force-kill manual model processes or
other distros' Windows clients. A stopped distro is not booted just to stop it.
This establishes release of these resources, not completion of model requests.

Qdrant intentionally remains running on loopback. It uses no GPU and avoids a
database-service restart when returning to development. It is not a remote
access surface by virtue of remaining local.

Dev Off reports the GoodQ boundaries and explicitly leaves whole-workstation
release unverified. The retained ambient-host Ollama unload is not proof for
both lanes, and Hermes producers are not yet part of this caller's drain. These
limitations must close before a full gaming-mode claim or live consolidation.
The user's full Dev Off scope includes NOMAD as well as Hermes and both Ollama
lanes. Their producer/database drain and startup owners remain the next gate.
The current exit code covers this bounded GoodQ workflow. Qdrant health and the
informational `nvidia-smi` snapshot do not establish global release.

Do not use a global GPU reset or kill unrelated desktop processes to reclaim
display-managed VRAM. Those operations can disrupt the active desktop and are
not required to release GoodQ compute memory.

## Model Identity Check

Hermes and the vLLM speed fallback are separate local services. Before changing
a configured model ID, compare the configured value with the live server's
`/v1/models` response and make one tiny completion against the advertised ID.

The current speed fallback is named `Qwen-0.5B-Speed`. Its portable client ID
is `goodq-qwen-speed`, controlled by `GOODQ_VLLM_SERVED_MODEL_NAME`. The WSL
installer alone resolves `GOODQ_WSL_MODEL_PATH`; that physical path is not a
client contract. A reachable endpoint alone is not sufficient: a stale model ID
causes completion requests to fail even when `/v1/models` succeeds.

## Minimal Verification

After Dev On, verify the API root, Qdrant collection endpoint, and each model
service's `/v1/models` endpoint. Then perform one bounded local retrieval or
one tiny model completion when the affected path changed.

After Dev Off, verify the owner-bound drain receipt, absence of GoodQ owners,
and actual compute release. An HTTP exception alone is not proof that a model
server stopped. Qdrant remaining reachable is expected. GPU tools may still
report desktop graphics allocation; distinguish it from AI compute ownership.

The bounded regression gate executes the batch control flow against isolated
external command boundaries and the real supervisor against owned Windows
processes. It covers refusal before dependency actions, active-work drain,
timeout preservation, stale receipts, unowned listeners, and explicit distro
binding. These tests do not start live models, qualify Hermes stop/escalation,
prove simultaneous mode transitions, or select the candidate environment.

## Recovery Rules

- Treat a strict configuration failure as a stop condition; fix the resolved
  local overlay or canonical config before retrying Dev On.
- Treat a reachable model endpoint with a rejected configured ID as model
  identity drift. Update only the stale reference after the advertised ID
  passes a tiny completion.
- Treat unexpected Qdrant exposure beyond loopback as a network-boundary issue,
  not a Dev On/Dev Off optimization.
- Keep model/runtime changes separate from ingestion and epoch work.
