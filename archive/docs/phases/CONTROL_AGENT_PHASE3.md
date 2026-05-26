# Control Agent Phase 3: Historical Live Integration Plan
> ⚠ Historical planning document — describes a 2025 experimental integration path and contains legacy path references.

## Current Runtime Truth

- The canonical file monitor is `cli/watchdog.py`, not `agents/watchdog_agent_integration.py`.
- Default `cli/watchdog.py` and `cli/run_ingestion.py` flows persist `disabled_no_llm_client` unless an `llm_client` is explicitly injected.
- Direct WSL startup commands using `~/vllm_server/scripts/start_llama1b.sh` are obsolete.
- For current behavior, trust `docs/CONTROL_AGENT.md`, `docs/systems/WATCHDOG_SYSTEM.md`, and `docs/CLI-REFERENCE.md`.

## 🎯 Overview

This document captures a Phase 3 integration plan for direct AI Control Agent orchestration. It is preserved as historical reference, not as the current default runtime contract.

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     File Monitoring Layer                     │
│                     (cli/watchdog.py)                        │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                   🤖 Control Agent Layer                      │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │   Error    │  │  Diagnosis   │  │   Recommendations  │  │
│  │  Detection │→ │   Engine     │→ │   & Auto-Healing   │  │
│  └────────────┘  └──────────────┘  └────────────────────┘  │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                  Ingestion Pipeline Steps                    │
│  Scene Detection → Image Analysis → Audio Processing         │
└──────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                   LLM Service Layer (WSL)                     │
│  vLLM (Port 38005) → Ollama (Port 31434) → LMStudio (1234)   │
└──────────────────────────────────────────────────────────────┘
```

## ✨ Features

### 1. **Real-Time Monitoring**
- Hooks into file detection, processing start, and completion
- Tracks all errors and exceptions
- Records performance metrics (duration, memory usage, GPU stats)

### 2. **AI-Powered Diagnosis**
- Analyzes errors using local LLM (Llama-3.2-1B at 178 tok/s)
- Identifies root causes from stack traces and context
- Suggests concrete remediation steps

### 3. **Self-Healing Capabilities**
- Automatic retry with adjusted parameters
- Dynamic config modifications based on AI recommendations
- GPU memory management (reduce batch size, switch models)
- Fallback strategies (CPU mode, alternative algorithms)

### 4. **Learning & Evolution**
- Stores every error + diagnosis + outcome in SQLite
- Builds a corpus of successful recovery strategies
- Uses past solutions to speed up future diagnostics

### 5. **Graceful Degradation**
- Pipeline works with or without Control Agent
- Automatic fallback if LLM services are unavailable
- No single point of failure

## 📋 Integration Points

### Watchdog Monitor (`cli/watchdog.py`)

The Control Agent is integrated at these key points:

1. **Initialization**
   ```python
   if CONTROL_AGENT_AVAILABLE:
       self.control_agent = ControlAgent()
   ```

2. **File Detection**
   ```python
   agent.on_file_detected(filename, file_type, size)
   ```

3. **Processing Start**
   ```python
   agent.on_processing_start(filename, file_type)
   ```

4. **Error Handling**
   ```python
   diagnosis = agent.analyze_error(error_msg, context)
   logger.info(f"🤖 AI Diagnosis: {diagnosis['diagnosis']}")
   ```

5. **Processing Complete**
   ```python
   agent.on_processing_complete(filename, success, error)
   ```

## 🚀 Usage

### Starting the Pipeline with Control Agent

```bash
# Ensure the current systemd-backed vLLM service path is available
scripts/start_vllm_servers.bat

# Start the ingestion watchdog
cd <project_root>
python -m cli.watchdog
```

You should see:
```
2025-11-16 02:30:00 [INFO] 🤖 Control Agent initialized - AI orchestration enabled
2025-11-16 02:30:00 [INFO] Watching directory: <project_root>\import_inbox
```

### Dropping a File for Processing

```bash
# Copy a test video to the inbox
copy "<project_root>\sample_video.mp4" "<project_root>\import_inbox\"
```

Watch the AI Control Agent in action:
```
2025-11-16 02:30:15 [INFO] New file detected: test_video.mp4
2025-11-16 02:30:18 [INFO] File stable: test_video.mp4 (125000000 bytes)
2025-11-16 02:30:18 [INFO] Queued for processing: test_video.mp4
2025-11-16 02:30:20 [INFO] Processing video: test_video.mp4
2025-11-16 02:35:42 [ERROR] Processing failed: CUDA out of memory
2025-11-16 02:35:45 [INFO] 🤖 AI Diagnosis: GPU memory exhaustion detected. The Whisper model is attempting to allocate 2.5GB but only 1.2GB is available. Recommend switching to whisper-base (smaller) or enabling CPU fallback.
2025-11-16 02:35:45 [INFO] 🤖 AI Recommendation: retry_with_changes - Reduce batch_size from 16 to 8, or use whisper-base instead of whisper-medium
```

### Viewing Reports

```bash
# Generate comprehensive report
python scripts\run_control_agent.py

# View specific diagnostics
python scripts\run_control_agent.py --errors-only
```

## 🧪 Testing

The standalone `scripts/test_control_agent_phase3.py` harness has been retired.
It depended on the old direct-orchestration assumptions from this historical
phase plan and no longer reflects the canonical runtime contract.

For current behavior:
- use `python -m cli.watchdog` for the canonical watcher
- use [CONTROL_AGENT.md](../../CONTROL_AGENT.md) for the live Control Agent contract

## 📊 Performance Impact

- **Control Agent Overhead**: ~50-200ms per event (file detection, error analysis)
- **AI Diagnosis Time**: ~500-2000ms (depending on error complexity)
- **Memory Footprint**: +50MB (Control Agent + memory database)
- **LLM Service**: Already running, no additional startup cost

**Net Impact**: Minimal (<1% of total pipeline time) with massive benefits in reliability and self-healing.

## 🔧 Configuration

### Enabling/Disabling Control Agent

The Control Agent is automatically enabled if available. To disable:

```python
# In cli/watchdog.py, adjust:
CONTROL_AGENT_AVAILABLE = False
```

### LLM Service Configuration

Control Agent uses the LLM client with automatic fallback:

1. **Primary**: vLLM Llama-3.2-1B (localhost:38005) - 178 tok/s
2. **Fallback**: Ollama Phi-4 (localhost:31434) - 70 tok/s
3. **Last Resort**: LMStudio (localhost:1234)

No configuration needed - it auto-discovers available services.

## 🎯 Next Steps

### Phase 4: Advanced Self-Healing
- Automatic config patching
- Multi-strategy retry logic
- Predictive failure prevention

### Phase 5: Reinforcement Learning
- Fine-tune local model on successful recoveries
- Build domain-specific diagnostic capabilities
- Evolve recovery strategies over time

## 📚 Related Documentation

- [Control Agent Phase 1](./CONTROL_AGENT_PHASE1.md) - Basic monitoring and reporting
- [Control Agent Phase 2](../../archive/reports/phase_reports/CONTROL_AGENT_PHASE2_COMPLETE.md) - Memory and diagnostics
- [LLM Client](../llm/LLM_CLIENT_GUIDE.md) - Multi-service LLM integration
- [vLLM Setup](../llm/VLLM_SYSTEMD_SETUP.md) - GPU-accelerated inference

## 🤝 Contributing

The Control Agent is designed to be extensible. To add custom recovery strategies:

1. Create a new method in `agents/control_agent.py`
2. Register it in the `recovery_strategies` dict
3. Validate against the canonical watchdog and Control Agent docs
4. Submit a PR with examples

---

**Status**: ✅ Production Ready  
**Last Updated**: 2025-11-16  
**Version**: 1.0.0
<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_ARCHIVED_ON: 2026-03-20 -->
<!-- ARCHIVE / NON-CANONICAL / DO NOT COPY PATHS -->
