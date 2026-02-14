# Control Agent Phase 3: Live Pipeline Integration
> ⚠ Historical planning document — contains legacy path references.

## 🎯 Overview

Phase 3 integrates the AI Control Agent directly into the GoodQ4All ingestion pipeline, enabling **real-time intelligent orchestration** with self-healing capabilities.

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     File Monitoring Layer                     │
│                  (watchdog_ingest.py)                        │
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

### Watchdog Monitor (`watchdog_ingest.py`)

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
# Ensure vLLM is running in WSL
wsl ~/vllm_server/scripts/start_llama1b.sh

# Start the ingestion watchdog
cd <project_root>
python scripts\watchdog_ingest.py
```

You should see:
```
2025-11-16 02:30:00 [INFO] 🤖 Control Agent initialized - AI orchestration enabled
2025-11-16 02:30:00 [INFO] Watching directory: <project_root>\import_inbox
```

### Dropping a File for Processing

```bash
# Copy a test video to the inbox
copy "C:\test_video.mp4" "<project_root>\import_inbox\"
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

```bash
# Run Phase 3 integration tests
python scripts\test_control_agent_phase3.py
```

Expected output:
```
🧪 PHASE 3 TEST: CONTROL AGENT PIPELINE INTEGRATION
================================================================================

📋 Test 1: Initialize Control Agent
✅ Control Agent initialized successfully
   - LLM Client: LLMClient
   - Memory Database: <project_root>\data\control_agent_memory.db

📋 Test 2: Test File Detection Callback
✅ File detection callback successful

📋 Test 3: Test Processing Start Callback
✅ Processing start callback successful

📋 Test 4: AI Error Diagnosis
✅ AI Diagnosis received:
   📊 Diagnosis: The error indicates that CUDA ran out of memory...
   💡 Root Cause: Insufficient GPU memory for the requested operation...
   🔧 Recommended Action: retry_with_changes
   ⚡ Confidence: high

📋 Test 5: Test Processing Completion Callback
✅ Success callback successful
✅ Failure callback successful

📋 Test 6: Generate Comprehensive Report
✅ Report generated successfully

📋 Test 7: Verify Watchdog Integration
✅ Watchdog has Control Agent integrated
   - Agent Type: ControlAgent

🎉 PHASE 3 INTEGRATION TEST COMPLETE!
```

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
# In watchdog_ingest.py, set:
CONTROL_AGENT_AVAILABLE = False
```

Or at runtime:
```bash
python scripts\watchdog_ingest.py --no-ai-control
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
3. Test with `test_control_agent_phase3.py`
4. Submit a PR with examples

---

**Status**: ✅ Production Ready  
**Last Updated**: 2025-11-16  
**Version**: 1.0.0

