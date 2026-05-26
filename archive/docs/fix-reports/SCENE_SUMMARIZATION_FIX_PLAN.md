<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_ARCHIVED_ON: 2026-02-12 -->

# Scene Summarization Fix - Implementation Plan
**Issue:** Scene summaries not being generated and saved to database
**Priority:** CRITICAL
**Complexity:** MEDIUM

## Solution Architecture

### Option 1: LLM-Based Summarization (RECOMMENDED)
Generate rich, natural language summaries using the local LLM.

**Pros:**
- High quality, contextual summaries
- Can synthesize multimodal data (vision + audio + emotions)
- Flexible and extensible

**Cons:**
- Requires LLM API call (adds latency)
- Depends on LLM being available

### Option 2: Template-Based Summarization (FALLBACK)
Generate summaries from metadata using templates.

**Pros:**
- Fast and deterministic
- No external dependencies
- Always works

**Cons:**
- Less natural language
- More rigid format

## Implementation Steps

### Step 1: Create Scene Summarization Function

**File:** `steps/common/scene_summarizer.py`

```python
def generate_scene_summary(
    scene_meta: Dict[str, Any],
    cfg: Dict[str, Any],
    use_llm: bool = True
) -> str:
    """
    Generate natural language summary of a scene.
    
    Args:
        scene_meta: Rich scene metadata
        cfg: Config dict
        use_llm: Use LLM if available, else template
        
    Returns:
        Natural language summary string
    """
```

### Step 2: Integrate into Pipeline

**Modify:** `steps/common/memory.py` function `register_scene_bundle()`

Add after line 348 (after upsert_scene):
```python
# Generate and save scene summary
from steps.common.scene_summarizer import generate_scene_summary
summary_text = generate_scene_summary(scene_meta, cfg)
store_short_term_summary(
    cfg,
    {"scene_id": scene_id, "summary": summary_text, "metadata": scene_meta},
    category="scene_summary"
)
```

### Step 3: Test and Validate

1. Run clean ingestion on sample.mp4
2. Verify 16 summaries created
3. Check summary quality
4. Test retrieval in chat

## Implementation

### Template-Based Approach (Quick Win)

**Summary Template:**
```
Scene {index} ({start:.1f}s - {end:.1f}s, {duration:.1f}s):
{caption}

Audio: {transcript}
Speakers: {speakers}
Sentiment: {sentiment_label} ({sentiment_score:.0%})
Emotions: {dominant_emotion}
Objects: {objects}
Tags: {tags}
```

### LLM-Based Approach (Full Solution)

**Prompt Template:**
```
Analyze this video scene and generate a concise, informative summary:

Visual: {caption}
Objects detected: {objects}
Faces: {face_count}

Audio transcript: {transcript}
Speakers: {speakers}
Sentiment: {sentiment_label} ({sentiment_score:.0%})
Emotions: {emotions}

Time: {start:.1f}s - {end:.1f}s ({duration:.1f}s)

Generate a 2-3 sentence summary that captures what's happening in this scene, who's speaking, and the emotional tone.
```

## Testing Plan

1. **Unit Test:** Test summary generation with sample metadata
2. **Integration Test:** Run full ingestion, verify summaries created
3. **Quality Test:** Review summary quality for accuracy and usefulness
4. **Performance Test:** Measure impact on ingestion time

## Success Criteria

- ✅ 16/16 scenes have summaries in database
- ✅ Summaries are accurate and informative  
- ✅ Summaries stored with correct category
- ✅ Summaries retrievable via query
- ✅ No significant performance degradation

## Rollout Strategy

1. **Phase 1:** Implement template-based fallback
2. **Phase 2:** Add LLM-based summarization
3. **Phase 3:** Make LLM the default with template fallback
4. **Phase 4:** Add summary caching/optimization

## Files to Create/Modify

### Create:
- `steps/common/scene_summarizer.py` (new)
- `tests/test_scene_summarizer.py` (new)

### Modify:
- `steps/common/memory.py` (add summary generation)
- `cli/run_ingestion.py` (optional: add --no-summarize flag)

## Estimated Effort

- Template approach: 30 minutes
- LLM approach: 1-2 hours
- Testing: 30 minutes
- **Total: 2-3 hours**
