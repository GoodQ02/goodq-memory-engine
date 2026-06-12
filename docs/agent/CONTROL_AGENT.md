<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-03 -->

# Control Agent & Self-Healing System

**Status:** ⚠️ CONDITIONAL - Runtime disabled by default unless an `llm_client` is explicitly injected  
**Last Updated:** May 3, 2026
**Version:** 1.0.0

---

## Overview

The Control Agent is GoodQ4All's conditional monitoring, diagnosis, and healing subsystem. In the current runtime contract, it requires explicit `llm_client` injection to initialize; default CLI flows persist a deterministic disabled state instead of attempting best-effort auto-init.

Current reality: the active control surface is observer-only. It can summarize and trend existing recurrence artifacts, but it cannot heal, mutate configs, trigger ingestion, or take execution authority.

---

## Active Read-Only Control Substrate (2026-05-03)

The active control-plane surface now includes a read-only recurrence instrument:

- `lib/control_recurrence_report.py`
- `lib/control_recurrence_index.py`
- `lib/control_recurrence_recommendations.py`
- `lib/control_recurrence_trend.py`
- `python -m cli.control_recurrence_report`
- `GET /api/control-recurrence/reports`
- `GET /api/control-recurrence/reports/latest`
- `GET /api/control-recurrence/reports/trend`
- `GET /api/control-recurrence/reports/{report_id}`
- `GET /api/control-recurrence/reports/{report_id}/markdown`
- `GET /api/control-recurrence/reports/{report_id}/recommendations`

Boundary: not healing yet. This instrument is not `ControlAgent` activation. It does not enable auto-healing, does not mutate configs, does not execute commands, does not use LLMs, does not generate reports from the API, and does not touch `cli/run_ingestion.py`.

It reads persisted runtime truth only:

- `step_runs.jsonl`
- run warnings
- `scene_ingest_results.json`
- `scene_manifest.json`
- `temporal_index.json`
- `experiment_log.json`
- `operator_run_metadata.json` and captured ingestion stdout/stderr events when a direct canonical run root has no wrapper `experiment_log.json`

It reports recurrence summaries, comparison deltas, category counts, recovered/unrecovered/skipped counts, Phase 6 health, Qdrant health, deterministic operator hints, deterministic inspection-only recommendation drafts, conservative trend summaries over existing durable JSON reports, and optional markdown/JSON artifacts under `reports/control_recurrence/`. Durable artifact discovery is recorded in `reports/control_recurrence/index.json`. Direct `cli.run_ingestion` run roots are supported read-only through existing output/workspace/operator-log artifacts, including multi-video direct roots; this does not create a second execution path.

For multi-video direct roots, shared captured stdout events are scoped by
persisted video and scene identity before recurrence aggregation. Recovered
native retry witnesses still coalesce once across run warnings, runtime events,
stderr text, and `step_runs.jsonl`.

The API surface reads only that existing index and the indexed artifacts. It does not regenerate reports, trigger ingestion, execute commands, scan arbitrary project paths, or form a second orchestration path.

Audio-vector interpretation boundary: recurrence reports, trend summaries, API
payloads, and operator recommendations must use the audio provenance contract
when discussing CLAP/Qdrant coverage. Current-run audio vector success requires
`clap_meta.status == ok` plus a Qdrant audio payload with matching `run_id` and
required provenance fields. Scene-id-only Qdrant matches are
provenance-unverified, not current-run proof.

Exact command examples:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --run-id 20260424_182406_season2_fresh_witness
```

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --run-root reports/fresh_ingest_runs/<direct_run_root> --write-md --write-json-file
```

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --baseline-run-id 20260424_003250_season1_recompare_witness --candidate-run-id 20260424_182406_season2_fresh_witness --json
```

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --baseline-run-id 20260424_003250_season1_recompare_witness --candidate-run-id 20260424_182406_season2_fresh_witness --write-md
```

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --run-id 20260424_182406_season2_fresh_witness --write-md --write-json-file
```

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --list-reports --json
```

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --recommendations-for 20260424_003250_season1_recompare_witness__vs__20260424_182406_season2_fresh_witness
```

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --trend --json
```

```powershell
curl http://127.0.0.1:30000/api/control-recurrence/reports
```

```powershell
curl http://127.0.0.1:30000/api/control-recurrence/reports/latest
```

```powershell
curl http://127.0.0.1:30000/api/control-recurrence/reports/trend
```

```powershell
curl http://127.0.0.1:30000/api/control-recurrence/reports/20260424_182406_season2_fresh_witness
```

```powershell
curl http://127.0.0.1:30000/api/control-recurrence/reports/20260424_003250_season1_recompare_witness__vs__20260424_182406_season2_fresh_witness/recommendations
```

Use this as the first safe control-agent substrate: operator awareness and pattern visibility before any healing authority is considered.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CONTROL AGENT                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │  Config Healer   │  │ Self-Healing     │               │
│  │                  │  │ Monitor          │               │
│  │ • Parse errors   │  │ • Watch pipeline │               │
│  │ • Generate fixes │  │ • Apply patterns │               │
│  │ • Backup configs │  │ • Track outcomes │               │
│  └──────────────────┘  └──────────────────┘               │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │          Recovery Strategies Database                │  │
│  │                                                      │  │
│  │  • Error patterns & fixes                           │  │
│  │  • Success rate tracking                            │  │
│  │  • Learning from outcomes                           │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │               LLM-Powered Diagnosis                  │  │
│  │                                                      │  │
│  │  • Analyze complex errors                           │  │
│  │  • Suggest novel solutions                          │  │
│  │  • Generate diagnostic reports                      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. Control Agent (agents/control_agent.py)

The orchestrator that ties everything together.

**Responsibilities:**
- Monitor pipeline logs and execution
- Analyze errors and suggest fixes
- Learn from past failures/successes
- Generate diagnostic reports
- Build knowledge base for self-improvement

**Key Methods:**
```python
# Analyze error with rule-based + LLM diagnosis
diagnosis = agent.diagnose_error(error_message, context)

# Attempt automatic healing
result = agent.auto_heal_failure(error, step_name, context)

# Learn from successful runs
agent.learn_from_success(step_name, execution_time, gpu_usage)

# Generate comprehensive report
agent.generate_report(output_path, diagnosis)

# Get actionable insights
insights = agent.get_insights()
```

### 2. Config Healer (agents/config_healer.py)

Autonomous config modification with safety backups.

**Known Healing Rules:**

| Error Pattern | Actions | Auto-Apply |
|---------------|---------|------------|
| CUDA out of memory | • Reduce batch size<br>• Switch to CPU<br>• Use smaller model | ✅ Yes |
| No audio stream found | • Skip audio step<br>• Mark as silent | ✅ Yes |
| Connection timeout | • Increase timeout<br>• Enable retry | ⚠️ Ask LLM |
| PyAnnote failed | • Increase warmup delay<br>• Switch to CPU<br>• Skip diarization | ⚠️ Ask LLM |
| Whisper RuntimeError | • Use smaller model<br>• Reduce chunk size | ✅ Yes |

On the active line, the control plane can now apply a bounded set of real config-healing actions when a healer is initialized. Supported delegated actions include `reduce_batch_size`, `switch_to_cpu`, `enable_retry`, `skip_step`, `partition_audio`, and model downgrades. Pattern families without a mapped bounded action still fail honestly instead of reporting simulated success.

**Safety Features:**
- All config modifications backed up to `data/config_backups/`
- Versioned backups with timestamps
- Rollback capability
- Dry-run mode for testing

### 3. Self-Healing Monitor (agents/self_healing_monitor.py)

Continuous background monitoring daemon.

**Monitoring Capabilities:**
- Check recent workflow executions
- Detect recurring failure patterns
- Apply fixes proactively
- Track healing success rates

**Error Pattern Recognition:**

```python
patterns = [
    "timeout" → retry_with_backoff
    "memory_error" → reduce_batch_size
    "model_not_found" → fallback_local_model
    "cuda_error" → fallback_to_cpu
    "empty_result" → adjust_thresholds
    "file_not_found" → skip_missing_file
]
```

Current truth on the active line:
- `retry_with_backoff`, `reduce_batch_size`, `fallback_to_cpu`, `fallback_local_model`, and `skip_missing_file` delegate to real bounded healer actions when the monitor is initialized with a healer.
- `fallback_local_model` prefers a smaller local model instead of attempting network downloads, preserving the local-first contract.
- `adjust_thresholds` now performs bounded scene-detection threshold tuning when the failed step is a scene-detection lane, and still returns an explicit no-mapped outcome for unsupported steps instead of pretending to heal successfully.

### 4. Recovery Strategies Database (agents/recovery_strategies.py)

Knowledge base that grows smarter over time.

**Database Schema:**

```sql
-- Track every recovery attempt
recovery_history:
  - timestamp, error_type, error_message
  - step_name, context
  - strategy_applied, outcome
  - success (boolean), duration_seconds
  - gpu_usage_mb, metadata

-- Learn optimal patterns
error_patterns:
  - pattern_name, error_regex
  - recommended_strategy
  - success_rate, total_attempts
  - successful_attempts, last_updated
```

**Learning Mechanism:**
1. Error occurs → Check pattern database
2. Apply highest success-rate strategy
3. Record outcome (success/failure)
4. Update success rate statistics
5. LLM suggests new strategies if pattern fails repeatedly

---

## Integration Points

### In Ingestion Pipeline (cli/run_ingestion.py)

Control Agent integration points exist, but default runtime startup records an explicit disabled state when no `llm_client` is injected.

#### 1. Startup State Persistence
```python
control_agent_status = "disabled_no_llm_client"
control_agent_reason = "ControlAgent requires injected llm_client"
```

#### 2. Step-Level Healing/Learning (Conditional)
```python
if control_agent_status == "initialized":
    agent = ControlAgent(llm_client=llm_client)
    # auto_heal_failure / learn_from_success
```

#### 3. Final Report Generation
```python
if control_agent:
    report_path = workspace / "control_agent_report.md"
    control_agent.generate_report(str(report_path))
```

---

## Databases & Storage

### Primary Database
**Location:** `<GOODQ_DATA_ROOT>/GoodQ_Data/control_memory.db`

**Tables:**
- `error_memory` - Error history and recovery attempts
- `success_patterns` - Successful runs for learning
- `file_tracking` - File processing status
- `recommendations` - Agent recommendations and outcomes

### Recovery Database
**Location:** `<GOODQ_DATA_ROOT>/GoodQ_Data/recovery.db`

**Purpose:** Stores recovery strategies and success rates

### Config Backups
**Location:** `<project_root>/data/config_backups/`

**Format:** `config_open_backup_YYYYMMDD_HHMMSS.yaml`

---

## Usage Examples

These examples describe direct module-level `ControlAgent` APIs after an
operator has explicitly injected an approved local `llm_client`. They are not
the canonical CLI/watchdog runtime path.

### Manual Diagnosis

```python
from agents.control_agent import ControlAgent

agent = ControlAgent(llm_client=llm_client)

# Analyze an error
diagnosis = agent.diagnose_error(
    error_message="CUDA out of memory",
    context={
        "step_name": "face_embed",
        "gpu_usage_mb": 15800,
        "batch_size": 32
    }
)

print(diagnosis)
# {
#     "error_pattern": "cuda_oom",
#     "recommended_actions": ["reduce_batch_size", "switch_to_cpu"],
#     "auto_apply": True,
#     "confidence": 0.95
# }
```

### Conditional Auto-Heal API (Disabled in Canonical Runtime)

```python
# Only valid after explicit local llm_client injection outside canonical ingest.
result = agent.auto_heal_failure(
    error=Exception("CUDA OOM during processing"),
    step_name="face_embed",
    context={"batch_size": 32, "gpu_memory": 15800}
)

if result["healed"]:
    print(f"✅ Applied fix: {result['fix_applied']}")
    print(f"New config: {result['new_config']}")
else:
    print(f"⚠️ Manual intervention needed")
```

### Learning from Success

```python
# After successful processing
agent.learn_from_success(
    step_name="image_embed_dino",
    execution_time=45.2,
    gpu_usage={"avg": 8200, "peak": 12400}
)
```

### Generate Diagnostic Report

```python
# Create comprehensive analysis
agent.generate_report(
    output_path="reports/system_health.md",
    diagnosis={"last_24h_errors": [...], "trends": [...]}
)
```

---

## Canonical Runtime Boundary

```
1. Video processing starts
   -> cli.run_ingestion.py remains the canonical execution owner

2. Control Agent module availability may be checked
   -> availability is not activation

3. No injected llm_client is present by default
   -> runtime records disabled_no_llm_client

4. Optional failures are persisted in truth surfaces
   -> step_runs.jsonl, run warnings, manifests, temporal index

5. Read-only recurrence tools inspect persisted artifacts
   -> summaries, comparisons, recommendations, trends

6. No automatic config mutation, command execution, ingestion trigger, or healing occurs
```

---

## Configuration

### Enable/Disable Control Agent

Current default CLI/watchdog startup does not enable the Control Agent just
because the module imports successfully. Runtime activation requires an
explicit injected `llm_client`; otherwise ingestion records
`disabled_no_llm_client` and continues deterministically without auto-healing.

The import guard in `cli/run_ingestion.py` only records whether the Control
Agent code is available:
```python
CONTROL_AGENT_AVAILABLE = True  # module imported, not runtime-enabled
```

To enable Control Agent behavior, wire an approved local `llm_client` injection
path and verify the resulting `control_agent_status` in the run context. Do not
treat `CONTROL_AGENT_AVAILABLE` as a user-facing feature flag.

### Config Healer Settings

Edit `agents/config_healer.py`:
```python
HEALING_RULES = {
    "your_error_pattern": {
        "actions": ["action1", "action2"],
        "priority": "high",
        "auto_apply": True
    }
}
```

### Database Locations

Edit in respective agent files:
```python
# Control Agent
db_path = Path("<GOODQ_DATA_ROOT>/GoodQ_Data/control_memory.db")

# Recovery Strategies
db_path = Path("<GOODQ_DATA_ROOT>/GoodQ_Data/recovery.db")
```

---

## Reports & Outputs

### Control Agent Report

**Location:** `<workspace>/control_agent_report.md`

**Contents:**
- Pipeline execution summary
- Errors encountered and fixes applied
- Success/failure statistics
- Performance metrics
- Recommendations for optimization

### Recovery Logs

Stored in database with queryable history:
```sql
SELECT error_type, strategy_applied, success, timestamp
FROM recovery_history
WHERE timestamp > datetime('now', '-7 days')
ORDER BY timestamp DESC;
```

---

## Performance Impact

**Overhead:** Low in expected operation; verify per-run timing artifacts for current values.

**Benefits:**
- Faster diagnosis and triage when initialized with an injected `llm_client`
- Reduced manual intervention when healing rules match known failures
- Explicit control-plane status persistence even when disabled

---

## Runtime Status (Artifact-Verified)

**Current runtime contract:**

✅ Control Agent module imports and storage schemas are present  
✅ Run artifacts persist explicit control-plane state (`control_agent_status`)  
⚠️ Default CLI/watchdog flows persist `disabled_no_llm_client` unless `llm_client` is injected  
⚠️ Auto-healing, learning, and report generation are active only when initialization succeeds

**Verification guidance:**
- Trust per-run artifacts (`control_agent_status`, `control_agent_reason`) over static document claims.
- Treat historical aggregate metrics as non-authoritative unless regenerated from current databases.

---

## Future Enhancements

### Planned Features (Phase 3):
- **Predictive Failure Detection** - Spot issues before they occur
- **Multi-Agent Coordination** - Control Agent + Watchdog + Orchestrator sync
- **Adaptive Batch Sizing** - Learn optimal batch sizes per GPU/model
- **Remote Monitoring API** - Query health status via HTTP endpoint
- **Anomaly Detection** - ML-based pattern recognition for novel errors

### Experimental:
- **Self-Optimization** - Tune hyperparameters automatically
- **Cost Optimization** - Balance performance vs. resource usage
- **A/B Testing** - Try multiple recovery strategies simultaneously

---

## Troubleshooting

### Control Agent Disabled by Default (Expected)

```bash
# Check if module import succeeds
python -c "from agents.control_agent import ControlAgent; print('OK')"

# Verify databases exist
ls <GOODQ_DATA_ROOT>\GoodQ_Data\control_memory.db
ls <GOODQ_DATA_ROOT>\GoodQ_Data\recovery.db
```

### Healing Not Applied

Check logs for:
```
[CONTROL] Control Agent disabled: no llm_client injection
control_agent_status=disabled_no_llm_client
```

### Database Locked

```python
# Reset database connection
from agents.control_agent import ControlAgent
agent = ControlAgent(llm_client=llm_client)
agent.recovery_db.conn.close()
```

---

## Related Documentation

- **Agent operating protocol:** `AGENTS.md`
- **Decision protocol:** `docs/architecture/AGENT_DECISION_PROTOCOL.md`
- **Current runtime status:** `docs/goodq4all_agent_status.md`
- **Canonical Watchdog system:** `docs/systems/WATCHDOG_SYSTEM.md`

---

## Conclusion

The Control Agent subsystem is production code with explicit activation semantics: default CLI/watchdog flows persist a deterministic disabled state until an injected `llm_client` integration is provided.

GoodQ4All remains unattended-capable through watchdog + artifact-backed observability, with control-plane state declared in run metadata for each run.
