<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_CANONICAL_POINTER: docs/guides/llm/LLM_INFRASTRUCTURE.md -->
<!-- DOC_ARCHIVED_ON: 2026-07-10 -->

⚠ Historical planning document.

Contains legacy absolute path examples reflecting the system state at time of writing.
Active runtime documentation uses environment abstractions:
<project_root>, <GOODQ_DATA_ROOT>, <GOODQ_WSL_WORKSPACE>.

# 🚀 LLM INTEGRATION - PHASE 1 IMPLEMENTATION PLAN

> ARCHIVE / NON-CANONICAL / DO NOT COPY PATHS

> ⚠ Historical planning document — contains legacy path references.

**Created:** 2025-11-08  
**Mission:** Enable LLM intelligence throughout GoodQ pipeline  
**Starting Status:** LLMs available but DISABLED in pipeline

---

## 📊 CURRENT STATE ASSESSMENT

### ✅ What We Have
1. **LM Studio Running** - localhost:1234 with qwen2.5-7b-instruct
2. **Scene Summarization Code** - EXISTS but `use_llm=False` (line 56 in apply_scene_summaries.py)
3. **Model Caches** - Scattered across THREE locations:
   - `<GOODQ_DATA_ROOT>\models\` (primary HuggingFace cache)
   - duplicate caches under older local data roots
   - Various tool directories

4. **Agent Framework** - Installed but dormant (goodq_agents conda env)
5. **Pipeline Steps** - 30+ processing steps, NONE using LLMs currently

### ❌ Critical Gaps
1. **No LLM calls in ingestion pipeline**
2. **Scene summarization disabled**
3. **No video-level summarization**
4. **No contextual relationship extraction**
5. **No agent self-healing**
6. **No learning from processing**

---

## 🎯 PHASE 1: ENABLE CORE LLM FEATURES

### Step 1: Unify Model Cache (10 min)
**Problem:** Models scattered across `<GOODQ_DATA_ROOT>\models`, duplicate caches, and tool dirs  
**Solution:** Consolidate to single cache, set environment variables

**Actions:**
```powershell
# Set HuggingFace cache to unified location
$env:HF_HOME = "<GOODQ_DATA_ROOT>\models"
$env:TRANSFORMERS_CACHE = "<GOODQ_DATA_ROOT>\models\transformers"
$env:HF_DATASETS_CACHE = "<GOODQ_DATA_ROOT>\models\datasets"

# Add to .env.local permanently
@"
HF_HOME=<GOODQ_DATA_ROOT>/models
TRANSFORMERS_CACHE=<GOODQ_DATA_ROOT>/models/transformers
HF_DATASETS_CACHE=<GOODQ_DATA_ROOT>/models/datasets
TORCH_HOME=<GOODQ_DATA_ROOT>/models/torch
"@ | Add-Content <project_root>\.env.local
```

**Verification:**
- Check that models load from `<GOODQ_DATA_ROOT>\models` only
- Archive duplicate caches into an environment-appropriate archive location

---

### Step 2: Enable Scene Summarization LLM (5 min)
**File:** `<project_root>\apply_scene_summaries.py` (Line 56)

**Change:**
```python
# BEFORE
summary_text = generate_scene_summary(scene_meta, cfg, use_llm=False)

# AFTER
summary_text = generate_scene_summary(scene_meta, cfg, use_llm=True)
```

**Test:**
```powershell
cd <project_root>
python apply_scene_summaries.py

# Verify LLM summaries in the epoch-scoped memory database
python -c "from pathlib import Path; import sqlite3, json; db=Path('<GOODQ_DATA_ROOT>')/'GoodQ_Data'/'epochs'/'<epoch>'/'memory.db'; c=sqlite3.connect(db).cursor(); c.execute('SELECT content FROM summaries WHERE category=\"scene_summary\" LIMIT 1'); print(json.dumps(json.loads(c.fetchone()[0]), indent=2))"
```

**Expected Output:** Natural language summary instead of template format

---

### Step 3: Integrate Scene Summarization into Pipeline (15 min)
**Files to modify:**
- `steps/video_ingest/step.py` (or main ingestion orchestrator)
- `pipelines/video_ingestion_pipeline.py` (if exists)

**Find current pipeline entry point:**
```powershell
cd <project_root>
# Search for main ingestion entry point
Get-ChildItem -Recurse -Include "*.py" | Select-String "video_scene_detect" -List | Select-Object Path
Get-ChildItem -Recurse -Include "*.py" | Select-String "def run_ingestion" -List | Select-Object Path
```

**Integration Code (add after scene detection):**
```python
# After scene detection and metadata collection
from steps.common.scene_summarizer import generate_scene_summary
from steps.common.memory import append_long_term_summary

# For each processed scene
for scene in scenes:
    scene_meta = collect_scene_metadata(scene)  # Existing
    
    # Generate LLM summary
    summary_text = generate_scene_summary(
        scene_meta, 
        cfg, 
        use_llm=cfg.get('llm', {}).get('scene_summarization', True)
    )
    
    # Store summary
    summary_data = {
        'scene_id': scene_id,
        'summary': summary_text,
        'index': scene_meta['index'],
        'start': scene_meta['start'],
        'end': scene_meta['end']
    }
    append_long_term_summary(cfg, summary_data, category='scene_summary')
```

---

### Step 4: Update Config for LLM Control (5 min)
**File:** `<project_root>\configs\config.yaml`

**Add LLM feature flags:**
```yaml
llm:
  api_url: http://localhost:1234/v1/chat/completions
  model_id: LM_STUDIO_GOODQ
  enabled: true  # Master enable switch
  timeout: 30  # Seconds per LLM call
  
  # Feature flags
  features:
    scene_summarization: true
    video_summarization: false  # Phase 2
    relationship_extraction: false  # Phase 2
    emotion_arc_analysis: false  # Phase 3
    self_healing: false  # Phase 4
  
  # Performance settings
  temperature: 0.3
  max_tokens: 200  # Scene summaries are concise
  batch_size: 5  # Process 5 scenes in parallel
```

---

### Step 5: Create Video-Level Summarization Step (30 min)
**New file:** `<project_root>\steps\video_summarizer\step.py`

**Implementation:**
```python
"""
Video-Level Summarization Step
Generates cohesive narrative from all scene summaries
"""
import sqlite3
import json
import requests
from typing import Dict, Any, List

def generate_video_summary_llm(cfg: Dict, video_id: str, db_path: str) -> str:
    """
    Generate video-level summary from all scene summaries
    """
    # Fetch all scene summaries for this video
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        SELECT content FROM summaries 
        WHERE category='scene_summary' 
        ORDER BY id
    """)
    
    scene_summaries = []
    for (content_json,) in c.fetchall():
        content = json.loads(content_json)
        scene_summaries.append(content.get('summary', ''))
    
    # Get video metadata
    c.execute("SELECT meta FROM videos WHERE id=?", (video_id,))
    video_meta = json.loads(c.fetchone()[0])
    conn.close()
    
    # Build prompt
    scenes_text = "\n\n".join([
        f"Scene {i+1}: {summary}" 
        for i, summary in enumerate(scene_summaries)
    ])
    
    prompt = f"""Analyze this video and generate a cohesive 2-3 paragraph summary:

VIDEO METADATA:
- Duration: {video_meta.get('duration', 0):.1f}s ({len(scene_summaries)} scenes)
- File: {video_meta.get('filename', 'Unknown')}

SCENE-BY-SCENE BREAKDOWN:
{scenes_text}

Generate a natural, flowing summary that:
1. Captures the overall narrative or purpose
2. Highlights key moments and transitions
3. Identifies main themes or subjects
4. Describes the emotional tone/arc

VIDEO SUMMARY:"""
    
    # Call LLM
    llm_config = cfg.get('llm', {})
    api_url = llm_config.get('api_url')
    
    response = requests.post(
        api_url,
        json={
            "messages": [
                {"role": "system", "content": "You are a video content analyst. Create coherent, informative video summaries."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.5,
            "max_tokens": 500,
        },
        timeout=30
    )
    
    if response.status_code == 200:
        result = response.json()
        summary = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        return summary
    
    return "Video summary generation failed."


def run_step(cfg: Dict, video_id: str) -> Dict[str, Any]:
    """
    Execute video summarization step
    """
    db_path = cfg['paths']['db_path']
    
    # Generate video summary
    video_summary = generate_video_summary_llm(cfg, video_id, db_path)
    
    # Store in database
    conn = sqlite3.connect(db_path)
    conn.execute("""
        INSERT OR REPLACE INTO summaries (category, content, created_at)
        VALUES ('video_summary', ?, datetime('now'))
    """, (json.dumps({
        'video_id': video_id,
        'summary': video_summary
    }),))
    conn.commit()
    conn.close()
    
    return {
        'success': True,
        'summary': video_summary,
        'video_id': video_id
    }
```

**Also create:** `<project_root>\steps\video_summarizer\__init__.py`
```python
from .step import run_step
__all__ = ['run_step']
```

---

### Step 6: Test Full LLM Pipeline (30 min)

**Test Script:** Create `<project_root>\test_llm_pipeline.py`
```python
#!/usr/bin/env python3
"""
Test LLM Integration End-to-End
"""
import sqlite3
import json
from pathlib import Path

# Test 1: Check LM Studio connectivity
print("="*80)
print("TEST 1: LM Studio Connectivity")
print("="*80)

import requests
try:
    response = requests.get("http://localhost:1234/v1/models", timeout=5)
    if response.status_code == 200:
        models = response.json()
        print("✅ LM Studio is running")
        print(f"   Available models: {len(models.get('data', []))}")
    else:
        print("❌ LM Studio returned error")
        exit(1)
except Exception as e:
    print(f"❌ Cannot connect to LM Studio: {e}")
    exit(1)

# Test 2: Scene summarization with LLM
print("\n" + "="*80)
print("TEST 2: Scene Summarization (LLM Mode)")
print("="*80)

cfg = {
    'paths': {'db_path': '<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/<epoch>/memory.db'},
    'llm': {'api_url': 'http://localhost:1234/v1/chat/completions'}
}

conn = sqlite3.connect(cfg['paths']['db_path'])
c = conn.cursor()
c.execute("SELECT id, meta FROM scenes LIMIT 1")
scene_id, meta_json = c.fetchone()
scene_meta = json.loads(meta_json)

from steps.common.scene_summarizer import generate_scene_summary

llm_summary = generate_scene_summary(scene_meta, cfg, use_llm=True)
template_summary = generate_scene_summary(scene_meta, cfg, use_llm=False)

print(f"\n📊 Scene {scene_meta.get('index', 0)}:")
print(f"\n🤖 LLM Summary:")
print(f"   {llm_summary}")
print(f"\n📝 Template Summary:")
print(f"   {template_summary[:200]}...")

if llm_summary != template_summary:
    print("\n✅ LLM generated unique summary (not template)")
else:
    print("\n⚠️  LLM summary matches template (possible fallback)")

# Test 3: Video summarization
print("\n" + "="*80)
print("TEST 3: Video Summarization")
print("="*80)

c.execute("SELECT id FROM videos LIMIT 1")
video_row = c.fetchone()
if video_row:
    video_id = video_row[0]
    from steps.video_summarizer.step import run_step
    
    result = run_step(cfg, video_id)
    
    if result['success']:
        print("✅ Video summary generated")
        print(f"\n📄 Video Summary:")
        print(f"   {result['summary'][:300]}...")
    else:
        print("❌ Video summarization failed")
else:
    print("⚠️  No videos in database to test")

conn.close()

print("\n" + "="*80)
print("LLM PIPELINE TEST COMPLETE")
print("="*80)
```

**Run test:**
```powershell
cd <project_root>
python test_llm_pipeline.py
```

---

## 🔍 VERIFICATION CHECKLIST

### Scene-Level LLMs
- [ ] LM Studio is responding (http://localhost:1234/v1/models)
- [ ] Scene summarization uses LLM (not template fallback)
- [ ] Summaries are natural language (2-3 sentences)
- [ ] Summaries stored in memory.db under category='scene_summary'

### Video-Level LLMs
- [ ] Video summarization step exists and runs
- [ ] Video summary aggregates all scene summaries
- [ ] Summary captures narrative arc and themes
- [ ] Stored in memory.db under category='video_summary'

### Integration
- [ ] Pipeline calls scene summarization automatically
- [ ] Video summarization runs after all scenes processed
- [ ] Config flags control LLM features (enable/disable)

### Performance
- [ ] Scene summary generation < 5 seconds per scene
- [ ] No memory leaks or GPU crashes
- [ ] Graceful fallback to template if LLM unavailable

---

## 🚦 SUCCESS CRITERIA

**PHASE 1 COMPLETE WHEN:**
1. ✅ Scene summaries use LLM by default
2. ✅ Video summaries generated and stored
3. ✅ All summaries queryable from memory.db
4. ✅ Test on sample.mp4 shows LLM-generated content
5. ✅ No performance degradation (< 1 min added per video)

---

## 📈 EXPECTED IMPROVEMENTS

### Before Phase 1:
```json
{
  "scene": 3,
  "caption": "a woman sitting at a table",
  "objects": ["person", "table"],
  "transcript": "So we started the band in 2005..."
}
```

### After Phase 1:
```json
{
  "scene": 3,
  "llm_scene_summary": "Scene 3 shows an interview segment where the speaker reminisces about forming their band in 2005. The casual coffee table setting and positive emotional tone suggest a relaxed podcast-style conversation.",
  "llm_video_summary": "This video captures a podcast interview with two band members discussing their creative journey from 2005 to present. The conversation flows through multiple topics including formation, creative process, and memorable performances, maintaining an upbeat and nostalgic tone throughout.",
  "caption": "a woman sitting at a table",
  "objects": ["person", "table"],
  "transcript": "So we started the band in 2005..."
}
```

---

## ⏭️ NEXT PHASES (Preview)

### Phase 2: Knowledge Graph LLM Enhancement (2-4 hours)
- Semantic relationship extraction
- Context-aware entity linking
- Family relationship mapping

### Phase 3: Emotion Arc Analysis (2-4 hours)
- Track emotional journey across scenes
- Identify emotional peaks and transitions
- Contextual emotion interpretation

### Phase 4: Agent Self-Healing (4-8 hours)
- Pipeline monitoring agent
- Failure detection and recovery
- Learning from processing errors

### Phase 5: Multi-Modal Context Integration (4-8 hours)
- Cross-reference visual, audio, text insights
- Temporal narrative threading
- Family archive-specific analysis

---

## 🛠️ TROUBLESHOOTING

### Issue: LM Studio not responding
**Solution:**
```powershell
# Check if LM Studio is running
curl http://localhost:1234/v1/models

# Restart LM Studio if needed
# Load model: qwen2.5-7b-instruct
```

### Issue: Scene summaries still using templates
**Solution:**
```python
# Check apply_scene_summaries.py line 56
# Must be: use_llm=True
```

### Issue: Out of memory during LLM calls
**Solution:**
```yaml
# In config.yaml, reduce batch size
llm:
  batch_size: 1  # Process one at a time
```

### Issue: LLM summaries are too long
**Solution:**
```yaml
# In config.yaml, reduce max_tokens
llm:
  max_tokens: 100  # Shorter summaries
```

---

## 📝 IMPLEMENTATION LOG

**Start Time:** _______________  
**Completed Steps:** _______________  
**Issues Encountered:** _______________  
**Final Status:** _______________  

---

**Ready to proceed with implementation?** 🚀
