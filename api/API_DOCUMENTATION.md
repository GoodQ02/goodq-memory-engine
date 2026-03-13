# GoodQ4All Unified API Documentation

**Version:** 2.0  
**Base URL:** `http://localhost:30000`  
**Last Updated:** 2025-11-19

---

## 🎯 Overview

The GoodQ4All API is a unified FastAPI server that consolidates all system endpoints into a single, production-ready interface running on **port 30000**.

### Key Features

- ✅ **Single Port Architecture** - All endpoints on port 30000
- ✅ **Real-time Health Monitoring** - GPU, LLM, and system status
- ✅ **Processing Pipeline Status** - Video processing and scene analytics
- ✅ **LLM Chat Integration** - Multi-model chat with fallback
- ✅ **Command Center** - System control and diagnostics
- ✅ **Static File Serving** - UI/dashboard hosting
- ✅ **Optional CORS** - Disabled by default; localhost-only when explicitly enabled

---

## 🏗️ Architecture

```
Port 30000 (Unified API)
├── /                          → Main interface (index.html)
├── /dashboard.html            → Processing dashboard
├── /api/health/*              → Health monitoring
├── /api/processing/*          → Processing status
├── /api/chat/*                → LLM chat endpoints
├── /api/command-center        → System control
├── /api/gpu                   → GPU statistics
├── /api/wsl2-status           → WSL2 integration status
├── /api/pipeline-engines      → Pipeline engine status
└── /api/progress              → Overall system progress
```

---

## 📡 API Endpoints

### Health & Status

#### `GET /api/health/summary`
Get overall system health summary.

**Response:**
```json
{
  "status": "healthy|degraded|offline",
  "timestamp": "2025-11-19T04:30:00Z",
  "models": {
    "total": 2,
    "healthy": 2,
    "unhealthy": 0
  },
  "gpu": {
    "available": true,
    "utilization": 45.2,
    "memory_used_mb": 2048,
    "memory_total_mb": 8192
  },
  "services": {
    "vllm": "healthy",
    "ollama": "healthy",
    "wsl2": "active"
  }
}
```

#### `GET /api/health/models`
Get detailed health status for all LLM models.

**Response:**
```json
{
  "models": [
    {
      "name": "Llama-1B-Speed",
      "endpoint": "http://localhost:38005/v1",
      "status": "healthy",
      "response_time_ms": 10,
      "last_check": "2025-11-19T04:30:00Z"
    },
    {
      "name": "Phi4-Ollama",
      "endpoint": "http://localhost:31434/v1",
      "status": "healthy",
      "response_time_ms": 2,
      "last_check": "2025-11-19T04:30:00Z"
    }
  ],
  "summary": {
    "total": 2,
    "healthy": 2,
    "unhealthy": 0
  }
}
```

#### `GET /api/gpu`
Get real-time GPU statistics.

**Response:**
```json
{
  "available": true,
  "name": "NVIDIA GeForce RTX 3060",
  "driver_version": "546.01",
  "cuda_version": "12.3",
  "utilization_percent": 45.2,
  "memory": {
    "used_mb": 2048,
    "total_mb": 8192,
    "free_mb": 6144,
    "percent_used": 25.0
  },
  "temperature_c": 65,
  "power_draw_w": 120,
  "power_limit_w": 170
}
```

---

### Processing & Progress

#### `GET /api/processing/stats`
Get processing pipeline statistics.

**Response:**
```json
{
  "status": "active|idle|error",
  "current_video": {
    "name": "01. 1987 - 1988.mp4",
    "size_gb": 7.28,
    "current_step": "audio_diarize",
    "progress_percent": 45
  },
  "totals": {
    "videos_active": 1,
    "videos_completed": 12
  },
  "scenes": {
    "detected": 342,
    "frames_extracted": 1025,
    "audio_clips": 156
  },
  "processing_rate": {
    "scenes_per_minute": 2.5,
    "seconds_per_scene": 24
  },
  "timestamps": {
    "started_at": "2025-11-19T03:00:00Z",
    "updated_at": "2025-11-19T04:30:00Z"
  }
}
```

#### `GET /api/progress`
Get overall system progress.

**Response:**
```json
{
  "overall_progress": 65,
  "current_phase": "Processing Videos",
  "videos": {
    "total": 15,
    "completed": 12,
    "in_progress": 1,
    "pending": 2
  },
  "pipeline_steps": [
    {
      "name": "Scene Detection",
      "status": "completed",
      "progress": 100
    },
    {
      "name": "Audio Diarization",
      "status": "in_progress",
      "progress": 45
    },
    {
      "name": "Transcription",
      "status": "pending",
      "progress": 0
    }
  ]
}
```

---

### Chat & LLM

#### `POST /api/chat/control-agent`
Chat with the control agent (system diagnostics and help).

**Request:**
```json
{
  "message": "What is the system status?",
  "context": {}
}
```

**Response:**
```json
{
  "response": "System is operating normally. 2 LLM models are healthy, GPU utilization at 45%.",
  "model_used": "Llama-1B-Speed",
  "timestamp": "2025-11-19T04:30:00Z",
  "diagnostics": {
    "health": "good",
    "suggestions": []
  }
}
```

#### `POST /api/chat/memory-qa`
Chat with memory/knowledge base.

**Request:**
```json
{
  "query": "Tell me about the 1987 videos",
  "context": {
    "session_id": "user123"
  }
}
```

**Response:**
```json
{
  "answer": "Based on your video collection, 1987 includes...",
  "sources": [
    {
      "video": "01. 1987 - 1988.mp4",
      "timestamp": "00:12:34",
      "confidence": 0.92
    }
  ],
  "model_used": "Phi4-Ollama"
}
```

---

### Command Center

#### `GET /api/command-center`
Get command center status (pipeline engines, system controls).

**Response:**
```json
{
  "engines": {
    "vllm_llama1b": {
      "name": "vLLM Llama-1B",
      "category": "LLM Inference",
      "status": "ready",
      "gpu": true,
      "port": 38005,
      "description": "Llama 1B Speed model"
    },
    "ollama": {
      "name": "Ollama Phi4",
      "category": "LLM Inference",
      "status": "ready",
      "gpu": false,
      "port": 31434,
      "description": "Phi4 via Ollama"
    },
    "wsl_audio": {
      "name": "WSL2 Audio Processing",
      "category": "Audio Pipeline",
      "status": "ready",
      "gpu": true,
      "description": "Faster Whisper + PyAnnote"
    }
  },
  "controls": {
    "pipeline_running": true,
    "auto_ingest_enabled": true,
    "gpu_acceleration": true
  }
}
```

#### `POST /api/command-center/action`
Execute command center actions.

**Request:**
```json
{
  "action": "pause_pipeline|resume_pipeline|clear_cache|rebuild_index",
  "parameters": {}
}
```

**Response:**
```json
{
  "success": true,
  "action": "pause_pipeline",
  "message": "Pipeline paused successfully",
  "timestamp": "2025-11-19T04:30:00Z"
}
```

---

### WSL2 Integration

#### `GET /api/wsl2-status`
Get WSL2 integration status.

**Response:**
```json
{
  "available": true,
  "distribution": "Ubuntu-22.04",
  "services": {
    "vllm": {
      "status": "active",
      "port": 38005,
      "uptime": "2h 15m"
    },
    "audio_processing": {
      "status": "ready",
      "gpu_enabled": true
    }
  },
  "gpu": {
    "passthrough": true,
    "devices": ["NVIDIA GeForce RTX 3060"]
  }
}
```

#### `POST /api/wsl2/test-audio`
Test WSL2 audio processing.

**Request:**
```json
{
  "test_file": "path/to/audio.wav"
}
```

**Response:**
```json
{
  "success": true,
  "transcription": "Test audio transcription...",
  "speakers": 2,
  "duration_seconds": 12.5,
  "processing_time_ms": 450
}
```

---

### Pipeline Engines

#### `GET /api/pipeline-engines`
Get status of all pipeline engines.

**Response:**
```json
{
  "engines": [
    {
      "id": "vllm_llama1b",
      "name": "vLLM Llama-1B",
      "category": "LLM Inference",
      "status": "ready",
      "gpu": true,
      "metrics": {
        "requests_processed": 1523,
        "avg_response_time_ms": 45,
        "uptime_hours": 72
      }
    }
  ],
  "summary": {
    "total": 7,
    "ready": 7,
    "processing": 0,
    "error": 0
  }
}
```

---

## 🔒 Error Handling

All endpoints return consistent error responses:

```json
{
  "error": "Error message",
  "code": "ERROR_CODE",
  "timestamp": "2025-11-19T04:30:00Z",
  "request_id": "abc123"
}
```

### Common HTTP Status Codes

- `200` - Success
- `400` - Bad Request (invalid parameters)
- `404` - Not Found
- `500` - Internal Server Error
- `503` - Service Unavailable (system degraded)

---

## 🚀 Quick Start

### Start the API Server

```bash
cd <repo_root>
uvicorn api.main:app --host 127.0.0.1 --port 30000 --reload
```

### Test Endpoints

```bash
# Health check
curl http://localhost:30000/api/health/summary

# GPU status
curl http://localhost:30000/api/gpu

# Processing stats
curl http://localhost:30000/api/processing/stats
```

---

## 📦 Dependencies

The unified API requires:
- FastAPI
- Uvicorn
- Pydantic
- GPUtil (GPU monitoring)
- Requests (HTTP client)
- python-dotenv (configuration)

Install with:
```bash
pip install fastapi uvicorn pydantic gputil requests python-dotenv
```

---

## 🔧 Configuration

Environment variables (optional):

```bash
# API Configuration
GOODQ_API_HOST=127.0.0.1
GOODQ_API_PORT=30000

# LLM Endpoints
VLLM_ENDPOINT=http://localhost:38005/v1
OLLAMA_ENDPOINT=http://localhost:31434/v1

# WSL2
WSL_DISTRIBUTION=Ubuntu-22.04
```

Loopback is the safe default. Only set `GOODQ_API_HOST=0.0.0.0` when you
intentionally want LAN exposure on a trusted network.

---

## 📝 Changelog

### Version 2.0 (2025-11-19)
- ✅ Consolidated all APIs into single unified server
- ✅ Migrated from ports 5050/5001 to single port 30000
- ✅ Added comprehensive health monitoring
- ✅ Integrated LLM chat endpoints
- ✅ Added WSL2 status and testing
- ✅ Improved error handling and logging
- ✅ Added real-time GPU monitoring
- ✅ Deprecated separate health_status.py and processing_api.py

### Version 1.0 (2025-11-17)
- Initial multi-port API architecture

---

## 🐛 Troubleshooting

### API Server Won't Start

**Issue:** Port 30000 already in use  
**Solution:** 
```bash
# Find process using port 30000
netstat -ano | findstr :30000

# Kill process
taskkill /PID <PID> /F
```

### Models Show as Unhealthy

**Issue:** vLLM or Ollama not responding  
**Solution:**
```bash
# Check vLLM (WSL)
wsl -d Ubuntu-22.04 -- systemctl status vllm-llama1b

# Restart vLLM
wsl -d Ubuntu-22.04 -- sudo systemctl restart vllm-llama1b

# Check Ollama
curl http://localhost:31434/v1/models
```

### GPU Not Detected

**Issue:** GPU stats show unavailable  
**Solution:**
```bash
# Verify GPU drivers
nvidia-smi

# Check WSL GPU passthrough
wsl -- nvidia-smi
```

---

## 📞 Support

For issues or questions:
- Check logs: canonical runtime log directory (`cfg.paths.log_dir`)
- API logs: Console output from uvicorn
- System logs: Windows Event Viewer

---

**Made with ❤️ by the GoodQ4All Team**
