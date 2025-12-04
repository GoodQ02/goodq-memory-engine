# Technical Analysis: Hidden Failures & Missing Functionality

**Date:** 2025-11-07
**Analyst:** GoodQ  
**Video Tested:** sample.mp4 (Colin & Joe band interview)
**Scenes Processed:** 10/15 complete

---

## Critical Findings

### 1. ❌ EMOTION ANALYSIS NOT EXECUTING

**Configuration:**
```yaml
audio:
  emotion:
    enabled: true
    model: speechbrain/emotion-recognition-wav2vec2-IEMOCAP
```

**Expected Output:**
- Emotions per audio segment: angry, happy, sad, neutral, fear, surprise, disgust
- Intensity scores per emotion
- Dominant emotion per scene

**Actual Output:**
- ❌ NONE - No emotion data in scene metadata
- No emotion field in database
- No emotion entries in logs

**Investigation Needed:**
1. Check if emotion model is being loaded
2. Verify emotion analyzer step is called
3. Check for silent failures in emotion processing
4. Look for try/except blocks swallowing errors

**File to Check:** `steps/audio/emotion_analyzer.py` or similar

---

### 2. ⚠️ OCR TEXT NOT SURFACED

**Status:** PARTIALLY WORKING

**Evidence:**
- Embeddings table shows `modality='frame_text'` entries
- 10 frame_text embeddings created
- OCR is running and creating embeddings

**Problem:**
- Raw OCR text NOT in scene metadata
- Can't see what text was extracted
- Text embedded but not stored as readable data

**Scene Metadata Check:**
```json
{
  "caption": "a man sitting in a chair",
  "objects": [...],
  // ❌ Missing: "ocr_text": "extracted text here"
}
```

**Fix Required:**
1. Surface OCR text to scene metadata
2. Add `ocr_text` field to scenes
3. Store raw text before/during embedding

**File to Check:** `steps/image/ocr_extractor.py` and `steps/image/image_analyzer.py`

---

### 3. ❌ INCOMPLETE SCENE PROCESSING

**Issue:** Only 10/15 scenes have extracted media

**Database Shows:**
- 15 scene records created (scenes 0-14)
- Only scenes 0-9 have keyframes and audio
- Scenes 10-14: Links point to non-existent files

**File System:**
```
logs/test_full_sample/sample/frames/
  scene_0000.jpg through scene_0009.jpg  ✅
  scene_0010.jpg through scene_0014.jpg  ❌ MISSING

logs/test_full_sample/sample/audio/
  scene_0000.wav through scene_0009.wav  ✅
  scene_0010.wav through scene_0014.wav  ❌ MISSING
```

**Possible Causes:**
1. Hard-coded limit of 10 scenes in extraction loop
2. Silent failure after scene 9
3. Timeout or resource limit
4. Early return condition met

**Check:** Scene extraction loops in video processing pipeline

---

### 4. ❌ HARDCODED SENTIMENT VALUES

**Current Output:**
```json
{
  "sentiment": {"label": "NEUTRAL", "score": 0.5},
  "sentiment_label": "NEUTRAL",
  "sentiment_score": 0.5
}
```

**Problem:**
- EVERY scene has identical sentiment: NEUTRAL 0.5
- Impossible that all scenes have exactly 0.5 sentiment
- Indicates placeholder/default value

**Expected Behavior:**
- Varying sentiment scores across scenes
- Some positive (> 0.5), some negative (< 0.5)
- Labels: POSITIVE, NEGATIVE, NEUTRAL

**Investigation:**
1. Check if sentiment analyzer is actually running
2. Look for hardcoded return value
3. Verify sentiment model is loaded
4. Check for exception catching returning default

---

### 5. ❌ MISSING DATABASE TABLES

**Current Schema:**
```sql
embeddings (hash, faiss_id, source_path, modality, ...)
links (parent_hash, child_hash, relation, ...)
scenes (id, video_hash, start, end, meta, ...)
segments (id, video_hash, start, end, speaker, meta, ...)
summaries (id, summary_type, category, content, ...)
```

**Missing Critical Tables:**

#### A) Transcriptions Table
```sql
CREATE TABLE transcriptions (
    id TEXT PRIMARY KEY,
    scene_id TEXT,
    segment_id TEXT,
    video_hash TEXT,
    speaker TEXT,
    start_time REAL,
    end_time REAL,
    text TEXT,  -- ❌ THIS IS MISSING
    confidence REAL,
    language TEXT,
    created_at TEXT,
    FOREIGN KEY (scene_id) REFERENCES scenes(id),
    FOREIGN KEY (segment_id) REFERENCES segments(id)
);
```

**Currently:** Transcript text buried in scene metadata JSON - can't query it!

#### B) Image Analysis Table
```sql
CREATE TABLE image_analysis (
    id TEXT PRIMARY KEY,
    scene_id TEXT,
    frame_path TEXT,
    caption TEXT,
    detected_objects JSON,
    detected_faces JSON,
    ocr_text TEXT,
    tags JSON,
    created_at TEXT,
    FOREIGN KEY (scene_id) REFERENCES scenes(id)
);
```

**Currently:** All image data in scene metadata JSON blob

#### C) Emotions Table
```sql
CREATE TABLE emotions (
    id TEXT PRIMARY KEY,
    scene_id TEXT,
    segment_id TEXT,
    timestamp REAL,
    emotion TEXT,  -- angry, happy, sad, etc.
    intensity REAL,
    source TEXT,  -- 'audio' or 'visual'
    created_at TEXT,
    FOREIGN KEY (scene_id) REFERENCES scenes(id)
);
```

**Currently:** No emotion storage at all!

#### D) Entities Table
```sql
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    entity_type TEXT,  -- PERSON, ORG, LOCATION, DATE, etc.
    name TEXT,
    mentions JSON,  -- [{scene_id, timestamp, context}, ...]
    first_mention_scene TEXT,
    last_mention_scene TEXT,
    created_at TEXT
);
```

**Currently:** Empty arrays in scene metadata

---

### 6. ❌ SEGMENTS MISSING TEXT FIELD

**Current Segments Table:**
```sql
CREATE TABLE segments (
    id TEXT,
    video_hash TEXT,
    start REAL,
    end REAL,
    speaker TEXT,  -- e.g., "SPEAKER_00"
    meta TEXT,     -- JSON: {"speaker": "SPEAKER_00"}
    created_at TEXT
);
```

**Problem:**
- Has speaker timing but NO transcript text
- Can't query "what did SPEAKER_00 say in this segment"
- Text exists in scene metadata but not linked to segments

**Fix:**
```sql
ALTER TABLE segments ADD COLUMN text TEXT;
ALTER TABLE segments ADD COLUMN confidence REAL;
ALTER TABLE segments ADD COLUMN language TEXT;
```

---

### 7. ⚠️ ORPHANED EMBEDDINGS

**Finding:** 39 embeddings have `scene_id = NULL`

**Impact:**
- Can't find embeddings for specific scenes
- Embeddings exist but aren't linked to content
- Breaks semantic search within scenes

**Fix Required:**
1. Update embedding creation to set scene_id
2. Backfill existing embeddings with scene_id
3. Add NOT NULL constraint after fix

**Query:**
```sql
UPDATE embeddings 
SET scene_id = (
    SELECT s.id FROM scenes s 
    WHERE embeddings.source_path LIKE '%scene_' || 
          substr(s.meta, instr(s.meta, '"index": ') + 9, 4) || '%'
)
WHERE scene_id IS NULL;
```

---

### 8. ❌ NO OUTPUT ARTIFACTS

**Missing Files:**

#### Per-Scene JSON Output
Expected: `output/sample/scene_0000.json`
```json
{
  "scene_id": "4070c7260c0be1d2...",
  "time": {"start": 0.0, "end": 2.0, "duration": 2.0},
  "visual": {
    "keyframe": "scene_0000.jpg",
    "caption": "a man in a wheelchair...",
    "objects": [...],
    "faces": [...]
  },
  "audio": {
    "file": "scene_0000.wav",
    "transcript": "That's what we want to do.",
    "speakers": ["SPEAKER_00", "SPEAKER_01"],
    "emotions": {...}
  },
  "analysis": {
    "sentiment": {...},
    "entities": [...],
    "tags": [...]
  }
}
```
**Actual:** ❌ No files created

#### Transcript Text Files
Expected: `output/sample/transcripts/scene_0000.txt`
```
[0.00 - 2.00] SPEAKER_00: That's what we want to do.
[0.59 - 0.77] SPEAKER_01: [brief interjection]
```
**Actual:** ❌ No files created

#### Video Summary
Expected: `output/sample/summary.md`
**Actual:** ❌ No file created

---

### 9. ❌ MISSING ENTITY EXTRACTION

**Configuration:**
```yaml
knowledge_graph:
  enabled: true
  entity_extraction:
    enabled: true
    min_confidence: 0.5
```

**Expected:**
From transcript "to make music that can be the soundtrack to people's":
- Extract: "music" (CONCEPT)
- Extract: "people" (GENERIC_PERSON)
- Extract: "soundtrack" (CONCEPT)

**Actual:**
```json
{
  "entities": [],  // ❌ EMPTY
  "tags": []       // ❌ EMPTY
}
```

**Investigation:**
1. Check if NER (Named Entity Recognition) model is loaded
2. Verify entity extraction step is called
3. Check for spaCy or transformers NER integration
4. Look for silent failures

---

### 10. ❌ NO MUSIC/AUDIO EVENT DETECTION

**Current Output:**
```json
{
  "music_events": [],
  "music_events_meta": null
}
```

**Missing Functionality:**
- Music vs speech classification
- Silence detection
- Background noise analysis
- Audio quality metrics

**Expected:**
```json
{
  "music_events": [
    {"type": "background_music", "start": 0.5, "end": 1.8, "confidence": 0.7}
  ],
  "audio_quality": {"snr": 15.2, "clarity": "good"},
  "silence_segments": []
}
```

---

### 11. ❌ NO TEMPORAL REFERENCE EXTRACTION

**Current Output:**
```json
{
  "time_hints": [],
  "time_hints_meta": null
}
```

**Expected Functionality:**
Parse temporal references from transcripts:
- "in 1987" → DATE: 1987
- "next week" → RELATIVE_TIME: +1 week
- "three hours ago" → RELATIVE_TIME: -3 hours

**Use Case:**
For home movies: "this was when I was born" → link to birth date entity

---

### 12. ❌ NO FACE → SPEAKER LINKING

**Current State:**
- Face encodings extracted: ✅
- Speaker IDs assigned: ✅
- Linking between them: ❌

**Missing Functionality:**
```json
{
  "speakers": {
    "SPEAKER_00": {
      "face_id": "face_abc123",
      "name": null,  // could be populated later
      "total_speech_time": 8.5,
      "appearances": [0, 1, 2, 5, 7]  // scene indices
    }
  }
}
```

**Implementation Needed:**
1. Track which frames have faces
2. Correlate face appearance with speaker activity
3. Build face → speaker → name graph

---

### 13. ⚠️ SPEAKER SEGMENT OVERLAP ISSUES

**Finding:** Scene 0 has 17 speaker segments for 2-second scene

**Data:**
```
SPEAKER_00: 0.03s - 2.07s
SPEAKER_01: 0.03s - 1.90s
SPEAKER_00: 0.03s - 3.02s  ❌ Extends past scene end!
SPEAKER_00: 0.03s - 2.11s
... (13 more)
```

**Problems:**
1. Many redundant/overlapping segments
2. Some segments extend past scene boundaries
3. Difficult to determine actual speaker turns

**Likely Cause:**
- Diarization running on full audio, not scene clips
- Segments not being clipped to scene boundaries
- Post-processing step missing

---

### 14. ❌ NO SCENE-TO-SCENE RELATIONSHIPS

**Current State:**
- Scenes exist independently
- No links between scenes
- No narrative flow tracking

**Missing:**
```sql
CREATE TABLE scene_relationships (
    scene_id_1 TEXT,
    scene_id_2 TEXT,
    relationship_type TEXT,  -- 'continues', 'references', 'contrasts', etc.
    confidence REAL,
    evidence JSON,
    FOREIGN KEY (scene_id_1) REFERENCES scenes(id),
    FOREIGN KEY (scene_id_2) REFERENCES scenes(id)
);
```

**Use Cases:**
- "Scene 5 continues the topic from Scene 2"
- "Scene 8 shows the same location as Scene 3"
- "Scene 10 answers question raised in Scene 6"

---

## Prioritized Fix List

### 🔴 CRITICAL (Breaks Core Functionality)

1. **Enable Emotion Analysis**
   - Files to check: emotion analyzer step
   - Look for: Silent exceptions, model loading issues
   - Test: Verify emotion data appears in scene metadata

2. **Fix Incomplete Scene Processing**
   - Why only 10/15 scenes?
   - Remove hard limits
   - Ensure all detected scenes are fully processed

3. **Surface OCR Text to Metadata**
   - Add `ocr_text` field to scene metadata
   - Store raw text, not just embeddings

### 🟡 HIGH (Core Features Not Working)

4. **Fix Sentiment Analysis**
   - Remove hardcoded 0.5 values
   - Verify actual sentiment model inference

5. **Create Transcriptions Table**
   - Extract text from scene metadata
   - Build structured table for querying

6. **Add Text to Segments**
   - Link transcript text to speaker segments
   - Enable "what did this speaker say" queries

7. **Fix Orphaned Embeddings**
   - Set scene_id for all embeddings
   - Enable scene-specific semantic search

### 🟢 MEDIUM (Enhanced Functionality)

8. **Create Image Analysis Table**
   - Extract from scene metadata JSON
   - Enable "find scenes with X object" queries

9. **Implement Entity Extraction**
   - Load NER model
   - Extract entities from transcripts
   - Build entity knowledge graph

10. **Create Output Artifacts**
    - Generate per-scene JSON files
    - Create transcript text files
    - Build summary documents

### 🔵 LOW (Advanced Features)

11. **Implement Music Detection**
    - Classify audio segments
    - Detect music vs speech vs silence

12. **Add Temporal Reference Extraction**
    - Parse dates/times from transcripts
    - Link to timeline

13. **Build Face → Speaker Links**
    - Correlate face detection with speaker activity
    - Track person across scenes

14. **Create Scene Relationships**
    - Detect topic continuity
    - Build narrative structure

15. **Fix Speaker Segment Overlap**
    - Clip segments to scene boundaries
    - Deduplicate overlapping segments

---

## Testing Checklist

After fixes, verify:

- [ ] All 15 scenes have extracted frames
- [ ] All 15 scenes have extracted audio
- [ ] Emotion data present in scene metadata
- [ ] OCR text visible in scene metadata (when text present)
- [ ] Sentiment varies across scenes (not all 0.5)
- [ ] Transcriptions table populated with text
- [ ] Segments table has text field populated
- [ ] All embeddings have scene_id
- [ ] Output JSON files created per scene
- [ ] Transcript TXT files created
- [ ] Entity extraction finds entities in transcripts
- [ ] Speaker segments don't overlap excessively
- [ ] No segments extend past scene boundaries

---

## Code Files to Investigate

### Priority 1: Emotion & OCR
```
steps/audio/emotion_analyzer.py
steps/image/ocr_extractor.py
steps/image/image_analyzer.py
```

### Priority 2: Scene Processing
```
agents/ingestion/video_processor.py
agents/ingestion/scene_detector.py
pipelines/ingest_multimodal.py
```

### Priority 3: Database Schema
```
lib/db.py
lib/storage.py
materializers/scene_materializer.py
```

### Priority 4: Entity & Sentiment
```
steps/nlp/entity_extractor.py
steps/nlp/sentiment_analyzer.py
steps/audio/transcriber.py
```

---

## Expected vs Actual Output Summary

| Feature | Expected | Actual | Status |
|---------|----------|---------|--------|
| Scene Detection | ✅ | ✅ | ✅ Working |
| Frame Extraction | 15 frames | 10 frames | ⚠️ Partial |
| Audio Clips | 15 clips | 10 clips | ⚠️ Partial |
| Transcription | ✅ | ✅ | ✅ Working |
| Image Captions | ✅ | ✅ | ✅ Working |
| Object Detection | ✅ | ✅ | ✅ Working |
| Face Detection | ✅ | ✅ | ✅ Working |
| Speaker Diarization | ✅ | ✅ (messy) | ⚠️ Needs refinement |
| Emotion Analysis | ✅ | ❌ | ❌ Not working |
| OCR Text | ✅ | ⚠️ (embedded only) | ⚠️ Partial |
| Sentiment | Varied scores | All 0.5 | ❌ Hardcoded |
| Entity Extraction | ✅ | ❌ | ❌ Not working |
| Music Detection | ✅ | ❌ | ❌ Not working |
| Time Hints | ✅ | ❌ | ❌ Not working |
| Face → Speaker Link | ✅ | ❌ | ❌ Not working |
| Scene Relationships | ✅ | ❌ | ❌ Not working |
| Embeddings | ✅ | ✅ (orphaned) | ⚠️ Partial |
| Transcription Table | ✅ | ❌ | ❌ Missing |
| Image Analysis Table | ✅ | ❌ | ❌ Missing |
| Emotions Table | ✅ | ❌ | ❌ Missing |
| Output JSON Files | ✅ | ❌ | ❌ Missing |
| Transcript Files | ✅ | ❌ | ❌ Missing |
| Summary Generation | ✅ | ❌ | ❌ Missing |

**Working:** 7 / 22 features (32%)  
**Partial:** 4 / 22 features (18%)  
**Not Working:** 11 / 22 features (50%)

---

## Conclusion

The multimodal ingestion pipeline has a **strong foundation** with scene detection, transcription, and visual analysis working well. However, **50% of configured features are not executing**, with several critical components silently failing:

**Immediate Action Required:**
1. Enable emotion analysis (configured but not running)
2. Fix scene processing to handle all 15 scenes
3. Surface OCR text to be human-readable
4. Implement actual sentiment scoring
5. Create structured database tables for querying

**Good News:**
- Core pipeline architecture is sound
- Data is being captured (even if not perfectly organized)
- Embeddings are being generated across modalities
- Knowledge graph structure exists

**Next Session Priority:**
Start with emotion analysis - this is a configured feature that should be working but isn't. Finding why it's failing will likely reveal patterns affecting other missing features.
