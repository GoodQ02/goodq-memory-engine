<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-02-12 -->

# Control Agent & Self-Healing System

**Status:** ⚠️ CONDITIONAL - Runtime disabled by default unless an `llm_client` is explicitly injected  
**Last Updated:** December 15, 2025  
**Version:** 1.0.0

---

## Overview

The Control Agent is GoodQ4All's monitoring, diagnosis, and healing subsystem. In the current runtime contract, it requires explicit `llm_client` injection to initialize; default CLI flows persist a deterministic disabled state instead of attempting best-effort auto-init.

**Think of it as:** An intelligent DevOps engineer that never sleeps, continuously learning optimal recovery patterns and applying fixes before you even notice problems.

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
    "model_not_found" → download_model
    "cuda_error" → fallback_to_cpu
    "empty_result" → adjust_thresholds
    "file_not_found" → skip_missing_file
]
```

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

### Automatic Healing

```python
# Trigger auto-healing
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

## Example Healing Workflow

```
1. Video processing starts
   └─> Control Agent initialized

2. Step "face_embed" fails with CUDA OOM
   └─> Error caught by run_ingestion.py
       └─> Calls agent.auto_heal_failure()

3. Control Agent analyzes error
   ├─> Checks HEALING_RULES (pattern match: "CUDA out of memory")
   ├─> Checks recovery_strategies DB (current success-rate metadata)
   └─> Recommended: reduce_batch_size (auto_apply=True)

4. Config Healer applies fix
   ├─> Backs up current config
   ├─> Modifies batch_size: 32 → 16
   ├─> Saves new config
   └─> Returns success=True

5. Step retries with new config
   └─> Success! (execution time: 52s, GPU: 7800MB)

6. Control Agent learns
   ├─> Records successful healing in recovery_history
   ├─> Updates success_rate in error_patterns
   └─> Stores optimal config in success_patterns

7. Next time same error occurs
   └─> Healing is even faster (learned pattern applied immediately)
```

---

## Configuration

### Enable/Disable Control Agent

Set in `cli/run_ingestion.py`:
```python
CONTROL_AGENT_AVAILABLE = True  # Set to False to disable
```

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

**Location:** `logs/scene_ingest/<video>/control_agent_report.md`

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

- **Agents System:** `docs/agents.md` (coming soon)
- **Pipeline Integration:** `docs/PIPELINE_ARCHITECTURE.md`
- **Configuration:** `docs/CONFIGURATION.md`
- **Canonical Watchdog Runtime:** `cli/watchdog.py`

---

## Conclusion

The Control Agent subsystem is production code with explicit activation semantics: default CLI/watchdog flows persist a deterministic disabled state until an injected `llm_client` integration is provided.

GoodQ4All remains unattended-capable through watchdog + artifact-backed observability, with control-plane state declared in run metadata for each run.
