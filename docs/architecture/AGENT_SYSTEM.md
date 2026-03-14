# GoodQ4All Agent System

> Historical architecture reference - describes a legacy parallel agent-orchestration stack and should not be read as the current runtime contract.

**Status:** Historical / mixed-state reference  
**Last Verified:** 2026-03-13  
**Version:** Legacy 2025 architecture snapshot

---

## Current Runtime Truth

- `cli/watchdog.py` is the canonical file monitor / automatic ingestion entry point.
- `cli/run_ingestion.py` and `cli/watchdog.py` persist `control_agent_status=disabled_no_llm_client` by default unless an `llm_client` is explicitly injected.
- `agents/watchdog_agent_integration.py`, `agents/pipeline_integration.py`, and `agents/orchestrator.py` are retired legacy parallel surfaces, not the canonical watchdog/runtime path.
- For current behavior, trust `docs/CONTROL_AGENT.md`, `docs/systems/WATCHDOG_SYSTEM.md`, and `docs/CLI-REFERENCE.md`.

## Historical Overview

The GoodQ4All agent system is a collection of autonomous, intelligent components that work together to monitor, heal, and optimize the multimodal ingestion pipeline. These agents operate independently but share knowledge through common databases and configuration.

**Philosophy:** Agents are **observers and advisors**, not controllers. They monitor, suggest, heal, and learn—but never force destructive actions without explicit approval.

---

## Agent Roster

| Agent | Purpose | Status | Auto-Deploy |
|-------|---------|--------|-------------|
| **Control Agent** | Pipeline monitoring, error diagnosis, healing orchestration | ✅ Active | Yes |
| **Config Healer** | Autonomous configuration modification with safety backups | ✅ Active | Yes |
| **Self-Healing Monitor** | Real-time health tracking and auto-recovery | ✅ Active | Yes |
| **Watchdog Agent Integration** | File monitoring → ingestion trigger | ✅ Active | Yes |
| **Pipeline Integration** | Agent hooks into ingestion flow | ✅ Active | Yes |
| **LLM Agent** | Natural language processing and reasoning | 🔄 Partial | No |
| **Orchestrator** | Multi-agent task coordination | 🚧 Planned | No |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      USER / FILE SYSTEM                          │
│         (Drops video → <GOODQ_DATA_ROOT>\incoming\)                      │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ↓
┌──────────────────────────────────────────────────────────────────┐
│         WATCHDOG AGENT (watchdog_agent_integration.py)           │
│  • Monitors directories for new files                            │
│  • Triggers ingestion pipeline automatically                     │
│  • Logs events to agent_checkpoints/watchdog_events.db          │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ↓
┌──────────────────────────────────────────────────────────────────┐
│         PIPELINE INTEGRATION (pipeline_integration.py)           │
│  • Injects agent hooks into cli/run_ingestion.py                │
│  • Wraps step execution with monitoring                          │
│  • Forwards errors to Control Agent                              │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ↓
┌──────────────────────────────────────────────────────────────────┐
│              CONTROL AGENT (control_agent.py)                    │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Self-Healing Monitor                                      │ │
│  │  • Watches logs continuously (60s intervals)               │ │
│  │  • Detects error patterns                                  │ │
│  │  • Triggers recovery strategies                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                           ↓                                      │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Recovery Strategies Database                              │ │
│  │  • Query known error patterns                              │ │
│  │  • Retrieve best recovery strategy                         │ │
│  │  • Track success rates                                     │ │
│  └────────────────────────────────────────────────────────────┘ │
│                           ↓                                      │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Config Healer                                             │ │
│  │  • Apply config modifications                              │ │
│  │  • Backup before changes                                   │ │
│  │  • Execute recovery action                                 │ │
│  └────────────────────────────────────────────────────────────┘ │
│                           ↓                                      │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  LLM Agent (for ambiguous cases)                           │ │
│  │  • Analyze complex errors                                  │ │
│  │  • Suggest novel recovery approaches                       │ │
│  │  • Generate diagnostic reports                             │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
                         │
                         ↓
┌──────────────────────────────────────────────────────────────────┐
│              SHARED KNOWLEDGE BASES (SQLite)                     │
│  • <GOODQ_DATA_ROOT>\GoodQ_Data\control_memory.db                        │
│  • <GOODQ_DATA_ROOT>\GoodQ_Data\recovery.db                              │
│  • <GOODQ_DATA_ROOT>\GoodQ_Data\agent_checkpoints\watchdog_events.db    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Agent Details

### 1. Control Agent (`agents/control_agent.py`)

**Role:** Master orchestrator for pipeline intelligence

**Responsibilities:**
- Monitor pipeline execution logs
- Analyze errors and diagnose root causes
- Coordinate recovery strategies
- Learn from successes and failures
- Generate diagnostic reports
- Build knowledge base over time

**Key Methods:**
```python
from agents.control_agent import ControlAgent

agent = ControlAgent()

# Diagnose an error
diagnosis = agent.diagnose_error(
    error_message="CUDA out of memory",
    context={"gpu_usage_mb": 15800, "batch_size": 32}
)

# Attempt automatic healing
result = agent.auto_heal_failure(
    error_message="CUDA out of memory",
    step_name="image_embed_clip",
    context=context
)

# Learn from success
agent.learn_from_success(
    step_name="audio_transcription",
    execution_time=45.2,
    gpu_usage=8500
)

# Get analytics
stats = agent.get_learning_statistics()
```

**Configuration:**
```yaml
# config.yaml
control_agent:
  enabled: true
  auto_heal: true
  ask_llm_for_complex: true
  max_retry_attempts: 3
```

**Databases:**
- `<GOODQ_DATA_ROOT>\GoodQ_Data\control_memory.db` - Long-term learning
- `<GOODQ_DATA_ROOT>\GoodQ_Data\agent_checkpoints\control_memory.db` - Runtime state

---

### 2. Config Healer (`agents/config_healer.py`)

**Role:** Safe configuration modification with backups

**Responsibilities:**
- Parse YAML configuration
- Apply targeted modifications
- Create timestamped backups before changes
- Validate config after modifications
- Revert if modifications cause failures

**Known Healing Rules:**

| Error Pattern | Config Change | Backup Location |
|---------------|---------------|-----------------|
| CUDA OOM | `vision.batch_size: 32 → 16` | `config_backups/config.yaml.<timestamp>` |
| Whisper timeout | `audio.chunk_size: 180 → 120` | `config_backups/config.yaml.<timestamp>` |
| PyAnnote fail | `audio.diarization.device: cuda → cpu` | `config_backups/config.yaml.<timestamp>` |
| Model not found | `audio.model: large-v3 → medium` | `config_backups/config.yaml.<timestamp>` |

**Usage:**
```python
from agents.config_healer import ConfigHealer
from lib.llm_client import LLMClient

healer = ConfigHealer(llm_client=LLMClient())

# Apply healing rule
result = healer.heal_error(
    error_message="CUDA out of memory in vision step",
    config_overrides={"vision.batch_size": 16}
)

# Rollback if needed
healer.rollback_to_backup("config.yaml.2025-12-15_14-30-45")
```

**Safety Features:**
- All modifications backed up to `<GOODQ_DATA_ROOT>\GoodQ_Data\config_backups/`
- Versioned backups with timestamps
- Rollback capability
- Validation before applying

---

### 3. Self-Healing Monitor (`agents/self_healing_monitor.py`)

**Role:** Real-time pipeline health tracking

**Responsibilities:**
- Continuously monitor pipeline logs
- Match errors to known patterns
- Trigger recovery actions automatically
- Track healing history
- Alert on critical failures

**Error Patterns Monitored:**

| Pattern | Keywords | Action |
|---------|----------|--------|
| Timeout | `timeout`, `timed out` | Retry with backoff |
| Memory Error | `out of memory`, `OOM` | Reduce batch size |
| Model Missing | `model not found` | Download model |
| CUDA Error | `CUDA`, `GPU`, `device-side assert` | Switch to CPU |
| Empty Result | `no scenes detected` | Adjust thresholds |
| File Missing | `file not found` | Skip and continue |

**Usage:**
```python
from agents.self_healing_monitor import SelfHealingMonitor

monitor = SelfHealingMonitor()

# Start async monitoring (runs in background)
await monitor.monitor_and_heal(check_interval=60)

# Check history
history = monitor.healing_history
```

**Configuration:**
```yaml
# config.yaml
self_healing:
  check_interval: 60  # seconds
  auto_apply_fixes: true
  alert_on_critical: true
```

---

### 4. Watchdog Agent Integration (`agents/watchdog_agent_integration.py`)

**Role:** File system monitoring → ingestion trigger

**Responsibilities:**
- Monitor `<GOODQ_DATA_ROOT>\incoming\` for new videos
- Trigger ingestion pipeline automatically
- Log all file events
- Handle multiple simultaneous files
- Prevent duplicate processing

**Usage:**
```python
# Via CLI (preferred)
python -m cli.watchdog --input-dir "<GOODQ_DATA_ROOT>\incoming"

# Programmatic
from agents.watchdog_agent_integration import WatchdogAgent

agent = WatchdogAgent(watch_dir="<GOODQ_DATA_ROOT>\incoming")
agent.start()
```

**Database:**
- `<GOODQ_DATA_ROOT>\GoodQ_Data\agent_checkpoints\watchdog_events.db`
  - Tracks processed files
  - Prevents duplicates
  - Logs all events

**See:** [Watchdog System Documentation](../systems/WATCHDOG_SYSTEM.md)

---

### 5. Pipeline Integration (`agents/pipeline_integration.py`)

**Role:** Hook agents into ingestion flow

**Responsibilities:**
- Inject agent monitoring into `cli/run_ingestion.py`
- Wrap step execution with error capture
- Forward errors to Control Agent
- Track step timing and GPU usage
- Enable/disable agent features

**Implementation:**
```python
# In cli/run_ingestion.py
from agents.pipeline_integration import with_agent_monitoring

@with_agent_monitoring
def process_scene(scene_data, cfg):
    # Normal processing
    return result
```

**Features:**
- Non-invasive: Works with existing code
- Optional: Can be disabled via config
- Performant: Minimal overhead (<5ms per step)

---

### 6. LLM Agent (`agents/llm_agent.py`)

**Role:** Natural language reasoning and diagnosis

**Status:** 🔄 Partial (integrated but not fully utilized)

**Responsibilities:**
- Analyze complex error messages
- Suggest novel recovery approaches
- Generate human-readable diagnostic reports
- Answer user questions about pipeline state

**LLM Fallback Chain:**
1. **vLLM (WSL2)** - `Qwen/Qwen2.5-14B-Instruct` (primary)
2. **Ollama (local)** - `llama3:8b` (fallback)
3. **OpenAI API** - `gpt-4` (cloud fallback, requires key)

**Usage:**
```python
from lib.llm_client import LLMClient

llm = LLMClient()

# Analyze error
diagnosis = llm.chat(
    messages=[{
        "role": "user",
        "content": f"Diagnose this error: {error_message}\nContext: {context}"
    }]
)
```

**See:** [LLM Integration Guide](../guides/llm/LLM_CLIENT_GUIDE.md)

---

### 7. Recovery Strategies (`agents/recovery_strategies.py`)

**Role:** Knowledge base of error patterns and fixes

**Responsibilities:**
- Store error patterns with regex matching
- Track recovery success rates
- Learn optimal strategies from history
- Seed initial patterns from documentation
- Update patterns based on outcomes

**Database Schema:**
```sql
-- recovery_history
CREATE TABLE recovery_history (
    timestamp TEXT,
    error_type TEXT,
    strategy_applied TEXT,
    outcome TEXT,
    success BOOLEAN,
    duration_seconds REAL,
    gpu_usage_mb INTEGER
);

-- error_patterns
CREATE TABLE error_patterns (
    pattern_name TEXT UNIQUE,
    error_regex TEXT,
    recommended_strategy TEXT,
    success_rate REAL,
    total_attempts INTEGER
);
```

**Usage:**
```python
from agents.recovery_strategies import RecoveryStrategies

strategies = RecoveryStrategies()

# Find best strategy for error
strategy = strategies.find_best_strategy(
    error_message="CUDA out of memory",
    step_name="image_embed_clip"
)

# Record outcome
strategies.record_attempt(
    error_type="cuda_oom",
    strategy_applied="reduce_batch_size",
    success=True,
    duration_seconds=37.2
)

# Get statistics
stats = strategies.get_statistics()
```

---

### 8. Recovery Database (`agents/recovery_db.py`)

**Role:** Persistent storage for failure tracking

**Responsibilities:**
- Store all failures with full context
- Track all recovery attempts
- Identify success patterns
- Provide query interface for analysis

**Tables:**
- `failures` - Complete failure records
- `recovery_attempts` - Individual recovery tries
- `success_patterns` - Known working solutions

**Usage:**
```python
from agents.recovery_db import RecoveryDatabase

db = RecoveryDatabase()

# Log failure
failure_id = db.log_failure(
    step_name="audio_transcription",
    error_type="RuntimeError",
    error_message="Whisper model crashed",
    context={"gpu_usage": 15800, "duration": 180}
)

# Log recovery attempt
db.log_recovery_attempt(
    failure_id=failure_id,
    strategy="downgrade_model",
    outcome="success",
    execution_time_ms=45200
)
```

---

### 9. Base Agent (`agents/base_agent.py`)

**Role:** Abstract base class for all agents

**Purpose:** Provides common functionality:
- Configuration loading
- Logging setup
- Database connections
- Error handling patterns
- Lifecycle management

**Usage:**
```python
from agents.base_agent import BaseAgent

class MyCustomAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="MyCustomAgent")
    
    def execute(self, **kwargs):
        self.logger.info("Executing...")
        # Custom logic
```

---

## Agent Communication

Agents share knowledge through:

1. **SQLite Databases**
   - `control_memory.db` - Control Agent learning
   - `recovery.db` - Failure tracking
   - `watchdog_events.db` - File processing history

2. **Shared Configuration**
   - `config.yaml` - System-wide settings
   - `.env.local` - Secrets and API keys

3. **Log Files**
   - `logs/ingestion_*.log` - Pipeline execution
   - `logs/control_agent.log` - Agent activities

4. **File System Signals**
   - `processing/` - Active work-in-progress
   - `processed/` - Completed videos
   - `failed/` - Failed ingestion attempts

---

## Deployment

### Enable All Agents

In `config.yaml`:
```yaml
control_agent:
  enabled: true
  auto_heal: true

watchdog:
  enabled: true
  watch_dirs:
    - "<GOODQ_DATA_ROOT>\incoming"

self_healing:
  enabled: true
  check_interval: 60
```

### Disable Agents

Set `enabled: false` or use CLI flags:
```powershell
# Run without control agent
python -m cli.run_ingestion --input-dir ./inbox --no-agent

# Run watchdog without auto-heal
python -m cli.watchdog --input-dir ./inbox --no-heal
```

---

## Testing

### Test Control Agent
```powershell
python scripts/test_recovery_system.py
```

### Test Config Healing
```powershell
python scripts/test_phase3_healing.py
```

### Test Pipeline Integration
```powershell
python scripts/test_phase2_integration.py
```

### Verify All Agents
```powershell
python -m cli.diagnostic --check-agents
```

---

## Monitoring

### Agent Status
```powershell
# Check if agents are running
rg "CONTROL AGENT\|Self-Healing\|Watchdog" logs/
```

### View Learning Statistics
```python
from agents.control_agent import ControlAgent

agent = ControlAgent()
stats = agent.get_learning_statistics()

print(f"Total errors seen: {stats['total_errors']}")
print(f"Auto-heal success rate: {stats['overall_success_rate']}%")
```

### Query Recovery Database
```powershell
sqlite3 "<GOODQ_DATA_ROOT>\GoodQ_Data\recovery.db" "SELECT * FROM recovery_history ORDER BY timestamp DESC LIMIT 10;"
```

---

## Performance Impact

| Agent | CPU Overhead | Memory Overhead | GPU Impact |
|-------|--------------|-----------------|------------|
| Control Agent | <2% | ~50MB | None |
| Config Healer | <0.5% | ~20MB | None |
| Self-Healing Monitor | <1% | ~30MB | None |
| Watchdog | <0.5% | ~15MB | None |
| LLM Agent | 5-10% (when active) | ~500MB | ~2GB VRAM |

**Total Overhead:** <5% CPU, <150MB RAM when idle

---

## Future Roadmap

### Planned Agents

1. **Orchestrator Agent** - Multi-agent task coordination
2. **Quality Assurance Agent** - Validate output quality
3. **Resource Optimizer Agent** - GPU/CPU load balancing
4. **Knowledge Graph Agent** - Entity resolution and graph maintenance
5. **User Interaction Agent** - Natural language interface

### Planned Features

- Multi-agent collaboration protocols
- Distributed agent deployment (Windows + WSL2)
- Agent-to-agent direct communication
- Reinforcement learning for recovery strategies
- Predictive failure detection

---

## Related Documentation

- **[Control Agent Guide](../CONTROL_AGENT.md)** - Detailed Control Agent documentation
- **[Error Handling & Recovery](../systems/ERROR_HANDLING_RECOVERY.md)** - Recovery system architecture
- **[Watchdog System](../systems/WATCHDOG_SYSTEM.md)** - Automated file monitoring
- **[Phase 3 Self-Healing](../archive/phases/PHASE3_SELF_HEALING.md)** - Implementation history
- **[LLM Integration](../guides/llm/LLM_CLIENT_GUIDE.md)** - LLM agent setup

---

## Troubleshooting

### Agents not responding?

1. Check enabled status:
   ```yaml
   control_agent:
     enabled: true
   ```

2. Verify databases exist:
   ```powershell
   ls <GOODQ_DATA_ROOT>\GoodQ_Data\control_memory.db
   ls <GOODQ_DATA_ROOT>\GoodQ_Data\recovery.db
   ```

3. Check logs:
   ```powershell
   rg "ERROR" logs/control_agent.log
   ```

### High CPU usage from agents?

- Increase `check_interval` for Self-Healing Monitor
- Disable LLM Agent if not needed
- Set `auto_heal: false` for manual recovery

### Want to reset agent memory?

```powershell
# Backup first!
Copy-Item "<GOODQ_DATA_ROOT>\GoodQ_Data\control_memory.db" "<GOODQ_DATA_ROOT>\GoodQ_Data\control_memory.db.backup"

# Reset
Remove-Item "<GOODQ_DATA_ROOT>\GoodQ_Data\control_memory.db"

# Restart pipeline - database will be recreated
```

---

**The GoodQ4All agent system is designed to operate autonomously, learning optimal behaviors over time and adapting to your specific hardware and workload patterns.**
