# Knowledge Graph Architecture

## System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                    GoodQ Multimodal Pipeline                      │
│                                                                    │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │ Video   │  │ Audio   │  │ Image   │  │  Text   │            │
│  │ Ingest  │  │ Process │  │ Process │  │ Extract │            │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘            │
│       │            │            │            │                   │
│       └────────────┴────────────┴────────────┘                   │
│                        │                                          │
│                        ▼                                          │
│              ┌──────────────────┐                                │
│              │ Analysis Results │                                │
│              └────────┬─────────┘                                │
└───────────────────────┼──────────────────────────────────────────┘
                        │
                        ▼
          ┌─────────────────────────┐
          │  Knowledge Graph Builder │
          └────────────┬─────────────┘
                       │
       ┌───────────────┼───────────────┐
       │               │               │
       ▼               ▼               ▼
   ┌───────┐      ┌────────┐      ┌────────┐
   │ Nodes │      │ Edges  │      │ Media  │
   └───┬───┘      └───┬────┘      └───┬────┘
       │              │               │
       └──────────────┴───────────────┘
                      │
                      ▼
            ┌──────────────────┐
            │ SQLite Database  │
            │ knowledge_graph  │
            │      .db         │
            └─────────┬────────┘
                      │
       ┌──────────────┼──────────────┐
       │              │              │
       ▼              ▼              ▼
  ┌─────────┐   ┌──────────┐   ┌────────┐
  │   CLI   │   │ Python   │   │  API   │
  │ Queries │   │   API    │   │ (Future)│
  └─────────┘   └──────────┘   └────────┘
```

## Entity Extraction Flow

```
Scene Analysis
      │
      ├─→ Object Detection ──→ Objects (dog, car, person)
      │                              │
      ├─→ Face Recognition  ──→ People (John, Sarah)
      │                              │
      ├─→ OCR / Caption     ──→ Text / Concepts
      │                              │
      ├─→ Audio Analysis    ──→ Speakers, Events
      │                              │
      ├─→ Sentiment         ──→ Emotions (happy, sad)
      │                              │
      └─→ EXIF / Location   ──→ Locations (beach, park)
                                     │
                                     ▼
                        All become Graph Nodes
```

## Graph Structure

### Node Types

```
┌─────────────────────────────────────────────────────────┐
│                       NODES                              │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐            │
│  │  Person  │  │  Object  │  │ Location  │            │
│  │          │  │          │  │           │            │
│  │  • John  │  │  • dog   │  │  • beach  │            │
│  │  • Sarah │  │  • car   │  │  • park   │            │
│  └──────────┘  └──────────┘  └───────────┘            │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐            │
│  │ Emotion  │  │ Concept  │  │   Event   │            │
│  │          │  │          │  │           │            │
│  │  • happy │  │  • birthday│  • scene   │            │
│  │  • sad   │  │  • party │  │   change  │            │
│  └──────────┘  └──────────┘  └───────────┘            │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Edge Types

```
Relationship Types:
──────────────────

co_occurs          │  Entities appearing together
                   │  Weight: Based on frequency
                   │
interacts_with     │  Physical/semantic interaction
                   │  (person → object)
                   │
located_in         │  Spatial relationship
                   │  (object → location)
                   │
has_emotion        │  Emotional state
                   │  (person → emotion)
                   │
temporal_next      │  Time-based adjacency
                   │  (scene₁ → scene₂)
                   │
mentions           │  Text/audio reference
                   │  (text → entity)
```

## Relationship Building

### Co-occurrence Example

```
Scene at 10.5s contains:
┌────────────────────────────┐
│  Entities:                 │
│  • Person: John            │
│  • Object: dog             │
│  • Location: beach         │
│  • Emotion: happy          │
└────────────────────────────┘
         │
         ▼
    Creates Edges:
         │
    ┌────┴────┬────────┬─────────┐
    │         │        │         │
    ▼         ▼        ▼         ▼
  John ───── dog ─── beach ─── happy
    └──────────┴────────┴──────────┘
     All connected with "co_occurs"
```

### Temporal Linking

```
Timeline:
─────────────────────────────────────────────►

Scene 1          Scene 2          Scene 3
(0-10s)         (10-20s)         (20-30s)
   │               │                │
   │               │                │
Entities:      Entities:        Entities:
 • John          • John           • Sarah
 • dog           • car            • park
   │               │                │
   │               │                │
   └───temporal───►│                │
                   └───temporal────►│
```

### Semantic Relationships

```
Domain Knowledge Applied:

Person + Location → located_in
  John at beach → John ──[located_in]──► beach

Person + Emotion → has_emotion
  John + happy → John ──[has_emotion]──► happy

Person + Object → interacts_with
  John + dog → John ──[interacts_with]──► dog

Object + Location → located_in
  dog at beach → dog ──[located_in]──► beach
```

## Query Patterns

### 1. Find Person Appearances

```
Query: "Where does John appear?"

   ┌─────┐
   │John │
   └──┬──┘
      │ appears_in
      ├──────────┬──────────┬──────────┐
      ▼          ▼          ▼          ▼
  Scene 1    Scene 3    Scene 7    Scene 12
  (0-10s)    (20-30s)   (60-70s)   (110-120s)
```

### 2. Co-occurrence Analysis

```
Query: "What appears with 'dog'?"

        ┌─────┐
        │ dog │
        └──┬──┘
           │ co_occurs
    ┌──────┼──────┬───────┐
    ▼      ▼      ▼       ▼
  John   Sarah  beach   happy
  (8x)   (3x)   (10x)   (6x)
  
  Numbers show co-occurrence frequency
```

### 3. Related Scenes

```
Query: "Scenes similar to Scene 5"

Scene 5 entities:
  • John
  • dog
  • beach

Search for scenes with similar entities:

Scene 1: 3/3 match (John, dog, beach)    ← Most similar
Scene 8: 2/3 match (dog, beach)
Scene 3: 1/3 match (John)
```

### 4. Temporal Narrative

```
Query: "Story from 0-60 seconds"

Timeline 0s ────────────────────────► 60s

Entities appearing:
  ├─ John (0-30s)
  ├─ Sarah (30-60s)
  ├─ dog (0-20s)
  └─ beach (0-60s)

Events:
  ├─ Scene change (0s)
  ├─ Scene change (10s)
  ├─ Scene change (20s)
  └─ Scene change (30s)

Summary:
  Locations: beach
  People: John, Sarah
  Objects: dog
  Emotions: happy, excited
```

## Database Schema

```
┌──────────────────────────────────────────────┐
│                NODES TABLE                   │
├──────────────────────────────────────────────┤
│ id              │ INTEGER PRIMARY KEY        │
│ node_type       │ TEXT (person/object/etc)   │
│ name            │ TEXT                       │
│ properties      │ JSON                       │
│ first_seen      │ REAL (timestamp)           │
│ last_seen       │ REAL (timestamp)           │
│ occurrence_count│ INTEGER                    │
└──────────────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│                EDGES TABLE                   │
├──────────────────────────────────────────────┤
│ id              │ INTEGER PRIMARY KEY        │
│ source_id       │ INTEGER (FK → nodes)       │
│ target_id       │ INTEGER (FK → nodes)       │
│ edge_type       │ TEXT (co_occurs/etc)       │
│ weight          │ REAL                       │
│ properties      │ JSON                       │
└──────────────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│             MEDIA_NODES TABLE                │
├──────────────────────────────────────────────┤
│ id              │ INTEGER PRIMARY KEY        │
│ media_type      │ TEXT (video/audio/etc)     │
│ media_path      │ TEXT                       │
│ scene_id        │ TEXT                       │
│ timestamp_start │ REAL                       │
│ timestamp_end   │ REAL                       │
│ properties      │ JSON                       │
└──────────────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│             NODE_MEDIA TABLE                 │
├──────────────────────────────────────────────┤
│ node_id         │ INTEGER (FK → nodes)       │
│ media_id        │ INTEGER (FK → media_nodes) │
│ confidence      │ REAL                       │
│ context         │ JSON (bbox, position, etc) │
└──────────────────────────────────────────────┘
```

## Performance Optimizations

### Indexing Strategy

```
High-Priority Indices:
─────────────────────
✓ nodes.node_type        (frequent filtering)
✓ nodes.name             (lookup by name)
✓ edges.source_id        (graph traversal)
✓ edges.target_id        (reverse traversal)
✓ edges.edge_type        (relationship filtering)
✓ media_nodes.media_path (content lookup)
✓ temporal_events.timestamp (temporal queries)

Composite Indices (future):
───────────────────────────
• (node_type, occurrence_count) for top entities
• (source_id, edge_type) for typed traversal
• (timestamp_start, timestamp_end) for range queries
```

### Query Optimization

```
Efficient Patterns:
─────────────────

✓ Limit traversal depth (max_depth=2)
✓ Filter by weight threshold (min_weight)
✓ Use specific edge types when possible
✓ Paginate large result sets
✓ Cache frequently accessed subgraphs

Avoid:
─────
✗ Full graph scans without filters
✗ Deep recursion without limits
✗ Unbounded temporal windows
```

## Future Enhancements

```
Planned Features:
────────────────

1. Advanced NLP
   └─► Named Entity Recognition (spaCy)
   └─► Relationship extraction from text
   └─► Coreference resolution

2. Face Recognition
   └─► Link face embeddings to people
   └─► Track same person across scenes
   └─► Person clustering

3. Graph Algorithms
   └─► PageRank for importance
   └─► Community detection
   └─► Shortest path queries
   └─► Centrality metrics

4. Visualization
   └─► Web-based graph explorer
   └─► D3.js/Cytoscape.js rendering
   └─► Interactive query builder

5. Advanced Queries
   └─► Pattern matching (Cypher-like)
   └─► Graph ML embeddings
   └─► Anomaly detection
```

## Integration Points

```
┌─────────────────────────────────────────────┐
│         Knowledge Graph Integrations         │
├─────────────────────────────────────────────┤
│                                              │
│  Input:                                      │
│  ├─► Pipeline analysis results               │
│  ├─► Scene manifests                         │
│  └─► Entity extractions                      │
│                                              │
│  Output:                                     │
│  ├─► Semantic search API                     │
│  ├─► Recommendation engine                   │
│  ├─► Timeline generator                      │
│  ├─► Related content finder                  │
│  └─► Context provider for LLM               │
│                                              │
│  Future:                                     │
│  ├─► Real-time updates                       │
│  ├─► Federated graphs                        │
│  └─► External knowledge bases                │
│                                              │
└─────────────────────────────────────────────┘
```
