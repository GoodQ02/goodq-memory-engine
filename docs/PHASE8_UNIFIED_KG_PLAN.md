# PHASE 8: UNIFIED KNOWLEDGE GRAPH - CROSS-VIDEO INTELLIGENCE

## Mission
Create a unified knowledge graph that connects ALL family videos across years, building a comprehensive "family memory brain" with cross-video relationships, temporal continuity, entity persistence, and multi-generational emotional narratives.

## Overview
Phase 8 transforms individual video knowledge graphs into a **unified semantic network** that understands your family's history across decades, tracks people through time, identifies recurring themes, and creates a queryable archive of memories.

## Current State ✅
- ✅ Single-video KG working (sample.mp4: 49 nodes, 943 edges)
- ✅ Entity extraction from all modalities
- ✅ Emotional arc analysis with LLM
- ✅ Temporal relationships within videos
- ✅ Analytics dashboard operational

## Phase 8 Goals 🎯

### 1. **Cross-Video Entity Resolution** (Priority 1)
**Goal**: Same person/place/object recognized across multiple videos

**Implementation**:
- Face embedding clustering across videos
- Voice print matching for speaker identity
- Name entity resolution (same person mentioned across years)
- Location persistence (recognize family home, vacation spots)
- Object tracking (family car, favorite toys, etc.)

**Database Changes**:
```sql
-- Global entity registry
CREATE TABLE global_entities (
    id INTEGER PRIMARY KEY,
    entity_type TEXT,  -- person, location, object
    canonical_name TEXT,
    properties TEXT,   -- JSON with face embeddings, voice prints, etc.
    first_appearance TEXT,  -- video_hash of first seen
    last_appearance TEXT,   -- video_hash of last seen
    appearance_count INTEGER,
    created_at TEXT
);

-- Video-specific instances linked to global entities
CREATE TABLE entity_instances (
    id INTEGER PRIMARY KEY,
    global_entity_id INTEGER,
    video_hash TEXT,
    local_node_id INTEGER,  -- FK to KG nodes table
    confidence REAL,
    FOREIGN KEY (global_entity_id) REFERENCES global_entities(id)
);
```

### 2. **Temporal Continuity Across Years** (Priority 1)
**Goal**: Understand chronological order and time gaps between videos

**Implementation**:
- Video timeline construction from 1987 → present
- Age progression tracking (recognize same person at different ages)
- Life event detection (births, graduations, weddings)
- Seasonal/holiday pattern recognition
- Family structure evolution over time

**Features**:
- "Show me all birthdays from 1987-2000"
- "Track my brother's growth from age 1 to 18"
- "What happened between summer 1990 and Christmas 1991?"

### 3. **Multi-Video Relationship Networks** (Priority 1)
**Goal**: Map family relationships across entire archive

**Implementation**:
- Family tree construction from visual co-occurrence
- Social network analysis (who appears with whom?)
- Relationship strength scoring based on co-appearances
- Group detection (extended family, friend groups, etc.)
- Interaction pattern analysis

**Network Types**:
- **Family Network**: Parent-child, siblings, grandparents
- **Social Network**: Friends, classmates, neighbors
- **Location Network**: Homes, schools, vacation spots
- **Event Network**: Holidays, parties, milestones

### 4. **Thematic Intelligence** (Priority 2)
**Goal**: Identify recurring themes, topics, and interests across years

**Implementation**:
- LLM-powered theme extraction across video collection
- Interest evolution tracking (hobbies, activities over time)
- Emotional theme patterns (family joy markers, difficult periods)
- Activity clustering (sports, music, travel, celebrations)
- Topic persistence analysis

**Queries Enabled**:
- "Show me all videos about music"
- "When did we start going camping?"
- "Track our Christmas traditions over the years"

### 5. **Emotional Narrative Arc** (Priority 2)
**Goal**: Create a multi-year emotional journey of the family

**Implementation**:
- Aggregate emotional arcs from individual videos
- Detect emotional patterns across years
- Identify pivotal moments (joy peaks, difficult periods)
- LLM synthesis of decade-long emotional journey
- Sentiment evolution visualization

**Outputs**:
- "The Family Emotional Journey 1987-2025"
- Decade summaries with emotional context
- Key moment identification
- Resilience and growth patterns

### 6. **Cross-Video Search & Retrieval** (Priority 2)
**Goal**: Find specific moments across entire archive

**Implementation**:
- Unified vector search across all embeddings
- Multi-modal query (find by face, voice, topic, emotion)
- Temporal range queries ("show 1990s summer vacations")
- Composite queries ("find Dad playing guitar")
- Similar moment detection

**Search Types**:
- Semantic: "family gatherings with grandparents"
- Visual: Find similar faces/scenes
- Audio: Find similar music/speech
- Temporal: Date ranges, seasons, years
- Emotional: "happiest moments" or "challenging times"

### 7. **Intelligent Summarization** (Priority 3)
**Goal**: LLM-generated summaries at multiple levels

**Implementation**:
- Per-year summaries (1987 highlights, 1988 highlights)
- Decade narratives (the 1990s story)
- Per-person highlights (Mom's journey, sibling growth)
- Theme-based compilations (all birthdays, all vacations)
- Automated "Year in Review" reports

### 8. **Conversational Memory Interface** (Priority 3)
**Goal**: Chat with your family archive

**Implementation**:
- Natural language queries across all videos
- Context-aware conversations
- Follow-up question handling
- Evidence-based answers with video timestamps
- Multi-turn dialogue about family history

**Examples**:
- User: "When did we move to the new house?"
- System: "Based on videos, your family moved in summer 1992. I see the new house first appearing in a video from July 4th, 1992..."
- User: "What was my brother like back then?"
- System: "In 1992 videos (ages 5-6), he appears in 8 videos, often playing with toy cars..."

## Technical Architecture

### Database Structure
```
unified_goodq.db
├── global_entities (people, places, objects across all videos)
├── entity_instances (video-specific appearances)
├── video_registry (metadata for all processed videos)
├── cross_video_relationships (entity connections across videos)
├── temporal_timeline (chronological event ordering)
├── thematic_index (themes and topics)
├── emotional_arcs (aggregated sentiment data)
└── search_index (unified vector search)
```

### Processing Flow
```
Individual Videos (1987_1988, 1989_1990, etc.)
    ↓
Extract to Individual KGs
    ↓
Entity Resolution & Merging
    ↓
Cross-Video Relationship Building
    ↓
Temporal Timeline Construction
    ↓
Theme & Emotional Aggregation
    ↓
Unified Knowledge Graph
    ↓
Search Index & Query Interface
```

### LLM Integration Points
1. **Entity Resolution**: Match person names across transcripts
2. **Relationship Inference**: Deduce family relationships from context
3. **Theme Extraction**: Identify recurring topics and interests
4. **Narrative Synthesis**: Generate year/decade summaries
5. **Query Understanding**: Parse natural language questions
6. **Answer Generation**: Create coherent responses with evidence

## Implementation Phases

### Phase 8.1: Database Infrastructure (1 hour)
- [ ] Create unified database schema
- [ ] Build entity resolution framework
- [ ] Implement video registry system
- [ ] Create migration scripts for existing data

### Phase 8.2: Entity Resolution Engine (2 hours)
- [ ] Face embedding clustering
- [ ] Voice signature matching
- [ ] Name entity deduplication
- [ ] Location canonicalization
- [ ] Confidence scoring system

### Phase 8.3: Cross-Video Relationship Builder (2 hours)
- [ ] Co-occurrence analysis across videos
- [ ] Temporal relationship mapping
- [ ] Family network construction
- [ ] Relationship strength scoring
- [ ] Network visualization data

### Phase 8.4: Temporal Timeline (1 hour)
- [ ] Chronological video ordering
- [ ] Event timeline construction
- [ ] Time gap analysis
- [ ] Age progression tracking
- [ ] Historical context integration

### Phase 8.5: Thematic Intelligence (2 hours)
- [ ] LLM-powered theme extraction
- [ ] Topic clustering across years
- [ ] Interest evolution tracking
- [ ] Activity pattern analysis
- [ ] Recurring event detection

### Phase 8.6: Unified Search (2 hours)
- [ ] Vector index across all embeddings
- [ ] Multi-modal query engine
- [ ] Temporal filtering
- [ ] Relevance ranking
- [ ] Result aggregation

### Phase 8.7: Conversational Interface (2 hours)
- [ ] Natural language query parser
- [ ] Context management system
- [ ] Evidence retrieval
- [ ] LLM answer generation
- [ ] Interactive chat loop

### Phase 8.8: Testing & Validation (1 hour)
- [ ] Test with sample.mp4 + 1987_1988 videos
- [ ] Validate entity resolution accuracy
- [ ] Test cross-video queries
- [ ] Verify timeline construction
- [ ] Benchmark search performance

## Success Metrics

- [ ] Entity resolution accuracy >85%
- [ ] Cross-video relationships detected
- [ ] Timeline includes all videos
- [ ] Search finds relevant clips <5 seconds
- [ ] Conversational queries answered correctly
- [ ] Multi-year summaries are coherent
- [ ] Family relationships mapped accurately

## Files to Create

1. `lib/unified_knowledge_graph.py` - Unified KG manager
2. `lib/entity_resolver.py` - Cross-video entity matching
3. `lib/timeline_builder.py` - Temporal continuity
4. `lib/theme_analyzer.py` - Cross-video theme extraction
5. `lib/unified_search.py` - Multi-modal search engine
6. `cli/memory_chat.py` - Conversational interface
7. `scripts/build_unified_kg.py` - Migration/build script
8. `scripts/analyze_cross_video.py` - Analysis tools
9. `tests/test_phase8_unified_kg.py` - Test suite

## Configuration Updates

Add to `config.yaml`:
```yaml
unified_knowledge_graph:
  enabled: true
  db_path: "data/unified_goodq.db"
  
  entity_resolution:
    face_similarity_threshold: 0.85
    voice_similarity_threshold: 0.80
    name_matching_algorithm: "fuzzy"  # fuzzy, exact, llm
    use_llm_for_disambiguation: true
    
  timeline:
    date_extraction_from_filenames: true
    date_format_patterns: 
      - "%Y_%m_%d"
      - "%Y"
    infer_missing_dates: true
    
  search:
    embedding_model: "clip"  # or custom
    index_type: "faiss"  # or annoy, chromadb
    max_results: 50
    
  chat:
    enabled: true
    context_window_size: 10
    max_conversation_turns: 20
    evidence_snippets: 3
```

## Integration with Existing System

- **Non-destructive**: Individual video KGs remain intact
- **Additive**: Unified KG references but doesn't replace individual KGs
- **Backward compatible**: All Phase 1-7 functionality preserved
- **Incremental**: Can build unified KG as new videos are processed

## Next Steps After Phase 8

- **Phase 9**: Advanced ML models (person re-identification, scene similarity)
- **Phase 10**: Web dashboard with interactive timeline
- **Phase 11**: Automated highlight reels and compilations
- **Phase 12**: Predictive insights (suggest similar old videos for new content)

---

**Status**: READY TO IMPLEMENT
**Estimated Time**: 12-15 hours total
**Dependencies**: Phases 1-7 complete ✅
**Ready for**: Multi-year family archive (1987-2025)

---

*"Building a brain for your family's memories"* 🧠✨
