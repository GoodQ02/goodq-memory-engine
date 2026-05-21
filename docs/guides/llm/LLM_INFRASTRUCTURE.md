<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_GUIDE -->
<!-- DOC_LAST_VERIFIED: 2026-05-21 -->

# GoodQ4All LLM Infrastructure

## Current Supported Contract

The supported local LLM surface is a **config-driven two-endpoint contract**:

- **Primary**: `llm.vllm_url`
  - Default: `http://localhost:38005/v1`
  - Model id from `llm.vllm_model`
- **Fallback**: `llm.ollama_url`
  - Default: `http://localhost:31434/v1`
  - Model id from `llm.ollama_model`

These endpoints are turned into the live `LLMClient` model list by:
- `steps/common/llm_model_factory.py`

This is the contract used by current injected client flows such as:
- `api/main.py`
- `agents/control_agent.py`
- `agents/config_healer.py`

## What This Guide Does Not Assume

This guide does **not** assume the older multi-model WSL stack is active.

Ports and scripts such as:
- `38004`
- `38001`
- `~/vllm_server/scripts/start_llama1b.sh`
- `~/vllm_server/scripts/start_llama3b.sh`

belong to an older experimental/operator surface. They may still exist, but they are not part of the current supported `llm_client.py` contract.

Those older direct-start scripts have now been retired from the tracked surface.

## Architecture

```text
┌───────────────────────────────────────────────────────┐
│                GoodQ4All Application                  │
│  api/main.py · ControlAgent · ConfigHealer · others  │
└──────────────────────────┬────────────────────────────┘
                           │
                           ▼
                 lib/llm_client.LLMClient
                           │
           ┌───────────────┴───────────────┐
           ▼                               ▼
   Primary vLLM endpoint            Fallback Ollama endpoint
   llm.vllm_url                     llm.ollama_url
   default :38005                  default :31434
```

## Supported Start Paths

### Preferred vLLM Path

Use the WSL systemd installer:

```bash
wsl -d <GOODQ_WSL_DISTRO> -- bash /mnt/<drive>/<repo_root>/scripts/wsl/install_vllm_service.sh
```

After installation, the supported service is:

```bash
sudo systemctl status vllm-llama1b
```

On Windows, prefer `scripts/start_vllm_servers.bat` for operator sessions. It
starts the systemd service and a single named `goodq-vllm-keepalive` process so
WSL does not tear down while the model warms up.

On the primary workstation, the Windows Task Scheduler task
`GoodQ4All vLLM WSL Startup` may call this wrapper at user logon. Treat that as
a local machine fixture, not a portable repo requirement.

### Manual Recovery / Operator Reference

Use:
- `docs/guides/llm/VLLM_SYSTEMD_SETUP.md`

### Windows Convenience Launcher

Use `scripts/start_vllm_servers.bat` if you want a Windows wrapper for the current systemd-backed primary endpoint.
Use `scripts/stop_vllm_servers.bat` to stop the service and clear the keepalive anchor.

The older `scripts/start_llm_servers.bat` launcher has been retired with the direct-start multi-model chain it depended on.

The older raw-process helper `scripts/wsl/start_all_vllm.sh` has also been retired. The supported operator path is the systemd-backed installer and service flow.

## Quick Verification

From Windows:

```powershell
curl http://127.0.0.1:38005/v1/models
curl http://localhost:31434/v1/models
```

If the primary vLLM service is installed and the fallback Ollama service is available, both commands should return model metadata.

## Supported Endpoints Today

| Role | Source config | Default endpoint | Default model id |
|------|---------------|------------------|------------------|
| Primary | `llm.vllm_url` / `llm.vllm_model` | `http://localhost:38005/v1` | `meta-llama/Llama-3.2-1B-Instruct` |
| Fallback | `llm.ollama_url` / `llm.ollama_model` | `http://localhost:31434/v1` | `phi4:latest` |

## Management

### GPU Status

```bash
wsl -d <GOODQ_WSL_DISTRO> -- nvidia-smi
```

### vLLM Service Status

```bash
wsl -d <GOODQ_WSL_DISTRO> -u root -- systemctl status vllm-llama1b
```

### vLLM Logs

```bash
wsl -d <GOODQ_WSL_DISTRO> -- journalctl -u vllm-llama1b -f
```

### Restart vLLM

```bash
wsl -d <GOODQ_WSL_DISTRO> -u root -- systemctl restart vllm-llama1b
```

### Restart WSL Networking

```powershell
wsl --shutdown
```

## Troubleshooting

### Primary Endpoint Not Reachable

Check the service first:

```bash
wsl -d <GOODQ_WSL_DISTRO> -u root -- systemctl status vllm-llama1b
```

If needed:

```bash
wsl -d <GOODQ_WSL_DISTRO> -u root -- systemctl restart vllm-llama1b
```

### Connection Refused from Windows

Verify the primary endpoint from inside WSL:

```bash
wsl -d <GOODQ_WSL_DISTRO> -- curl http://localhost:38005/v1/models
```

If Windows still cannot reach it, review WSL networking configuration and then restart WSL:

```powershell
wsl --shutdown
```

### Fallback Not Reachable

Check the configured Ollama endpoint:

```powershell
curl http://localhost:31434/v1/models
```

If unavailable, bring Ollama up separately before relying on failover.

## Configuration Authority

The active LLM endpoints come from:
- `configs/config.yaml`
- local config overrides
- environment variables

The model list used by the client is built by:
- `steps/common/llm_model_factory.py`

That factory currently defines **two** models:
- `Llama-1B-Speed`
- `Phi4-Ollama`

If you want to expand the supported client surface, update the factory and the config contract together.

## Notes on Historical Drift

Older LLM docs and helpers described a larger stack with:
- multiple direct-start WSL scripts
- extra ports such as `38004`, `38001`, and `8000`
- model tiers like Qwen and Llama-11B

Those descriptions are not the current supported client contract. Treat them as advanced or historical unless and until the config-driven model factory is expanded to match them.
