# 🎭 GoodQ4All

> **Transforming multimedia into deep emotional intelligence and human understanding**

GoodQ4All is an AI-powered multimedia analysis platform that goes beyond surface-level transcription to understand the *emotional fabric* of human communication. By combining GPU-accelerated audio processing, computer vision, and advanced NLP, we map the nuances of human expression—tone, sentiment, speaker dynamics, and context—into actionable insights.

---

## 🌟 What Makes GoodQ4All Special

### **Emotional Intelligence First**
Unlike traditional transcription tools, GoodQ4All analyzes:
- **Speaker emotion** and tonal patterns
- **Contextual relationships** between speakers, topics, and moments
- **Temporal dynamics** - how emotions evolve throughout conversations
- **Multi-modal understanding** - combining audio, visual, and text cues

### **GPU-Accelerated Processing**
- **5-10× faster** than CPU-based solutions
- **Real-time speaker diarization** with PyAnnote.audio
- **High-accuracy transcription** via Faster-Whisper (OpenAI Whisper optimized)
- **CUDA 12.8** acceleration on NVIDIA GPUs

### **Knowledge Graph Architecture**
Every conversation becomes a rich network of:
- **Entities** (people, places, concepts)
- **Relationships** (who spoke to whom, about what)
- **Temporal links** (conversation flow and evolution)
- **Emotional context** (sentiment, tone, intensity)

---

## 🚀 Quick Start

### One-Command Launch
```bash
# Windows - Double click or run:
L:\goodq4all\LAUNCH_GOODQ.bat

# Then select option 1 for complete system
```

**What starts:**
- 🚀 API Server (http://localhost:3000)
- 👁️ Watchdog (auto-processes files from import_inbox)
- 🎨 Web UI (opens automatically in your browser)

### Drop & Process
1. Drop any video/audio file into `import_inbox/`
2. System auto-detects and processes
3. View results in real-time at http://localhost:3000

**Supported formats:** MP4, MP3, WAV, AVI, MOV, FLAC, and more

---

## 💡 Use Cases

### 🎙️ **Interview & Podcast Analysis**
- Automatic speaker identification
- Emotional arc mapping
- Key topic extraction
- Conversation flow visualization

### 📹 **Video Content Understanding**
- Scene-by-scene breakdown
- Speaker dynamics and turn-taking
- Sentiment trends over time
- Multi-speaker conversation networks

### 🧠 **Research & Insights**
- Emotion pattern discovery
- Speaker relationship mapping
- Temporal trend analysis
- Cross-conversation knowledge linking

### 🎬 **Media Production**
- Automated content tagging
- Emotional beat detection
- Speaker highlight reels
- Contextual search across archives

---

## 🏗️ Architecture

```
┌─────────────────┐
│  Drop Files In  │
│  import_inbox/  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│       🔍 Watchdog Monitor           │
│   (Auto-detect & Queue Files)       │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│    🎬 Multi-Stage Pipeline          │
│  ┌──────────────────────────────┐   │
│  │ 1. Audio Extraction (FFmpeg) │   │
│  │ 2. GPU Transcription         │   │
│  │    (Faster-Whisper + CUDA)   │   │
│  │ 3. Speaker Diarization       │   │
│  │    (PyAnnote.audio)          │   │
│  │ 4. Emotion Analysis          │   │
│  │ 5. Entity Extraction         │   │
│  │ 6. Knowledge Graph Build     │   │
│  │ 7. Embeddings (FAISS)        │   │
│  └──────────────────────────────┘   │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│      💾 Unified Data Layer          │
│  • SQLite (structured data)         │
│  • FAISS (vector embeddings)        │
│  • Knowledge Graph (relationships)  │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│      🌐 REST API + WebSockets       │
│    (Real-time updates & queries)    │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│       🎨 Interactive Web UI         │
│  • Chat with your content           │
│  • Explore knowledge graphs         │
│  • Visualize emotion timelines      │
│  • Search semantically              │
└─────────────────────────────────────┘
```

---

## ✨ Features

### 🎯 **Core Processing**
- ✅ GPU-accelerated transcription (5-10× faster)
- ✅ Multi-speaker diarization with confidence scores
- ✅ Emotion & sentiment analysis per segment
- ✅ Automatic scene detection (smart chunking)
- ✅ Entity extraction (people, places, topics)
- ✅ Knowledge graph construction
- ✅ Vector embeddings for semantic search

### 🎨 **Web Interface**
- ✅ Real-time processing monitor
- ✅ Interactive knowledge graph visualization
- ✅ Emotion timeline charts
- ✅ Semantic search across all content
- ✅ Chat interface with LLM integration
- ✅ Multi-view analytics dashboard
- ✅ Command center with live logs

### 🔧 **System**
- ✅ Automatic file ingestion (watchdog)
- ✅ Process conflict detection
- ✅ Graceful error handling & recovery
- ✅ Progress tracking & reporting
- ✅ Multi-format support (video/audio/text)
- ✅ Deduplication & file management

---

## 🛠️ Technology Stack

### **Audio Processing (WSL2 + GPU)**
- **Faster-Whisper** - Optimized OpenAI Whisper with CTranslate2
- **PyAnnote.audio** - State-of-the-art speaker diarization
- **FFmpeg** - Audio/video extraction and conversion
- **CUDA 12.8 + cuDNN 9** - GPU acceleration
- **PyTorch 2.9** - Deep learning framework

### **Backend**
- **Python 3.12** - Core language
- **FastAPI** - High-performance REST API
- **SQLite** - Structured data storage
- **FAISS** - Vector similarity search
- **ZenML** - Pipeline orchestration
- **NetworkX** - Knowledge graph operations

### **Frontend**
- **Vanilla JavaScript** - No framework overhead
- **Chart.js** - Data visualization
- **D3.js** - Knowledge graph rendering
- **WebSockets** - Real-time updates

---

## 📦 Installation & Setup

### **Prerequisites**
- Windows 10/11 with WSL2
- NVIDIA GPU (RTX series recommended)
- CUDA 12.x drivers installed
- Python 3.10+

### **Installation**
```bash
# 1. Clone repository
git clone https://github.com/yourusername/goodq4all.git
cd goodq4all

# 2. Run installation
INSTALL.bat

# 3. Configure environment
copy .env.local.template .env.local
# Edit .env.local with your settings

# 4. Launch system
LAUNCH_GOODQ.bat
```

**Detailed setup:** See [INSTALL.md](INSTALL.md)

---

## 🎮 Usage

### **Master Launcher Options**
```
LAUNCH_GOODQ.bat provides:

1 - Launch Complete System (API + Watchdog + UI)
2 - Launch API Server Only
3 - Launch Watchdog Only  
4 - View System Status
5 - Stop All Services
6 - Exit
```

### **Processing Workflow**
1. **Start system:** `LAUNCH_GOODQ.bat` → Option 1
2. **Drop files:** Place media in `import_inbox/`
3. **Auto-process:** Watchdog detects and queues
4. **Monitor:** http://localhost:3000 (UI opens automatically)
5. **Explore:** View results in real-time as pipeline completes

### **Manual Processing**
```bash
# Process specific file
python scripts/process_media.py path/to/file.mp4

# Batch process directory
python scripts/batch_process.py path/to/directory/
```

---

## 📊 Web UI Features

### **💬 Chat Interface**
Ask questions about your processed content:
- "What emotions dominated this conversation?"
- "Who spoke the most about topic X?"
- "Show me moments of high tension"
- "Summarize the key discussion points"

### **🎬 Scenes Explorer**
- Browse processed scenes with metadata
- View transcripts with speaker labels
- See emotion scores per segment
- Jump to specific timestamps

### **🧠 Knowledge Graph**
- Interactive network visualization
- Entity relationship exploration
- Temporal flow analysis
- Filter by type, speaker, or topic

### **📈 Analytics Dashboard**
- Processing statistics
- Emotion distribution charts
- Speaker participation metrics
- Timeline visualizations

### **🎛️ Command Center**
- Live pipeline logs (auto-scrolling)
- Real-time progress tracking
- System health monitoring
- Process control (start/stop)

---

## 🗂️ Project Structure

```
goodq4all/
├── 🚀 LAUNCH_GOODQ.bat          # Main launcher (START HERE)
├── 📦 INSTALL.bat                # One-click installation
├── 🌐 index.html                 # Web UI entry point
├── 🔌 api_server.py              # REST API server
│
├── 📥 import_inbox/              # Drop files here for auto-processing
├── 💾 data/
│   ├── memory.db                # Main database
│   ├── knowledge_graph.db       # Relationship store
│   ├── faiss_indices/           # Vector embeddings
│   ├── processing/              # Active processing
│   └── processed/               # Completed files
│
├── 🔧 scripts/
│   ├── watchdog_ingest.py       # Auto-file detection
│   ├── process_media.py         # Manual processing
│   └── batch_process.py         # Bulk operations
│
├── 🎯 pipelines/                 # ZenML pipeline definitions
├── 🔨 steps/                     # Pipeline step implementations
├── 🤖 agents/                    # Agent configurations
├── 📊 web/                       # UI components & assets
├── 📚 docs/                      # Documentation
└── 🧪 tests/                     # Test suite
```

---

## 🔍 API Documentation

### **Key Endpoints**
```http
GET  /api/status              # System health & stats
GET  /api/scenes              # List all processed scenes
GET  /api/scene/{id}          # Scene details with segments
GET  /api/entities            # Extracted entities
GET  /api/knowledge-graph     # Full graph data
GET  /api/emotions/timeline   # Emotion trends over time
GET  /api/speakers            # Speaker statistics
POST /api/chat                # LLM chat interface
POST /api/search              # Semantic search
WS   /ws/progress             # Real-time progress updates
```

**Full API docs:** http://localhost:3000/docs (when server running)

---

## ⚙️ Configuration

### **Scene Detection**
```yaml
# config.yaml
visual_intel:
  scene_detection:
    min_scene_length: 300  # 5 minutes (prevents over-segmentation)
    threshold: 30.0         # Scene change sensitivity
```

### **Audio Processing**
```bash
# WSL2 environment
~/goodq_audio/scripts/process.sh
  --model=medium          # Whisper model size (tiny/base/small/medium/large)
  --no-diarization        # Skip speaker detection (faster)
```

### **LLM Integration**
```env
# .env.local
LLM_PROVIDER=lmstudio
LLM_API_BASE=http://localhost:1234/v1
LLM_MODEL=qwen/qwen3-vl-4b
```

---

## 🐛 Troubleshooting

### **"Watchdog already running"**
```bash
LAUNCH_GOODQ.bat → Option 5 (Stop All Services)
```

### **API Not Responding**
```bash
curl http://localhost:3000/api/status
# Check logs: logs/api_server.log
```

### **GPU Not Detected**
```bash
# In WSL2
nvidia-smi
python -c "import torch; print(torch.cuda.is_available())"
```

### **Audio Processing Fails**
```bash
# Check WSL2 audio environment
wsl ~/goodq_audio/scripts/test_gpu.sh
# Review logs: ~/goodq_audio/logs/
```

**Full troubleshooting guide:** [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

---

## 📈 Performance

### **GPU Acceleration Benefits**
- **Transcription:** 5-10× faster than CPU (RTX 4070 Ti SUPER)
- **Diarization:** 3-4× faster with GPU
- **Real-time factor:** Process 1hr audio in 6-10 minutes

### **Benchmarks**
| Task | CPU Time | GPU Time | Speedup |
|------|----------|----------|---------|
| 1hr transcription | ~60 min | ~8 min | 7.5× |
| Speaker diarization | ~20 min | ~5 min | 4× |
| Emotion analysis | ~5 min | ~2 min | 2.5× |

---

## 🤝 Contributing

We welcome contributions! Areas of focus:
- 🎯 Emotion detection models
- 🧠 Knowledge graph algorithms  
- 🎨 UI/UX improvements
- 📚 Documentation
- 🧪 Test coverage

**See:** [CONTRIBUTING.md](CONTRIBUTING.md)

---

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

Built with love using:
- [OpenAI Whisper](https://github.com/openai/whisper)
- [Faster-Whisper](https://github.com/guillaumekln/faster-whisper)
- [PyAnnote.audio](https://github.com/pyannote/pyannote-audio)
- [FastAPI](https://fastapi.tiangolo.com/)
- [ZenML](https://zenml.io/)
- [FAISS](https://github.com/facebookresearch/faiss)

---

## 📞 Contact & Support

- **Documentation:** [docs/](docs/)
- **Issues:** [GitHub Issues](https://github.com/yourusername/goodq4all/issues)
- **Discussions:** [GitHub Discussions](https://github.com/yourusername/goodq4all/discussions)

---

**🌟 Star this repo if GoodQ4All helps you understand human communication better!**

---

*Last Updated: November 15, 2025*  
*Version: 2.1.0*  
*Status: Production Ready ✅*
