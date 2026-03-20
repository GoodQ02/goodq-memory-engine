# GoodQ4All Agent System

> Historical architecture reference. Use this file to understand the shape of the older agent initiative, not as the current runtime contract.

**Status:** Historical / mixed-state reference  
**Last Verified:** 2026-03-20

## Current Runtime Truth

- `cli/watchdog.py` is the canonical automatic ingestion entrypoint.
- `cli/run_ingestion.py` and `cli/watchdog.py` persist explicit control-plane state for every run.
- `agents/control_agent.py` is conditional and disabled by default unless an `llm_client` is explicitly injected.
- `agents/watchdog_agent_integration.py`, `agents/pipeline_integration.py`, and `agents/orchestrator.py` are retired legacy surfaces.
- The current truth anchors are:
  - `docs/CONTROL_AGENT.md`
  - `docs/systems/WATCHDOG_SYSTEM.md`
  - `docs/CLI-REFERENCE.md`

## What Still Matters

The surviving agent-related code is now a small, bounded subsystem:

- `agents/control_agent.py` - conditional diagnosis/healing coordinator
- `agents/config_healer.py` - safe config-healing helper with backups
- `agents/recovery_db.py` - persistent recovery-memory store
- `agents/recovery_strategies.py` - historical pattern/recommendation store
- `agents/self_healing_monitor.py` - supporting monitor code, not a canonical always-on service

These components are useful as supporting machinery, but they are not a separate always-on multi-agent runtime.

## What Was Retired

The original agent push experimented with:

- parallel watchdog wrappers
- orchestration bridges
- multi-agent coordination
- phase-specific recovery harnesses

Those surfaces are now archived or retired because they no longer match the supported runtime contract.

Historical validation harnesses live under:

- `scripts/archive/legacy_validation/root/test_recovery_system.py`
- `scripts/archive/legacy_validation/root/test_phase3_healing.py`
- `scripts/archive/legacy_validation/root/test_phase2_integration.py`

## Practical Guidance

- For current watchdog behavior, use `python -m cli.watchdog`.
- For current ingestion behavior, use `python -m cli.run_ingestion`.
- For current control-agent boundaries, use `docs/CONTROL_AGENT.md`.
- Treat this document as architecture history and design context only.

## Related Docs

- `docs/CONTROL_AGENT.md`
- `docs/systems/WATCHDOG_SYSTEM.md`
- `docs/PHASE6_MULTIMODAL_FUSION.md`
- `docs/archive/phases/PHASE3_SELF_HEALING.md`
