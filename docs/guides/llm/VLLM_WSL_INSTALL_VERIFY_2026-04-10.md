<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-10 -->

# WSL vLLM Install And Verify Procedure (This Machine)

This is the concrete operator runbook for bringing up the local LLM runtime on the current workstation.

It is intentionally:
- WSL-first
- local-only
- additive
- reversible
- aligned with the existing GoodQ config contract

It is **not** a generic design note. It reflects the machine state verified on 2026-04-10.

## Machine Snapshot

Verified facts for this workstation:
- WSL distro: `Ubuntu-22.04`
- WSL user: `jdben`
- WSL home: `/home/jdben`
- WSL Python: `3.10.12`
- GPU visible in WSL: `NVIDIA GeForce RTX 4070 Ti SUPER`
- GPU driver visible in WSL: `595.79`
- WSL systemd: enabled
- WSL networking: mirrored mode with host loopback enabled

Verified gaps:
- no `vllm-llama1b` systemd service installed
- no `ollama` service installed
- no LM Studio / Ollama runtime running on Windows
- no local text-LLM model staged yet
- `http://localhost:1234`, `:38005`, `:31434`, and `:11434` were all unavailable at verification time

## Prime Rules

1. Do not modify [`configs/config.yaml`](../../../configs/config.yaml).
2. Do not modify [`configs/open_config.yaml`](../../../configs/open_config.yaml).
3. Use `config.local.yaml` only for local runtime routing.
4. Stand up `vLLM` first.
5. Treat Ollama as a later fallback, not part of initial bring-up.
6. Do not use LM Studio for pipeline runtime.

## LLM Authority Contract

LLM outputs are:
- non-authoritative by default
- non-persistent unless explicitly promoted by a canonical, feature-gated path
- never allowed to mutate canonical truth surfaces directly

Operational meaning:
- an LLM may help interpret a scene
- it may not directly edit `scene_manifest.json`
- it may not directly edit `temporal_index.json`
- it may not directly write to the Knowledge Graph
- any persistence must happen through an explicit canonical promotion step that is additive, optional, and auditable

This is the rule that keeps interpretation from quietly becoming truth.

## Target Runtime Shape

The intended local runtime for this machine is:
- primary inference host: WSL `Ubuntu-22.04`
- primary server: `vLLM`
- primary port: `38005`
- API contract: OpenAI-compatible `/v1`
- primary consumer surfaces:
  - `llm.api_url`
  - `llm.vllm_url`
  - `llm.vllm_model`

Important integration note:
- many older LLM-adjacent steps use `llm.api_url` directly
- the general `LLMClient` also uses `llm.vllm_url` / `llm.vllm_model`
- for a clean implementation, both must point to the same running `vLLM` service

## Recommended Storage Decision

For this machine, prefer a WSL-local model path over a mounted Windows path.

Recommended model path:
- `/home/jdben/models/Llama-3.2-1B-Instruct`

Why:
- avoids mount latency and path translation issues
- fits the service installer defaults
- keeps the pipeline runtime fully WSL-local

Do not assume the model ID in config ahead of time.

After the service is up, query `/v1/models` and use the exact returned model ID in local override config.

## Phase 1: Preflight

Run from Windows PowerShell:

```powershell
wsl -d Ubuntu-22.04 -- bash -lc 'whoami; echo $HOME; python3 --version; systemctl is-system-running || true'
wsl -d Ubuntu-22.04 -- bash -lc 'nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader'
wsl -d Ubuntu-22.04 -- bash -lc 'test -d ~/vllm_server && echo VLLM_HOME_EXISTS || echo VLLM_HOME_MISSING'
wsl -d Ubuntu-22.04 -- bash -lc 'test -d ~/models/Llama-3.2-1B-Instruct && echo MODEL_EXISTS || echo MODEL_MISSING'
```

Expected current result on this machine:
- WSL healthy
- GPU visible
- `~/vllm_server` missing or incomplete
- model missing

## Phase 2: Create Dedicated vLLM Runtime

Run inside WSL:

```bash
mkdir -p ~/vllm_server
python3 -m venv ~/vllm_server/venv
source ~/vllm_server/venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install vllm
```

Verification:

```bash
~/vllm_server/venv/bin/python -c "import vllm; print('vllm ok')"
```

If this import fails, stop here and fix the WSL Python environment before continuing.

## Phase 3: Stage The Model

Create model directory root:

```bash
mkdir -p ~/models
```

Then place or download the model into:

```bash
/home/jdben/models/Llama-3.2-1B-Instruct
```

The exact download method can vary, but the success criterion is simple:

```bash
test -f ~/models/Llama-3.2-1B-Instruct/config.json && echo MODEL_READY
```

Do not proceed to service install until that file exists.

## Phase 4: Install The systemd Service

From Windows PowerShell, run this from the repo root:

```powershell
$repoWsl = wsl -d Ubuntu-22.04 -- wslpath .
wsl -d Ubuntu-22.04 -- bash -lc "cd '$repoWsl/scripts/wsl' && GOODQ_WSL_USER=jdben GOODQ_WSL_MODEL_PATH=/home/jdben/models/Llama-3.2-1B-Instruct ./install_vllm_service.sh"
```

On this machine, `sudo` is interactive, so expect a password prompt during:
- service file creation
- daemon reload
- enable/start operations

The installer should create:
- `/etc/systemd/system/vllm-llama1b.service`
- `~/vllm_server/logs/vllm-service.log`
- `~/vllm_server/logs/vllm-service-error.log`

## Phase 5: Verify The Service Directly

Inside WSL:

```bash
sudo systemctl status vllm-llama1b --no-pager
curl http://localhost:38005/v1/models
```

Required success condition:
- `systemctl` reports active
- `/v1/models` returns a JSON model list

Capture the exact returned model ID from `/v1/models`.

That returned value is the authoritative `llm.vllm_model` for this machine.

Also record:
- `llm_model_id_used`
- `timestamp_utc`
- `endpoint`

This should be stored with the run record whenever the endpoint is probed, so model drift is explainable later.

## Phase 6: Create Local Override Config

Create or update local-only config at the repo root:

```text
config.local.yaml
```

Recommended minimum override:

```yaml
host:
  wsl_distro: Ubuntu-22.04
  wsl_user: jdben
  wsl_workspace: /home/jdben/goodq_audio

llm:
  api_url: http://localhost:38005/v1/chat/completions
  vllm_url: http://localhost:38005/v1
  vllm_model: <exact model id returned by /v1/models>
  features:
    scene_context_analysis: false
```

Notes:
- keep `scene_context_analysis` off until endpoint sanity is proven
- do not assume the model ID string; copy the exact value returned by the running server
- this step is what aligns direct-step callers and the general LLM client to the same runtime

## Phase 7: Windows-Side Sanity Tests

Run from the repo root in PowerShell:

```powershell
scripts\test_vllm_from_windows.ps1
```

Then run the full client test through the canonical env:

```powershell
conda run -n goodq_core python scripts\test_llm_client.py
```

Required success conditions:
- `/v1/models` reachable from Windows
- at least one healthy model reported by `test_llm_client.py`
- simple chat completion works
- streaming works

## Phase 8: Pipeline-Specific Sanity

Before resuming Season 3 `03x03`, do one direct endpoint proof for the exact surface that was blocked:

```powershell
conda run -n goodq_core python -c "from steps.common.context_analyzer_llm import analyze_scene_context_llm; scene={'scene_index':0,'audio':{'transcript':'Jerry argues with George about a missing pen.','emotion':'frustrated'},'keyframe':{'caption':'Two men talking in an apartment kitchen','objects':[{'label':'person'},{'label':'table'}]}}; print(analyze_scene_context_llm(scene))"
```

This does not need to be perfect. It only needs to prove:
- `llm.api_url` is routed correctly
- the function returns structured output instead of transport failure

## Phase 9: Resume Treatment Ladder

Once the endpoint and direct function proof both pass:

```powershell
conda run -n goodq_core python scripts\season3_feature_ladder.py --start-at-prefix 03x03
```

Expected treatment target:
- `03x03` with `scene_context_llm`

## Optional Later Step: Non-Interactive Start Commands

The current Windows helper script assumes non-interactive sudo:
- [`scripts/start_vllm_servers.bat`](../../../scripts/start_vllm_servers.bat)

Do not change this during initial bring-up.

After the service is stable, consider a separate hardening pass to allow a limited non-interactive start/status path for:
- `vllm-llama1b`
- optional later `ollama`

That should be treated as a follow-up usability improvement, not part of initial install.

## Stop Conditions

Stop and investigate if any of these happen:
- `curl http://localhost:38005/v1/models` fails after the service is active
- the returned model ID does not match the configured `llm.vllm_model`
- `test_llm_client.py` shows zero healthy models
- direct `analyze_scene_context_llm(...)` call fails with connection errors
- `scene_context_llm` introduces identity leakage or generic filler once enabled

## Success Definition

This machine is considered ready for `scene_context_llm` when all of the following are true:
- WSL `vLLM` service is active on `38005`
- Windows can reach `/v1/models`
- local override config routes both `api_url` and `vllm_url` to the same runtime
- `test_llm_client.py` passes with at least one healthy model
- direct `analyze_scene_context_llm(...)` returns structured output
- Season 3 ladder can resume from `03x03`
