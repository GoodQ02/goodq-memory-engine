<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-06-07 -->

# GoodQ4All Terminology & Concept Glossary

This glossary maps the key nouns, databases, tools, APIs, and directory-level concepts in GoodQ4All to their authoritative documentation and codebase components.

## Core Software & Middleware Components

* **`MiniAgentClient`**: 
  - *Description*: Gated safety middleware wrapper that intercepts LLM reasoning and native tool operations (e.g., Qdrant, FAISS, and Home Assistant).
  - *Location*: [`agents/mini_agent_client.py`](../../../agents/mini_agent_client.py)
  - *Documentation*: [`docs/architecture/AGENT_SYSTEM.md`](../../architecture/AGENT_SYSTEM.md)
* **`goodq_mini_agent`**:
  - *Description*: Pure-Python zero-dependency policy enforcement engine that validates tool calls against strict JSON schemas.
  - *Conda Env*: Installed in the `goodq_core` environment.
  - *Config directory*: [`agents/stack/`](../../../agents/stack)
* **`LLMClient`**:
  - *Description*: Unified local LLM connection manager supporting failover and connection health checks.
  - *Location*: [`lib/llm_client.py`](../../../lib/llm_client.py)
  - *Documentation*: [`docs/architecture/LLM_CLIENT_INJECTION_CONTRACT.md`](../../architecture/LLM_CLIENT_INJECTION_CONTRACT.md)
* **`ControlAgent`**:
  - *Description*: Conditionally active self-healing and system diagnostics manager.
  - *Location*: [`agents/control_agent.py`](../../../agents/control_agent.py)
  - *Documentation*: [`docs/CONTROL_AGENT.md`](../../CONTROL_AGENT.md)
* **`ConfigHealer`**:
  - *Description*: Subsystem helper that safely fixes configuration errors with backups.
  - *Location*: [`agents/config_healer.py`](../../../agents/config_healer.py)
  - *Documentation*: [`docs/CONTROL_AGENT.md`](../../CONTROL_AGENT.md)

## Ingestion & Control Plane

* **`watchdog`**:
  - *Description*: Background folder observer that monitors the import inbox for new media, running the ingestion DAG automatically.
  - *Location*: [`cli/watchdog.py`](../../../cli/watchdog.py)
  - *Documentation*: [`docs/systems/WATCHDOG_SYSTEM.md`](../systems/WATCHDOG_SYSTEM.md)
* **`run_ingestion`**:
  - *Description*: Canonical CLI entrypoint for manual and batch ingestion of media.
  - *Location*: [`cli/run_ingestion.py`](../../../cli/run_ingestion.py)
  - *Documentation*: [`docs/CLI-REFERENCE.md`](../../CLI-REFERENCE.md)
* **`LAUNCH_GOODQ.exe` / `LAUNCH_GOODQ.ps1`**:
  - *Description*: Supervising Go launcher / PowerShell bootstrap wrapper that checks ports, environment variables, starts the local daemons (Qdrant, API), and boots the visual consoles.
  - *Location*: Root executable/script.
  - *Documentation*: [`docs/guides/FIRST_RUN.md`](../FIRST_RUN.md)

## Visual & Browsing Consoles

* **`Retro Memory Explorer`**:
  - *Description*: Read-only visual cockpit, served locally at `/ui/retro_console_v1/`. Includes the helipad drag-and-drop Upload Pad, resizable split-panels, CRT frame previews, and entity co-occurrence canvas graphs.
  - *Code location*: `ui/retro_console_v1/`
  - *Documentation*: [`docs/agent/CURRENT_STATE.md`](../../agent/CURRENT_STATE.md)
* **`Operator Console`**:
  - *Description*: Bounded operator read-only preview served locally at `/ui/operator_console_v1/`. Includes preflight strips, current scope diagnostic indicators, and verification statistics.
  - *Code location*: `ui/operator_console_v1/`
  - *Documentation*: [`docs/agent/CURRENT_STATE.md`](../../agent/CURRENT_STATE.md)

## Databases & Vectors

* **`Qdrant`**:
  - *Description*: Windows native service serving as the authoritative vector store for CLIP, DINOv2, Text, and Audio embedding collection points.
  - *Default Port*: 6333
  - *Documentation*: [`docs/guides/QDRANT_SETUP.md`](../QDRANT_SETUP.md)
* **`FAISS`**:
  - *Description*: Dense vector indexes stored in the active epoch folder used for parity retrieval. Locked via `FaissLock` to prevent concurrency collisions.
  - *Code location*: [`steps/common/faiss_utils.py`](../../../steps/common/faiss_utils.py)
  - *Documentation*: [`docs/architecture/MEMORY_STORAGE.md`](../../architecture/MEMORY_STORAGE.md)
* **`SQLite Memory DB`**:
  - *Description*: The relational database containing parsed scenes, segments, links, and transaction commit events.
  - *Location*: Resolved as `<GOODQ_DATA_ROOT>/GoodQ_Data/db/memory.db`.
  - *Documentation*: [`docs/architecture/MEMORY_STORAGE.md`](../../architecture/MEMORY_STORAGE.md)
* **`Knowledge Graph DB`**:
  - *Description*: Relational database containing entity nodes, links, and temporal context.
  - *Location*: Resolved as `<GOODQ_DATA_ROOT>/GoodQ_Data/db/knowledge_graph.db`.
  - *Documentation*: [`docs/architecture/MEMORY_STORAGE.md`](../../architecture/MEMORY_STORAGE.md)

## Paths & Storage Abstractions

* **`GOODQ_DATA_ROOT`**:
  - *Description*: Environment variable defining the base writeable root for the local system (defaults to `%PROGRAMDATA%\GoodQ4All` or user profile).
  - *Documentation*: [`docs/architecture/CONFIG_LOADING_CONTRACT.md`](../../architecture/CONFIG_LOADING_CONTRACT.md)
* **`import_inbox`**:
  - *Description*: Folder monitored by watchdog for incoming files, resolved as `<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox\`.
  - *Documentation*: [`docs/guides/FIRST_RUN.md`](../FIRST_RUN.md)
* **`epochs`**:
  - *Description*: Dynamic directory structure storing logs, intermediate state, and vector indexes for a specific run campaign (e.g., `epoch_2026_06_02_family_clean_01`).
  - *Documentation*: [`docs/SCENE_MANIFEST_SPECIFICATION.md`](../../SCENE_MANIFEST_SPECIFICATION.md)

## Pipeline Algorithms & AI Services

* **`Phase 6b (Harmonization)`**:
  - *Description*: Ingestion pipeline stage that fuses transcript, visual descriptions, and audio signals into a unified temporal scene index.
  - *Documentation*: [`docs/PHASE6_MULTIMODAL_FUSION.md`](../../PHASE6_MULTIMODAL_FUSION.md)
* **`vLLM`**:
  - *Description*: Local high-speed LLM server hosted on WSL serving Qwen. Capped via `--gpu-memory-utilization` to conserve VRAM.
  - *Documentation*: [`docs/agent/CURRENT_STATE.md`](../../agent/CURRENT_STATE.md)
* **`Ollama`**:
  - *Description*: Local fallback LLM server hosted on Windows running Phi4. Optimized via Flash Attention.
  - *Documentation*: [`docs/agent/CURRENT_STATE.md`](../../agent/CURRENT_STATE.md)
* **`faster-whisper`**:
  - *Description*: WSL2-based audio transcriber and diarizer pipeline.
  - *Documentation*: [`docs/reference/WSL_AUDIO_RUNTIME.md`](../WSL_AUDIO_RUNTIME.md)
