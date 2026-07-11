<!-- DOC_LAST_VERIFIED: 2026-07-11 -->
# Gemini Desktop Agent & Workspace Integration

This guide documents the integration, environment path settings, Model Context Protocol (MCP) servers, credentials, and local workstation configurations for the primary dev workstation.

## Authority Boundary

Read `docs/agent/PROJECT_ORIENTATION.md` first. This file is an operational
Gemini/workstation integration guide, not authority for live service state,
current model inventory, persisted GoodQ results, branch governance, or product
behavior. Counts, model names, permissions, and roadmap items below are snapshots
or configuration examples and must be verified before use. Repository contracts
and live evidence retain their question-specific authority.

---

## 1. Shell Environment & PATH Governance

To prevent command resolution failures for development tools (such as Node.js, Conda, and global packages), the shell environment is dynamically managed:

* **PowerShell 7 Profile**: Configured in `%USERPROFILE%\Documents\PowerShell\Microsoft.PowerShell_profile.ps1`.
* **Path Normalization**: The profile implements a dynamic path restorer `Add-GoodCubePersistedPathEntries` which:
  1. Reads all paths from the process environment, Machine registry, and User registry.
  2. Normalizes paths (deduplicates entries and resolves trailing slashes).
  3. Dynamically expands nested environment variables (e.g., `%NVM_HOME%` and `%NVM_SYMLINK%`) to absolute paths.
  4. Automatically overrides the active `$env:Path` when differences are detected, making Node, Python, and git instantly visible on startup.

---

## 2. Model Context Protocol (MCP) Setup

MCP servers are registered globally in `%USERPROFILE%\.gemini\config\mcp_config.json`. As of 2026-06-30, 12 servers are configured:

**Local npx-based servers:**
1. **`chrome-devtools-mcp`** — Chrome DevTools automation (click, navigate, screenshot, etc.)
2. **`sequential-thinking`** — Structured reasoning tool
3. **`everything`** — Mock reference server for testing

**Google Cloud managed MCP servers** (authenticated via `google_credentials`):
4. **`cloud-sql-managed-mcp`** — Cloud SQL instance management
5. **`gmp-code-assist`** — Google Maps code assistance
6. **`google-cloud-logging`** — Cloud Logging queries
7. **`google-cloud-monitoring`** — Cloud Monitoring metrics and alerts
8. **`google-cloud-resource-manager`** — Project search
9. **`google-compute-engine`** — Compute Engine instance management
10. **`google-developer-knowledge`** — Developer documentation search
11. **`vertex-ai-search`** — Vertex AI Search and conversational search
12. **`knowledge-catalog`** — Dataplex knowledge catalog

**HTTP MCP servers with API keys:**
- **`context7`** — Library documentation (requires `CONTEXT7_API_KEY` header). Key stored as literal in JSON because Gemini does not support env var expansion in MCP headers. Must match canonical key in `%USERPROFILE%\.env.local`.

**Global Permission Grants:**
* Configured in `%USERPROFILE%\.gemini\config\config.json`.
* Permitted domains: Includes `127.0.0.1`, `192.168.1.1`, `github.com`, and `*` (global URL reading via `read_url(*)`).

---

## 3. Local AI Model Hardening (VRAM Governance)

To safely manage memory on the RTX 4070 Ti SUPER 16GB GPU without Out-of-Memory (OOM) crashes, we enforce strict VRAM budgeting in `configs/models_config.yaml`:

```yaml
gpu_budget:
  total_vram_gb: 16.0
  reserved_display_gb: 1.5
  reserved_cuda_fragmentation_gb: 1.0
  usable_target_gb: 13.5
  emergency_stop_gb: 14.5
```

### Dynamic Execution Profiles
* **`GPU_16GB_INGEST_QUALITY`**: Running DeepSeek-R1-14B (Reasoning), Qwen2.5-VL-7B (Vision), and Whisper Large-v3-Turbo (Audio). Models load sequentially; concurrent execution is blocked, and resident models are evicted dynamically.
* **`GPU_16GB_INTERACTIVE_LIGHT`**: Running DeepSeek-R1-7B (Reasoning) and Qwen2.5-VL-3B (Vision) concurrently.
* **Model Lifecycle Manager**: Controlled via `lib/model_lifecycle.py` context manager, which audits free VRAM using PyTorch CUDA/nvidia-smi before executing model tasks.

---

## 4. Hugging Face & GitHub Authentication

To support automated model weight downloads (including gated models like Gemma 2 or Gemma 4) and codebase synchronization:

* **SSH Key Authentication**:
  * **GitHub**: Verified ED25519 key (`github:GOOD-CUBE`) is authenticated for remote repository actions.
  * **Hugging Face**: Verified ED25519 key is authenticated for repository access.
* **HF Token Security**:
  * Gated Hugging Face access tokens are isolated inside `.env.local` using `HF_TOKEN=<token_value>`.
  * The token is loaded dynamically by the model download scripts and is never logged or committed.

---

## 5. Local Compute Clustering Roadmap (LAN Extension)

> **STATUS: ROADMAP — Not yet implemented.** The following describes future intent, not production reality.

```
                  [ प्राइमरी Workstation (GOOD-CUBE) ]
                                  |
                      [ Nginx / LiteLLM Gateway ]
                                  |
         +------------------------+------------------------+
         |                                                 |
[ Compute Node B (Ollama) ]                      [ Compute Node C (Ollama) ]
```

1. **Load Balancing (LiteLLM)**: Run a LiteLLM gateway on the primary machine to distribute text completion requests across active Ollama instances on other LAN nodes.
2. **Distributed Inference (Ray/vLLM)**: Split large parameter models (e.g., 70B models) across multiple LAN GPUs using Ray clusters.
3. **Microservice Orchestration (K3s)**: Deploy a lightweight Kubernetes cluster to run containerized ingestion services, vector databases (Qdrant), and transcription pipelines.

---

## 6. IDE Provisioning (VS Code)

To integrate these local custom MCP servers and workspace indexes into your editor, VS Code can be provisioned silently:

* **Stable Release**:
  ```powershell
  winget install --id Microsoft.VisualStudioCode --silent --accept-package-agreements --accept-source-agreements
  ```
* **Insiders Preview**:
  ```powershell
  winget install --id Microsoft.VisualStudioCode.Insiders --silent --accept-package-agreements --accept-source-agreements
  ```
* **Recommended Extensions**: **Continue** or **Cursor** configured to point to local Ollama endpoints (`http://127.0.0.1:11434`) and your whitelisted local MCP servers.
