# GoodQ Pipeline Flow Diagrams

**Last Updated:** December 15, 2025  
**Status:** ✅ Production Verified

## 📊 Visual Architecture Reference

This document contains ASCII and Mermaid diagrams for the GoodQ pipeline architecture. View these diagrams in a Markdown-compatible viewer or use Mermaid Live Editor.

**Evidence Source:** Forensic code analysis of `cli/run_ingestion.py`, verified active processing logs (Dec 14-15, 2025)

---

## 🎬 Complete Pipeline Flow (Current Production)

```mermaid
graph TD
    A[Input Video] --> B{Video Hash Check}
    B -->|Exists| C[Load Scene Manifest]
    B -->|New| D[Scene Detection PySceneDetect]
    D --> E[Create Scene Manifest]
    
    C --> F[Process Scenes]
    E --> F
    
    F --> G{For Each Scene}
    
    G --> H[Visual Pipeline]
    G --> I[Audio Pipeline WSL2]
    
    H --> H1[Extract Keyframe]
    H1 --> H2[OCR Tesseract]
    H1 --> H3[Caption BLIP]
    H1 --> H4[Object Detect YOLO]
    H1 --> H5[Face Embed]
    H1 --> H6[CLIP Embed]
    H1 --> H7[DINO Embed]
    H1 --> H8[Tagger WD14]
    
    I --> I1[Extract Audio Chunk]
    I1 --> I2[audio_unified_wsl2]
    I2 --> I3[Transcription Whisper]
    I2 --> I4[Diarization Pyannote]
    I2 --> I5[Emotion Detection]
    I2 --> I6[Audio Embeddings]
    I1 --> I7[Metadata]
    I1 --> I8[CLAP Embed]
    
    H2 --> J[Entity Extraction]
    H3 --> J
    H4 --> J
    I3 --> J
    
    J --> K[Cross-Modal Resolution]
    K --> L[Knowledge Graph Update]
    
    L --> M[Memory Storage]
    H5 --> M
    H6 --> M
    H7 --> M
    I6 --> M
    I8 --> M
    
    M --> N[SQLite memory.db]
    M --> O[SQLite knowledge_graph.db]
    M --> P[Qdrant Vectors]
    
    N --> Q[Query & Retrieval]
    O --> Q
    P --> Q
```

---

## 🔄 Deduplication Flow

```mermaid
graph TD
    A[Video Input] --> B[Compute Video Hash SHA256]
    B --> C{Check Memory DB}
    
    C -->|Hash Found| D[Load Existing Scenes]
    C -->|Hash Not Found| E[Run Scene Detection]
    
    E --> F[Generate Scene Manifests]
    F --> G[Store Video Hash + Manifests]
    
    D --> H{For Each Scene}
    G --> H
    
    H --> I[Compute Scene Hash]
    I --> J{scene_has_materialized?}
    
    J -->|Yes| K[Log status=skipped]
    J -->|No| L[Process Scene]
    
    K --> M[Load Cached Artifacts]
    L --> N[Generate New Artifacts]
    N --> O[register_scene_bundle]
    
    M --> P[Continue Pipeline]
    O --> P
    
    P --> Q{More Scenes?}
    Q -->|Yes| H
    Q -->|No| R[Complete]
```

---

## 🖼️ Visual Pipeline Detail (Production)

```mermaid
flowchart LR
    A[Keyframe JPG] --> B[OCR Tesseract]
    A --> C[Caption BLIP]
    A --> D[Object Detect YOLO]
    A --> E[Face Embed]
    A --> F[CLIP Embed]
    A --> G[DINO Embed]
    A --> H[Tagger WD14]
    
    B --> I[Text Output]
    C --> I
    D --> J[objects field]
    E --> K[Face Vectors 512d]
    F --> L[CLIP Vectors 512d]
    G --> M[DINO Vectors 768d]
    H --> N[Aesthetic Tags]
    
    I --> O[Entity Extractor]
    J --> O
    
    O --> P[Entities List]
    
    P --> Q[Knowledge Graph]
    K --> R[Qdrant]
    L --> R
    M --> R
    J --> S[memory.db scene_data]
    N --> S
```

**Artifact Locations (Verified Dec 15, 2025):**
- Keyframes: `<project_root>\logs\scene_ingest\<video_name>\video\scene_XXXX.jpg`
- Stored in: `memory.db` (scene_bundles table) + Qdrant collections

---

## 🎵 Audio Pipeline Detail (WSL2 Unified - Production)

```mermaid
flowchart TD
    A[Scene Audio WAV] --> B[WSL2: audio_unified_wsl2]
    
    B --> C[Whisper large-v3]
    B --> D[Pyannote 3.1 Diarization]
    B --> E[Silero VAD]
    B --> F[Emotion Wav2Vec2]
    
    C --> G[Transcript + Timestamps]
    D --> H[Speaker Segments]
    E --> I[Voice Activity]
    F --> J[8-class Emotion]
    
    G --> K[result.json]
    H --> K
    I --> K
    J --> K
    
    K --> L[Embeddings 768d]
    K --> M[Audio Features]
    
    A --> N[Windows: CLAP Embed]
    
    L --> O[Qdrant Audio]
    N --> O
    
    G --> P[Entity Extractor]
    P --> Q[Knowledge Graph]
    
    K --> R[memory.db scene_data]
```

**Artifact Locations (Verified Dec 15, 2025):**
- Audio chunks: `<project_root>\logs\scene_ingest\<video_name>\audio\scene_XXXX.wav`
- WSL2 output: `\\wsl.localhost\Ubuntu\home\joesdomingo\goodq_audio\output\result.json`
- GPU: RTX 4070 Ti SUPER 16GB, CUDA 12.8
- Models loaded: Whisper medium (service) / large-v3 (direct), Pyannote 3.1, Silero VAD, Wav2Vec2 emotion

---

## 💾 Memory Layer Architecture (Production)

```mermaid
graph TB
    subgraph "Persistent Storage"
        A[memory.db] --> A1[scenes table]
        A --> A2[assets table]
        A --> A3[scene_bundles table]
        A --> A4[video_metadata table]
        
        B[knowledge_graph.db] --> B1[entities table]
        B --> B2[relationships table]
        B --> B3[entity_mentions table]
        B --> B4[cross_references table]
        
        C[Qdrant Collections] --> C1[text_embeddings]
        C --> C2[clip_embeddings]
        C --> C3[dino_embeddings]
        C --> C4[audio_embeddings]
    end
    
    subgraph "Query Layer"
        D[Semantic Search] --> C1
        D --> C2
        D --> C3
        D --> C4
        
        E[Metadata Query] --> A1
        E --> A2
        E --> A3
        
        F[Graph Traversal] --> B1
        F --> B2
        F --> B3
        
        G[Cross-Modal] --> A
        G --> B
        G --> C
    end
    
    C1 -.payload.scene_id.- A1
    C2 -.payload.scene_id.- A1
    C3 -.payload.scene_id.- A1
    C4 -.payload.scene_id.- A1
    B3 -.scene_id.- A1
```

**Database Locations (Stitching-Era Baseline):**
- memory.db: `<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\memory.db`
- knowledge_graph.db: `<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\knowledge_graph.db`
- Qdrant: `localhost:6333` (Windows service, no Docker)
- Vector dimensions: text=384d, CLIP=512d, DINO=768d, audio=512d

---

## 🏗️ Environment Isolation

```mermaid
graph TD
    subgraph "Base System"
        A[Miniconda Python 3.13]
    end
    
    subgraph "Isolated Environments"
        B1[goodq_image_caption Python 3.10]
        B2[goodq_object_detect Python 3.10]
        B3[goodq_audio_transcribe Python 3.10]
        B4[goodq_audio_emotion Python 3.10]
        B5[goodq_text_embed Python 3.10]
        B6[...18 more envs...]
    end
    
    A -.creates.- B1
    A -.creates.- B2
    A -.creates.- B3
    A -.creates.- B4
    A -.creates.- B5
    A -.creates.- B6
    
    B1 --> C1[torch 2.3.1 CUDA]
    B2 --> C2[ultralytics CUDA]
    B3 --> C3[faster-whisper CUDA]
    B4 --> C4[transformers CUDA]
    B5 --> C5[sentence-transformers CPU]
    
    B1 -.pth link.- D[<project_root>/ goodq4all]
    B2 -.pth link.- D
    B3 -.pth link.- D
    B4 -.pth link.- D
    B5 -.pth link.- D
    
    style B1 fill:#90EE90
    style B2 fill:#90EE90
    style B3 fill:#90EE90
    style B4 fill:#90EE90
    style B5 fill:#ADD8E6
```

---

## ⚡ Performance: First Run vs Deduplication

```
First Run (158 seconds)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Scene Detection     ████████████ 12s
Image OCR           ██████ 6s (x2 scenes)
Image Caption       ███████████████ 14s (x2 scenes)
Object Detection    ████████████ 12s (x2 scenes)
Face Embedding      ████████ 8s (x2 scenes)
CLIP Embedding      ██████████ 10s (x2 scenes)
DINO Embedding      ██████████ 10s (x2 scenes)
Audio Metadata      ████ 4s
Audio Diarization   ██████████████████ 18s
Audio Transcription █████████████████████████ 25s
Speech Emotion      ██████ 6s
CLAP Embedding      ██████████ 10s
Text Processing     ███████ 7s
NER Tagging         ████████ 8s
Memory Integration  ████████ 8s

Second Run (38 seconds - 76% faster!)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Scene Detection     (skipped - dedupe)
Image OCR           ███ 3s (partial)
Image Caption       ███████ 7s (partial)
Object Detection    ██████ 6s (partial)
Face Embedding      (skipped - dedupe)
CLIP Embedding      (skipped - dedupe)
DINO Embedding      (skipped - dedupe)
Audio Metadata      (skipped - dedupe)
Audio Diarization   (skipped - dedupe)
Audio Transcription (skipped - dedupe)
Speech Emotion      (skipped - dedupe)
CLAP Embedding      (skipped - dedupe)
Text Processing     ███ 3s (partial)
NER Tagging         ████ 4s (partial)
Memory Integration  ██████ 6s
```

---

## 🔐 Data Security Model

```mermaid
graph TD
    A[User Data] --> B{Privacy Boundary}
    
    B --> C[Local Processing Only]
    C --> D[GPU/CPU on <project_root> drive]
    
    B -.Optional.- E[External APIs]
    E -.User Choice.- F[OpenAI GPT]
    E -.User Choice.- G[ElevenLabs TTS]
    
    D --> H[Local Storage]
    H --> I[<GOODQ_DATA_ROOT>/GoodQ_Data (See LEGACY_PATHS_DEPRECATED.md)/]
    H --> J[<GOODQ_DATA_ROOT>/models/]
    
    I --> K[SQLite Encrypted?]
    I --> L[FAISS Indices]
    I --> M[Step Logs]
    
    K --> N[Backup to NAS]
    L --> N
    M --> N
    
    N --> O[<drive>:/ UGREEN NAS]
    O -.Optional.- P[GPG Encryption]
    
    style C fill:#90EE90
    style H fill:#90EE90
    style E fill:#FFD700
    style F fill:#FFD700
    style G fill:#FFD700
```

---

## 📊 Scalability Paths

```mermaid
graph TB
    subgraph "Current Single Machine"
        A1[1x RTX 4070 Ti SUPER]
        A2[64GB RAM]
        A3[2x 4TB NVMe]
        A4[44TB NAS]
    end
    
    subgraph "Vertical Scaling Path"
        B1[1x RTX 6000 Ada 48GB]
        B2[128GB RAM]
        B3[4x 4TB NVMe RAID]
        B4[100TB NAS 10Gb]
    end
    
    subgraph "Horizontal Scaling Path"
        C1[4x GPUs Multi-Node]
        C2[Ray/Dask Cluster]
        C3[Shared NAS Storage]
        C4[Redis Coordinator]
    end
    
    subgraph "Index Scaling"
        D1[FAISS IVF-PQ]
        D2[100M+ Vectors]
        D3[Quantization]
        D4[ANN Search]
    end
    
    A1 -.Upgrade.- B1
    A2 -.Upgrade.- B2
    A3 -.Upgrade.- B3
    A4 -.Upgrade.- B4
    
    B1 -.Distribute.- C1
    B2 -.Distribute.- C2
    B3 -.Distribute.- C3
    B4 -.Distribute.- C4
    
    A1 -.Optimize.- D1
    A2 -.Optimize.- D2
    A3 -.Optimize.- D3
    A4 -.Optimize.- D4
```

---

## 🔄 Orchestration Flow

```mermaid
sequenceDiagram
    participant U as User
    participant CLI as CLI Script
    participant ZM as legacy orchestration
    participant SR as Step Runner
    participant ENV as Conda Env
    participant MEM as Memory Layer
    
    U->>CLI: pwsh ingest_videos_lite.ps1
    CLI->>CLI: Sync .env.local
    CLI->>ZM: conda run -n goodq_core
    ZM->>ZM: Load run_ingestion.py
    
    loop For each video
        ZM->>ZM: Compute video hash
        ZM->>MEM: Check if processed
        alt Already processed
            MEM-->>ZM: Return cached scenes
            ZM->>ZM: Log status=skipped
        else New video
            ZM->>ZM: Run scene detection
            
            loop For each scene
                ZM->>SR: Execute step
                SR->>ENV: conda run -n goodq_<step>
                ENV->>ENV: Load model
                ENV->>ENV: Process input
                ENV-->>SR: Return result
                SR->>MEM: Store artifacts
                SR->>SR: Log to step_runs.jsonl
                SR-->>ZM: Complete
            end
        end
    end
    
    ZM-->>CLI: Pipeline complete
    CLI-->>U: Results saved
```

---

## 🎯 Use Case Flow: Video Search

```mermaid
graph LR
    A[User Query: Find scenes with dogs] --> B[Encode Query]
    B --> C[CLIP Text Encoder]
    C --> D[Query Vector 512d]
    
    D --> E[FAISS CLIP Index Search]
    E --> F[Top-K Similar Vectors]
    
    F --> G[ID Map Lookup]
    G --> H[Content Hashes]
    
    H --> I[SQLite Query]
    I --> J[Scene Metadata]
    
    J --> K[Return Results]
    K --> L[Scene IDs + Timestamps]
    K --> M[Object Labels]
    K --> N[Captions]
    K --> O[Video Paths]
    
    L --> P[Display to User]
    M --> P
    N --> P
    O --> P
```

---

## 📈 Monitoring Dashboard Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    GoodQ Command Center                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  GPU Status                    System Metrics                   │
│  ┌──────────────────┐          ┌──────────────────┐            │
│  │ RTX 4070 Ti SUPER│          │ CPU: 34%         │            │
│  │ Temp: 67°C       │          │ RAM: 28GB/64GB   │            │
│  │ Usage: 85%       │          │ Disk: 1.2TB/4TB  │            │
│  │ Memory: 12GB/16GB│          │ Network: 2.5Gbps │            │
│  └──────────────────┘          └──────────────────┘            │
│                                                                  │
│  Pipeline Status               Recent Steps                     │
│  ┌──────────────────┐          ┌──────────────────┐            │
│  │ Running: Yes     │          │ image_caption OK │            │
│  │ Video: sample.mp4│          │ object_detect OK │            │
│  │ Scene: 5/12      │          │ audio_diarize OK │            │
│  │ Progress: 42%    │          │ audio_emotion OK │            │
│  └──────────────────┘          └──────────────────┘            │
│                                                                  │
│  Memory Stats                  Logs Tail                        │
│  ┌──────────────────┐          ┌──────────────────┐            │
│  │ Scenes: 1,234    │          │ [21:06:53] CLAP  │            │
│  │ Text Vecs: 45K   │          │ [21:06:46] tagger│            │
│  │ Image Vecs: 23K  │          │ [21:06:44] emotion│           │
│  │ Audio Vecs: 8.5K │          │ [21:06:40] merge │            │
│  │ DB Size: 892MB   │          │ [21:06:20] whisper│           │
│  └──────────────────┘          └──────────────────┘            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

*Diagrams last updated: October 6, 2025*

**Note:** View these diagrams in:
- VS Code with Mermaid extension
- GitHub (native Mermaid rendering)
- [Mermaid Live Editor](https://mermaid.live)
- Any Markdown viewer with Mermaid support

