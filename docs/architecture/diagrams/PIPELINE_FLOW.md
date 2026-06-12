<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-27 -->

# GoodQ Pipeline Flow Diagrams

**Status:** Active architecture reference
**Rendering target:** GitHub Markdown with native Mermaid support

These diagrams describe the current GoodQ4All runtime shape. They are not a
replacement for the canonical contracts; they are a GitHub-friendly visual map
of those contracts.

Primary contracts:

- [INGEST_ORCHESTRATION_CONTRACT.md](../INGEST_ORCHESTRATION_CONTRACT.md)
- [SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md)
- [MEMORY_STORAGE.md](../MEMORY_STORAGE.md)
- [SCENE_MANIFEST_SPECIFICATION.md](../SCENE_MANIFEST_SPECIFICATION.md)
- [PHASE6_MULTIMODAL_FUSION.md](../PHASE6_MULTIMODAL_FUSION.md)

The canonical execution owner remains `cli/run_ingestion.py`. Control recurrence
reporting is read-only observability and does not activate `ControlAgent` or
healing.

---

## Canonical Pipeline Flow

```mermaid
flowchart TB
    OP["Operator or Watchdog"] --> CLI["cli/run_ingestion.py"]
    CLI --> DISCOVER["Resolve config and input media"]
    DISCOVER --> SCENE_DETECT["Scene detection"]
    SCENE_DETECT --> MANIFEST["video/scene_manifest.json"]

    MANIFEST --> LOOP{"For each scene"}

    LOOP --> VISION["Vision steps"]
    LOOP --> AUDIO["Audio steps"]
    LOOP --> TEXT["Transcript and text signals"]

    VISION --> VISION_OUT["Keyframes, OCR, captions, objects, faces, visual embeddings"]
    AUDIO --> AUDIO_OUT["Audio chunks, transcript, diarization, emotion, audio embeddings"]
    TEXT --> TEXT_OUT["Entities, tags, scene context, summaries"]

    VISION_OUT --> SCENE_TRUTH["Scene-level truth"]
    AUDIO_OUT --> SCENE_TRUTH
    TEXT_OUT --> SCENE_TRUTH

    SCENE_TRUTH --> KG_RT["Realtime KG update"]
    SCENE_TRUTH --> MEM_DB["memory.db"]
    SCENE_TRUTH --> QDRANT["Qdrant vector collections"]

    SCENE_TRUTH --> PHASE6A["Phase 6a scene visual embeddings"]
    PHASE6A --> PHASE6B["Phase 6b cross-modal harmonization"]
    PHASE6B --> TEMPORAL["temporal_index.json"]
    PHASE6B --> MANIFEST_UPDATE["scene_manifest.json enriched"]

    KG_RT --> KG_DB["knowledge_graph.db"]
    MEM_DB --> RUN_SUMMARY["output/scene_ingest_results.json"]
    KG_DB --> RUN_SUMMARY
    QDRANT --> RUN_SUMMARY
    TEMPORAL --> RUN_SUMMARY
    MANIFEST_UPDATE --> RUN_SUMMARY

    classDef entry fill:#f8fafc,stroke:#475569,stroke-width:1px,color:#0f172a
    classDef process fill:#ecfeff,stroke:#0891b2,stroke-width:1px,color:#164e63
    classDef truth fill:#f0fdf4,stroke:#16a34a,stroke-width:1px,color:#14532d
    classDef store fill:#fff7ed,stroke:#ea580c,stroke-width:1px,color:#7c2d12
    classDef report fill:#f5f3ff,stroke:#7c3aed,stroke-width:1px,color:#3b0764

    class OP,CLI,DISCOVER entry
    class SCENE_DETECT,LOOP,VISION,AUDIO,TEXT,VISION_OUT,AUDIO_OUT,TEXT_OUT,PHASE6A,PHASE6B process
    class MANIFEST,SCENE_TRUTH,TEMPORAL,MANIFEST_UPDATE truth
    class KG_RT,MEM_DB,KG_DB,QDRANT store
    class RUN_SUMMARY report
```

---

## Scene Truth Flow

```mermaid
flowchart LR
    subgraph Inputs["Scene inputs"]
        VIDEO["Video frame"]
        WAV["Scene audio"]
        META["Video metadata"]
    end

    subgraph Perception["Perception steps"]
        OCR["OCR"]
        CAPTION["Caption"]
        OBJECTS["Objects"]
        FACE["Face signals"]
        WHISPER["Transcription"]
        DIAR["Diarization"]
        EMOTION["Emotion"]
        EMBED["Embeddings"]
    end

    subgraph SceneArtifacts["Authoritative scene artifacts"]
        SM["scene_manifest.json"]
        TI["temporal_index.json"]
    end

    VIDEO --> OCR
    VIDEO --> CAPTION
    VIDEO --> OBJECTS
    VIDEO --> FACE
    VIDEO --> EMBED

    WAV --> WHISPER
    WAV --> DIAR
    WAV --> EMOTION
    WAV --> EMBED
    META --> SM

    OCR --> SM
    CAPTION --> SM
    OBJECTS --> SM
    FACE --> SM
    WHISPER --> SM
    DIAR --> SM
    EMOTION --> SM
    EMBED --> SM
    SM --> TI

    classDef input fill:#f8fafc,stroke:#64748b,color:#0f172a
    classDef step fill:#ecfeff,stroke:#0891b2,color:#164e63
    classDef artifact fill:#f0fdf4,stroke:#16a34a,color:#14532d

    class VIDEO,WAV,META input
    class OCR,CAPTION,OBJECTS,FACE,WHISPER,DIAR,EMOTION,EMBED step
    class SM,TI artifact
```

---

## Memory Layer Architecture

This section replaces the older memory-layer diagram that did not render on
GitHub. The broken edge syntax has been replaced with conservative Mermaid
links, and the diagram now reflects the active epoch-scoped storage contract.

```mermaid
flowchart TB
    subgraph TruthArtifacts["Artifact truth"]
        SM["scene_manifest.json"]
        TI["temporal_index.json"]
        SIR["scene_ingest_results.json"]
    end

    subgraph SQLite["Epoch SQLite"]
        MEM["memory.db"]
        MEM_SCENES["scenes / segments / summaries"]
        MEM_EMB["embedding routing metadata"]
        MEM_AUDIT["memory_commit_events"]
        KG["knowledge_graph.db"]
        KG_NODES["nodes"]
        KG_EDGES["edges"]
        KG_MEDIA["media_nodes / node_media"]
        KG_EVENTS["events / event_nodes"]
    end

    subgraph VectorStore["Vector storage"]
        QT["Qdrant text/audio collections"]
        QV["Qdrant CLIP/DINO epoch collections"]
        FAISS["FAISS optional parity"]
    end

    subgraph Retrieval["Read surfaces"]
        RETRIEVE["cli.retrieve / API retrieval"]
        NLQ["cli.nl_query"]
        REPORTS["run summaries and recurrence reports"]
    end

    SM --> MEM
    SM --> KG
    SM --> QV
    SM --> TI
    TI --> SIR
    MEM --> SIR
    KG --> SIR

    MEM --> MEM_SCENES
    MEM --> MEM_EMB
    MEM --> MEM_AUDIT

    KG --> KG_NODES
    KG --> KG_EDGES
    KG --> KG_MEDIA
    KG --> KG_EVENTS

    MEM_EMB -- embedding_id --> QT
    MEM_EMB -- embedding_id --> QV
    QV -- payload scene_id --> SM
    QT -- payload scene_id --> SM
    KG_MEDIA -- scene_id --> SM

    QT --> RETRIEVE
    QV --> RETRIEVE
    FAISS -. configured fallback .-> RETRIEVE
    KG --> NLQ
    MEM --> NLQ
    SIR --> REPORTS
    TI --> REPORTS

    classDef artifact fill:#f0fdf4,stroke:#16a34a,color:#14532d
    classDef sqlite fill:#fff7ed,stroke:#ea580c,color:#7c2d12
    classDef vector fill:#eef2ff,stroke:#4f46e5,color:#312e81
    classDef read fill:#fdf4ff,stroke:#c026d3,color:#701a75

    class SM,TI,SIR artifact
    class MEM,MEM_SCENES,MEM_EMB,MEM_AUDIT,KG,KG_NODES,KG_EDGES,KG_MEDIA,KG_EVENTS sqlite
    class QT,QV,FAISS vector
    class RETRIEVE,NLQ,REPORTS read
```

Storage locations:

- `memory.db`: `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/memory.db`
- `knowledge_graph.db`: `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/knowledge_graph.db`
- scene manifest: `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video_name>/video/scene_manifest.json`
- temporal index: `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video_name>/temporal_index.json`
- run summary: `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/output/scene_ingest_results.json`
- Qdrant: `http://127.0.0.1:6333`

Qdrant collection names are resolved from config. The active epoch pattern is
`goodq_<modality>_epoch_<epoch>` for configured modality collections.

---

## Audio Runtime Flow

```mermaid
flowchart TB
    SCENE_AUDIO["Scene audio chunk"] --> SELECT{"WSL audio enabled and healthy?"}

    SELECT -- yes --> WSL["Direct unified WSL worker"]
    SELECT -- no --> WIN["Windows-safe audio path"]

    WSL --> WSL_OUT["transcript, diarization, emotion, embeddings, voice signatures"]
    WIN --> WIN_OUT["available transcript/audio metadata and explicit fallback status"]

    WSL_OUT --> AUDIO_TRUTH["audio truth in scene_manifest.json"]
    WIN_OUT --> AUDIO_TRUTH

    AUDIO_TRUTH --> STATUS["diarization_status / emotion_status / backend fields"]
    AUDIO_TRUTH --> PHASE6["Phase 6 harmonization input"]

    classDef choice fill:#fefce8,stroke:#ca8a04,color:#713f12
    classDef runtime fill:#ecfeff,stroke:#0891b2,color:#164e63
    classDef truth fill:#f0fdf4,stroke:#16a34a,color:#14532d

    class SELECT choice
    class WSL,WIN,WSL_OUT,WIN_OUT runtime
    class AUDIO_TRUTH,STATUS,PHASE6 truth
```

WSL is a compute extension, not a storage authority. The Windows host and the
epoch artifact tree remain the source of truth.

---

## Control Observability Boundary

```mermaid
flowchart LR
    STEP_RUNS["step_runs.jsonl"] --> RECURRENCE["control_recurrence_report"]
    WARNINGS["run warnings"] --> RECURRENCE
    SIR["scene_ingest_results.json"] --> RECURRENCE
    SM["scene_manifest.json"] --> RECURRENCE
    TI["temporal_index.json"] --> RECURRENCE
    EXP["experiment_log.json"] --> RECURRENCE

    RECURRENCE --> SUMMARY["human summary"]
    RECURRENCE --> JSON["stable JSON"]
    RECURRENCE --> MD["optional markdown"]

    RECURRENCE -. does not activate .-> CA["ControlAgent"]
    RECURRENCE -. does not mutate .-> CFG["configs"]
    RECURRENCE -. does not orchestrate .-> INGEST["cli/run_ingestion.py"]

    classDef input fill:#f8fafc,stroke:#64748b,color:#0f172a
    classDef report fill:#f5f3ff,stroke:#7c3aed,color:#3b0764
    classDef boundary fill:#fee2e2,stroke:#dc2626,color:#7f1d1d

    class STEP_RUNS,WARNINGS,SIR,SM,TI,EXP input
    class RECURRENCE,SUMMARY,JSON,MD report
    class CA,CFG,INGEST boundary
```

The recurrence report is observability only. It does not heal, mutate config, or
replace canonical ingestion.

---

## Orchestration Sequence

```mermaid
sequenceDiagram
    participant Operator
    participant CLI as cli/run_ingestion.py
    participant Step as Step runner
    participant Manifest as scene_manifest.json
    participant KG as knowledge_graph.db
    participant Qdrant
    participant Phase6 as Phase 6
    participant Output as scene_ingest_results.json

    Operator->>CLI: Start canonical ingestion
    CLI->>CLI: Resolve config and input media
    CLI->>Manifest: Write initial scene manifest

    loop For each scene
        CLI->>Step: Execute scoped scene step
        Step-->>CLI: Return result or visible failure
        CLI->>Manifest: Persist scene truth
        CLI->>KG: Persist realtime graph evidence
        CLI->>Qdrant: Persist vectors when available
    end

    CLI->>Phase6: Run visual embeddings and harmonization
    Phase6->>Manifest: Persist Phase 6 fields
    Phase6-->>CLI: Return temporal_index.json path
    CLI->>Output: Write run summary
```

---

## Use Case Flow: Scene Retrieval

```mermaid
flowchart LR
    QUERY["User query"] --> ENCODE["Encode query"]
    ENCODE --> SEARCH["Qdrant-first vector search"]
    SEARCH --> PAYLOAD["Payload scene_id / embedding provenance"]
    PAYLOAD --> ARTIFACTS["scene_manifest.json and temporal_index.json"]
    PAYLOAD --> KG["knowledge_graph.db"]
    PAYLOAD --> MEM["memory.db"]
    ARTIFACTS --> RESULT["Scene result with evidence"]
    KG --> RESULT
    MEM --> RESULT

    classDef query fill:#f8fafc,stroke:#64748b,color:#0f172a
    classDef search fill:#eef2ff,stroke:#4f46e5,color:#312e81
    classDef truth fill:#f0fdf4,stroke:#16a34a,color:#14532d

    class QUERY,ENCODE query
    class SEARCH,PAYLOAD search
    class ARTIFACTS,KG,MEM,RESULT truth
```

---

## Diagram Hygiene Notes

- Mermaid blocks intentionally use conservative `flowchart` and
  `sequenceDiagram` syntax for GitHub rendering.
- Scene manifests and `temporal_index.json` are authoritative artifact truth.
- Qdrant is the canonical vector store; FAISS is optional parity/fallback.
- Optional enrichment failures must remain visible and must not halt ingestion
  unless they invalidate the required scene/run truth.
