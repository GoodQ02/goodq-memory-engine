# Phase 6: Full Knowledge Graph Integration with LLM Enhancement

## Overview
Integrate knowledge graph construction at every key pipeline step to ensure all LLM-generated insights, entity detections, and relationships are captured in the unified semantic graph.

## Current State
✅ Knowledge graph infrastructure working (49 nodes, 943 edges)
✅ LLM-powered emotional arc analysis functional
✅ Scene-level data being ingested
✅ Basic entity extraction (objects, people, emotions, tags)

## Integration Points

### 1. Scene Processing → KG Integration
**Status**: Partial - needs enhancement
**Files to modify**:
- `cli/run_ingestion.py` - Add KG updates after each scene
- `steps/graph_builder/graph_builder.py` - Enhance entity extraction

**Actions**:
- [  ] Add real-time KG updates as scenes are processed
- [  ] Extract entities from LLM scene summaries
- [  ] Link transcript entities to visual entities
- [  ] Create temporal relationships between consecutive scenes

### 2. Audio Transcription → KG Integration  
**Status**: Missing
**Files to modify**:
- `steps/audio_transcribe/step.py`
- New: `steps/audio_transcribe/kg_integration.py`

**Actions**:
- [  ] Extract named entities from transcripts (people, places, topics)
- [  ] Create speaker nodes in KG
- [  ] Link spoken topics to visual content
- [  ] Timestamp entity mentions for temporal context

### 3. LLM Scene Summarization → KG Integration
**Status**: Partial - summaries stored but not fully linked
**Files to modify**:
- `steps/graph_builder/llm_enrichment.py`

**Actions**:
- [  ] Parse LLM summaries for additional entities
- [  ] Extract themes and concepts from summaries
- [  ] Create "theme" nodes that span multiple scenes
- [  ] Build semantic relationships from narrative analysis

### 4. Emotion/Sentiment → KG Integration
**Status**: Working - needs enhancement
**Files to modify**:
- `steps/emotion_classify/step.py`
- `steps/sentiment/step.py`

**Actions**:
- [  ] Create emotion transition edges between scenes
- [  ] Link emotions to specific objects/people when detected
- [  ] Build emotional co-occurrence patterns
- [  ] Track sentiment evolution over time

### 5. Video-Level Summary → KG Integration
**Status**: Missing
**Files to modify**:
- `steps/video_summarizer/step.py`
- New: `steps/video_summarizer/kg_integration.py`

**Actions**:
- [  ] Create video-level nodes in KG
- [  ] Extract overarching themes from video summary
- [  ] Link scene-level content to video-level narrative
- [  ] Create hierarchical relationships (video → scenes → entities)

### 6. Cross-Modal Entity Resolution
**Status**: Not implemented
**New file**: `lib/entity_resolver.py`

**Actions**:
- [  ] Merge duplicate entities across modalities
  - Person seen + person named in audio = same node
  - Object detected + object mentioned = same node
- [  ] Confidence-based entity merging
- [  ] Coreference resolution across scenes

### 7. Relationship Enhancement with LLM
**Status**: Partial
**Files to enhance**:
- `steps/graph_builder/emotion_arc_analyzer.py`
- New: `steps/graph_builder/relationship_analyzer.py`

**Actions**:
- [  ] Use LLM to infer implicit relationships
- [  ] Detect causality between events
- [  ] Identify emotional reactions to entities
- [  ] Generate explanation text for relationships

### 8. Query Interface Enhancement
**Status**: Basic stats only
**Files to create/modify**:
- `cli/graph_query.py` (new)
- Enhance: `show_kg_insights.py`

**Actions**:
- [  ] Natural language query interface using LLM
- [  ] Entity-centric queries (show me all scenes with X)
- [  ] Relationship traversal (how are X and Y connected?)
- [  ] Temporal queries (what happened before/after X?)

## Implementation Order

1. **Scene Processing Enhancement** (Priority 1)
   - Real-time KG updates during ingestion
   - Most impactful for capturing data

2. **Cross-Modal Entity Resolution** (Priority 1)
   - Prevents duplicate entities
   - Improves graph quality significantly

3. **LLM Entity Extraction** (Priority 2)
   - Extract entities from summaries
   - Mine transcripts for additional context

4. **Relationship Enhancement** (Priority 2)
   - Build richer semantic connections
   - LLM-powered relationship inference

5. **Video-Level Integration** (Priority 3)
   - Hierarchical structure
   - Overarching narrative capture

6. **Query Interface** (Priority 3)
   - User-facing features
   - Validation of graph quality

## Success Metrics

- [ ] 100% of scenes have linked entities in KG
- [ ] LLM-extracted entities represented in graph
- [ ] Cross-modal entity merging reduces duplicates by 30%+
- [ ] Temporal relationships connect all consecutive scenes
- [ ] Emotional arc reflects LLM analysis
- [ ] Natural language queries return accurate results
- [ ] Graph can answer: "Who was present during [event]?"
- [ ] Graph can answer: "What caused [emotion]?"
- [ ] Graph can answer: "What topics were discussed with [person]?"

## Testing Strategy

1. **Integration Tests**:
   - Run full pipeline on sample.mp4
   - Verify all expected entities in KG
   - Check relationship counts match expectations

2. **Query Tests**:
   - Test entity lookups
   - Test relationship traversal
   - Test temporal queries

3. **Quality Tests**:
   - Verify no orphaned nodes
   - Check relationship weights
   - Validate temporal ordering

## Files to Create

- `lib/entity_resolver.py` - Cross-modal entity merging
- `steps/audio_transcribe/kg_integration.py` - Audio→KG bridge
- `steps/video_summarizer/kg_integration.py` - Video summary→KG
- `steps/graph_builder/relationship_analyzer.py` - LLM relationship inference
- `cli/graph_query.py` - Natural language KG queries
- `tests/test_kg_integration.py` - Integration test suite

## Configuration Updates

Add to `configs/config.yaml`:
```yaml
knowledge_graph:
  enabled: true
  db_path: "data/knowledge_graph.db"
  
  entity_resolution:
    enabled: true
    confidence_threshold: 0.7
    merge_similar_names: true
    
  llm_enrichment:
    enabled: true
    extract_entities_from_summaries: true
    infer_relationships: true
    relationship_confidence_threshold: 0.6
    
  temporal_features:
    create_sequence_edges: true
    max_temporal_distance: 30.0  # seconds
    
  query_interface:
    enabled: true
    natural_language: true
    max_results: 50
```

## Next Steps After Phase 6

- Phase 7: Advanced Analytics (pattern detection, anomaly finding)
- Phase 8: Multi-video knowledge graph (family memories connected across videos)
- Phase 9: Conversational interface (chat with your memories)
