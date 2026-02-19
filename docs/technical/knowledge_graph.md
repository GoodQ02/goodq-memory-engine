# Knowledge Graph System

## Overview

The GoodQ Knowledge Graph provides a powerful semantic layer on top of the multimodal analysis pipeline. It creates rich, queryable relationships between entities, concepts, temporal events, and media content.

## Architecture

### Core Components

1. **KnowledgeGraph** (`lib/knowledge_graph.py`)
   - SQLite-based graph database
   - Nodes: entities, concepts, locations, people, objects, events, emotions
   - Edges: relationships between nodes (co-occurrence, semantic, temporal)
   - Media nodes: links to actual video scenes/audio clips
   - Temporal events: time-based occurrences

2. **GraphQuery** (`lib/graph_query.py`)
   - High-level query interface
   - Specialized query methods for common patterns
   - Entity summarization and statistics

3. **Graph Builder Step** (`steps/graph_builder/`)
   - legacy orchestration pipeline step
   - Constructs graph from analysis results
   - Automatically creates nodes, edges, and relationships

4. **CLI Tool** (`cli/graph_query.py`)
   - Command-line interface for querying
   - Interactive exploration of the graph

## Database Schema

### Nodes Table
Stores all entities in the graph:
```sql
CREATE TABLE nodes (
    id INTEGER PRIMARY KEY,
    node_type TEXT,    -- person, object, location, concept, event, emotion
    name TEXT,
    properties TEXT,   -- JSON blob
    first_seen REAL,
    last_seen REAL,
    occurrence_count INTEGER,
    created_at TEXT
)
```

### Edges Table
Stores relationships between nodes:
```sql
CREATE TABLE edges (
    id INTEGER PRIMARY KEY,
    source_id INTEGER,
    target_id INTEGER,
    edge_type TEXT,    -- co_occurs, causes, located_in, mentions, etc.
    weight REAL,
    properties TEXT,
    created_at TEXT
)
```

### Media Nodes Table
Links to actual media content:
```sql
CREATE TABLE media_nodes (
    id INTEGER PRIMARY KEY,
    media_type TEXT,     -- video, audio, image, text
    media_path TEXT,
    scene_id TEXT,
    timestamp_start REAL,
    timestamp_end REAL,
    properties TEXT
)
```

### Node-Media Table
Associates nodes with media:
```sql
CREATE TABLE node_media (
    node_id INTEGER,
    media_id INTEGER,
    confidence REAL,
    context TEXT        -- JSON with bbox, position, etc.
)
```

### Temporal Events Table
Time-based events:
```sql
CREATE TABLE temporal_events (
    id INTEGER PRIMARY KEY,
    event_type TEXT,
    timestamp REAL,
    duration REAL,
    properties TEXT
)
```

## Graph Construction

The graph is automatically built during pipeline execution:

1. **Entity Extraction**
   - Objects from object detection
   - People from face recognition
   - Text from OCR and transcription
   - Audio events from audio analysis
   - Emotions from sentiment analysis
   - Locations from EXIF/recognition

2. **Relationship Building**
   - **Co-occurrence**: Entities appearing together in same scene
   - **Temporal**: Entities appearing in adjacent time windows
   - **Semantic**: Domain-specific relationships (object-location, person-emotion, etc.)

3. **Media Linking**
   - Each node is linked to media where it appears
   - Includes confidence scores and context (bounding boxes, timestamps)

## Query Patterns

### Find Person Appearances
```python
from lib.graph_query import GraphQuery

with GraphQuery('data/knowledge_graph.db') as gq:
    appearances = gq.find_person_appearances('John')
    for app in appearances:
        print(f"Scene: {app['scene_id']}, Time: {app['timestamp_start']}s")
```

### Get Scene Context
```python
context = gq.get_scene_context('scene_0042')
# Returns all entities, relationships, and metadata for the scene
```

### Find Related Scenes
```python
related = gq.find_related_scenes('scene_0042', max_results=5)
# Returns scenes with similar content/entities
```

### Track Concept Evolution
```python
timeline = gq.find_concept_evolution('birthday')
# Returns all appearances of concept over time
```

### Search by Criteria
```python
results = gq.search_by_multiple_criteria({
    'objects': ['person', 'cake'],
    'emotions': ['happy'],
    'time_range': (0, 300),
    'min_confidence': 0.7
})
```

### Temporal Narrative
```python
story = gq.find_temporal_story(start_time=0.0, end_time=60.0)
# Returns entities, events, and relationships in time window
```

## CLI Usage

### View Statistics
```bash
python cli/graph_query.py stats
```

### Find Person
```bash
python cli/graph_query.py find-person "John"
```

### Get Scene Context
```bash
python cli/graph_query.py scene-context scene_0042
python cli/graph_query.py scene-context scene_0042 --json  # JSON output
```

### List Entities
```bash
python cli/graph_query.py list-entities
python cli/graph_query.py list-entities --type person --limit 20
```

### Search
```bash
python cli/graph_query.py search --objects person car --emotions happy
python cli/graph_query.py search --start-time 0 --end-time 100 --min-confidence 0.8
```

### Temporal Story
```bash
python cli/graph_query.py story 0 60
python cli/graph_query.py story 0 60 --json
```

### Export Subgraph
```bash
python cli/graph_query.py export 1 2 3 4 output.json
```

## Integration with Pipeline

The knowledge graph is built as part of the pipeline:

```python
from steps.graph_builder import build_knowledge_graph

@pipeline
def goodq_pipeline(...):
    # ... other steps ...
    
    # Build knowledge graph from results
    graph_stats = build_knowledge_graph(
        analysis_results=results,
        config=config
    )
```

## Advanced Queries

### Graph Traversal
```python
# Find all nodes within 2 hops of a person
with GraphQuery('data/knowledge_graph.db') as gq:
    cursor = gq.kg.conn.cursor()
    person_id = cursor.execute(
        "SELECT id FROM nodes WHERE name='John'"
    ).fetchone()[0]
    
    related = gq.kg.find_related_nodes(
        person_id, 
        max_depth=2,
        min_weight=0.5
    )
```

### Co-occurrence Analysis
```python
# Find entities that frequently appear together
dog_id = cursor.execute(
    "SELECT id FROM nodes WHERE name='dog'"
).fetchone()[0]

co_occurring = gq.kg.find_co_occurring_nodes(dog_id)
```

### Temporal Queries
```python
# Find events near a timestamp
events = gq.kg.find_temporal_neighbors(
    timestamp=42.5,
    time_window=10.0,
    event_type='scene_change'
)
```

## Performance Considerations

1. **Indexing**: All key columns are indexed for fast queries
2. **Batch Operations**: Use transactions for bulk insertions
3. **Denormalization**: Some data is duplicated for query speed
4. **Caching**: Consider caching frequently accessed subgraphs

## Future Enhancements

1. **NLP Integration**: Named Entity Recognition for better entity extraction
2. **Face Recognition**: Link face embeddings to identified people
3. **Location Recognition**: Automatic place identification
4. **Causal Relationships**: Detect cause-effect between events
5. **Graph ML**: Apply graph algorithms (PageRank, community detection)
6. **Visualization**: Web interface for graph exploration
7. **Pattern Mining**: Discover recurring patterns in data

## Example Use Cases

### 1. Find All Scenes with a Person
```bash
python cli/graph_query.py find-person "Sarah"
```

### 2. Discover Related Content
```bash
python cli/graph_query.py related-scenes scene_0042 --max-results 10
```

### 3. Emotion Analysis
```bash
python cli/graph_query.py search --emotions happy excited --min-confidence 0.8
```

### 4. Object Tracking Over Time
```bash
python cli/graph_query.py track-concept "car"
```

### 5. Scene Similarity
```python
# Find scenes similar to a given scene based on entities
context = gq.get_scene_context('scene_0042')
related = gq.find_related_scenes('scene_0042')
```

## Troubleshooting

### Graph Not Building
- Ensure analysis results contain entity data
- Check that graph_builder step is in pipeline
- Verify database path is writable

### Slow Queries
- Check if indices exist: `PRAGMA index_list('nodes')`
- Consider adding domain-specific indices
- Use `EXPLAIN QUERY PLAN` to analyze queries

### Missing Relationships
- Verify entity extraction is working
- Check edge building functions in `graph_builder.py`
- Ensure co-occurrence threshold is appropriate

## API Reference

See inline documentation in:
- `lib/knowledge_graph.py`
- `lib/graph_query.py`
- `steps/graph_builder/graph_builder.py`

## Testing

Run the test suite:
```bash
python scripts/test_knowledge_graph.py
```

This creates a test database and validates all query patterns.
