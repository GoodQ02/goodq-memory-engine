# GoodQ Agent Utilities

**Status:** Mixed state - conditional runtime utilities plus legacy orchestration artifacts  
**Last Verified:** 2026-03-13

---

## Overview

The `agents/` directory is **not** a single canonical production runtime.

Current runtime truth:

- The authoritative ingestion entry points are `cli/run_ingestion.py` and `cli/watchdog.py`.
- `ControlAgent` still exists, but default CLI/runtime flows record `disabled_no_llm_client` unless an `llm_client` is explicitly injected.
- `watchdog_agent_integration.py`, `pipeline_integration.py`, and `orchestrator.py` represent an older parallel orchestration path and should not be treated as canonical bootstrap/runtime surfaces.

---

## Component Status

| Component | File | Current role | Status |
|-----------|------|--------------|--------|
| Control Agent | `control_agent.py` | Conditional diagnosis/healing utility requiring injected `llm_client` | Conditional |
| Config Healer | `config_healer.py` | Runtime healing helper used by Control Agent flows | Runtime utility |
| Self-Healing Monitor | `self_healing_monitor.py` | Runtime/diagnostic helper | Runtime utility |
| Recovery Database | `recovery_db.py` | Stores recovery history and outcomes | Runtime utility |
| Recovery Strategies | `recovery_strategies.py` | Strategy library for healing actions | Runtime utility |
| LLM Agent | `llm_agent.py` | Optional reasoning helper for advanced/legacy flows | Partial |
| Orchestrator | `orchestrator.py` | Legacy multi-agent workflow coordinator | Historical |
| Watchdog Agent Integration | `watchdog_agent_integration.py` | Legacy parallel file-watcher/orchestrator path | Historical |
| Pipeline Integration | `pipeline_integration.py` | Legacy wrapper layer for agent-driven ingestion | Historical |

---

## What To Trust

- Current Control Agent contract: `docs/CONTROL_AGENT.md`
- Current Watchdog/runtime contract: `docs/systems/WATCHDOG_SYSTEM.md`
- Current CLI behavior: `docs/CLI-REFERENCE.md`

If these disagree with older agent/orchestration notes, trust the docs above and the current runtime code.
