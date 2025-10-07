# GoodQ Pipeline Flow Diagrams

## 📊 Visual Architecture Reference

This document contains ASCII and Mermaid diagrams for the GoodQ pipeline architecture. View these diagrams in a Markdown-compatible viewer or use Mermaid Live Editor.

---

## 🎬 Complete Pipeline Flow

```mermaid
graph TD
    A[Input Video] --> B{Video Hash Check}
    B -->|Exists| C[Load Scene Manifest]
    B -->|New| D[Scene Detection ffmpeg]
    D --> E[Create Scene Manifest]
    
    C --> F[Process Scenes]
    E --> F
    
    F --> G{For Each Scene}
    
    G --> H[Image Pipeline]
    G --> I[Audio Pipeline]
    
    H --> H1[Extract Keyframes]
    H1 --> H2[OCR Tesseract]
    H1 --> H3[Caption BLIP]
    H1 --> H4[Detect YOLO]
    H1 --> H5[Face Embed]
    H1 --> H6[CLIP Embed]
    H1 --> H7[DINO Embed]
    H2 --> H8[NER Tag]
    H3 --> H8
    
    I --> I1[Extract Audio]
    I1 --> I2[Metadata]
    I1 --> I3[Diarize PyAnnote]
    I3 --> I4[Transcribe Whisper]
    I4 --> I5[Speaker Merge]
    I5 --> I6[Time Hints]
    I5 --> I7[Music Events]
    I5 --> I8[Speech Emotion]
    I5 --> I9[Text Sentiment]
    I5 --> I10[Text Emotion]
    I5 --> I11[NER Tag]
    I1 --> I12[CLAP Embed]
    
    H8 --> J[Memory Integration]
    I11 --> J
    H5 --> J
    H6 --> J
    H7 --> J
    I12 --> J
    
    J --> K[SQLite Store]
    J --> L[FAISS Index]
    J --> M[ID Maps]
    
    K --> N[Query & Retrieval]
    L --> N
    M --> N
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

## 🖼️ Image Pipeline Detail

```mermaid
flowchart LR
    A[Keyframe] --> B[OCR]
    A --> C[Caption]
    A --> D[Object Detect]
    A --> E[Face Detect]
    A --> F[CLIP Embed]
    A --> G[DINO Embed]
    
    B --> H[Text Output]
    C --> H
    D --> I[Bounding Boxes]
    E --> J[Face Vectors]
    F --> K[Vision-Language Vectors]
    G --> L[Visual Feature Vectors]
    
    H --> M[NER Tagging]
    M --> N[Entities]
    
    I --> O[Object Labels]
    J --> P[Known Faces DB]
    K --> Q[FAISS CLIP Index]
    L --> R[FAISS DINO Index]
    N --> S[SQLite]
    O --> S
    P --> S
```

---

## 🎵 Audio Pipeline Detail

```mermaid
flowchart TD
    A[Audio Segment] --> B[Metadata Extraction]
    A --> C[Speaker Diarization]
    
    B --> D[Duration, SR, Format]
    C --> E[Speaker Segments]
    
    E --> F[Transcription Whisper]
    F --> G[Text + Timestamps]
    
    G --> H[Speaker Merge]
    H --> I[Consolidated Segments]
    
    I --> J[Time Hints]
    I --> K[Music Events]
    I --> L[Speech Emotion]
    I --> M[Text Sentiment]
    I --> N[Text Emotion]
    I --> O[NER Tagging]
    
    A --> P[CLAP Embedding]
    
    J --> Q[Temporal Refs]
    K --> R[Event Labels]
    L --> S[Emotion Labels]
    M --> T[Sentiment Scores]
    N --> U[Emotion Scores]
    O --> V[Entities]
    P --> W[Audio Vectors]
    
    D --> X[SQLite]
    Q --> X
    R --> X
    S --> X
    T --> X
    U --> X
    V --> X
    W --> Y[FAISS Audio Index]
```

---

## 💾 Memory Layer Architecture

```mermaid
graph TB
    subgraph "Memory Layer"
        A[SQLite Database] --> A1[scenes table]
        A --> A2[assets table]
        A --> A3[scene_bundles table]
        A --> A4[summaries table]
        
        B[FAISS Indices] --> B1[Text Index 384d]
        B --> B2[CLIP Index 512d]
        B --> B3[DINO Index 768d]
        B --> B4[Audio Index 512d]
        
        C[ID Maps] --> C1[clip_id_map.sqlite]
        C --> C2[dino_id_map.sqlite]
        C --> C3[clap_id_map.sqlite]
    end
    
    subgraph "Query Layer"
        D[Semantic Search] --> B1
        D --> B2
        D --> B3
        D --> B4
        
        E[Metadata Query] --> A1
        E --> A2
        E --> A3
        
        F[ID Resolution] --> C1
        F --> C2
        F --> C3
    end
    
    B1 -.Link.- C1
    B2 -.Link.- C1
    B3 -.Link.- C2
    B4 -.Link.- C3
```

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
    
    B1 -.pth link.- D[L:/ zenml_project]
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
    C --> D[GPU/CPU on L:/ drive]
    
    B -.Optional.- E[External APIs]
    E -.User Choice.- F[OpenAI GPT]
    E -.User Choice.- G[ElevenLabs TTS]
    
    D --> H[Local Storage]
    H --> I[L:/GoodQ_Data/]
    H --> J[L:/models/]
    
    I --> K[SQLite Encrypted?]
    I --> L[FAISS Indices]
    I --> M[Step Logs]
    
    K --> N[Backup to NAS]
    L --> N
    M --> N
    
    N --> O[G:/ UGREEN NAS]
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
    participant ZM as ZenML
    participant SR as Step Runner
    participant ENV as Conda Env
    participant MEM as Memory Layer
    
    U->>CLI: pwsh ingest_videos_lite.ps1
    CLI->>CLI: Sync .env.local
    CLI->>ZM: conda run -n goodq_zenml
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
