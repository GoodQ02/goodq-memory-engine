<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-03-20 -->

# Error Handling & Recovery System

**Status:** Operational with conditional Control Agent support  
**Last Verified:** 2026-03-20

## Current Runtime Truth

GoodQ handles failures through visible runtime state, persisted artifacts, and bounded recovery helpers.

- critical path failures are logged and surfaced
- non-critical enrichments may fail without halting ingestion
- watchdog and ingestion runs persist status metadata and output artifacts
- Control Agent diagnosis is available only when an `llm_client` is explicitly injected
- there is no canonical always-on autonomous healing daemon in the default runtime

For current behavior, trust:

- `docs/CONTROL_AGENT.md`
- `docs/systems/WATCHDOG_SYSTEM.md`
- `cli/run_ingestion.py`
- `cli/watchdog.py`

## Active Recovery Surfaces

- `agents/config_healer.py` - targeted config-healing helper
- `agents/recovery_db.py` - persistent recovery-memory store
- `agents/recovery_strategies.py` - historical strategy store
- `agents/control_agent.py` - conditional diagnosis/healing coordinator

These are supporting surfaces, not a separate guaranteed service layer.

## Runtime Pattern

### Default CLI Behavior

- `cli/run_ingestion.py` records deterministic control-agent status
- `cli/watchdog.py` records watchdog state and recovery context
- failures remain visible in logs, manifests, and run artifacts

### Optional Diagnosis Path

If an `llm_client` is explicitly injected:

- Control Agent may analyze errors
- recovery recommendations may be generated
- healing reports may be written

If no `llm_client` is injected:

- the runtime persists the disabled state explicitly
- ingestion continues under the normal local contract

## Historical Surfaces

The original Phase 2 / Phase 3 self-healing campaign produced standalone validation harnesses that are no longer part of the active support surface:

- `scripts/archive/legacy_validation/root/test_recovery_system.py`
- `scripts/archive/legacy_validation/root/test_phase3_healing.py`
- `scripts/archive/legacy_validation/root/test_phase2_integration.py`

These are preserved as historical reference only.

## Operator Guidance

- Use canonical runtime commands first.
- Treat archived recovery harnesses as historical evidence, not current acceptance tests.
- When debugging current runtime behavior, prefer:
  - `python scripts/utils/check_watchdog_status.py`
  - `python scripts/test_llm_client.py`
  - `python scripts/test_wsl2_bridge.py`

## Related Docs

- `docs/CONTROL_AGENT.md`
- `docs/systems/WATCHDOG_SYSTEM.md`
- `docs/CLI-REFERENCE.md`
- `docs/archive/phases/PHASE3_SELF_HEALING.md`
