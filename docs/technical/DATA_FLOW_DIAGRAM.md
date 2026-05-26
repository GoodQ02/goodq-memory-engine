<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: REFERENCE_ONLY -->
<!-- DOC_CANONICAL_POINTER: docs/architecture/SYSTEM_ARCHITECTURE.md -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

# 📊 GoodQ Data Flow - Current vs. Fixed

> Historical architecture snapshot. Older API examples in this document, including the legacy `GET /api/search?q=...` surface, are preserved to explain the original repair narrative and should not be treated as the active contract. Current search/retrieval truth lives under `POST /api/search/multimodal`, `GET /api/search/text`, `GET /api/search/visual`, and the router-backed scene surfaces documented in `docs/reference/API.md`.

## 🔴 CURRENT STATE (Broken)

```
┌─────────────────────────────────────────────────────────────────┐
│                         VIDEO FILE                              │
│                      (1987_1988.mp4)                           │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
            ┌────────────────┐
            │  Video Extract │
            │  (FFmpeg)      │
            └───────┬────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
   ┌─────────┐            ┌─────────┐
   │ Frames  │            │  Audio  │
   │ (JPG)   │            │  (WAV)  │
   └────┬────┘            └────┬────┘
        │                      │
        ▼                      ▼
   ┌─────────┐            ┌─────────┐
   │ Image   │            │ Audio   │
   │ Caption │            │Transcribe│
   └────┬────┘            └────┬────┘
        │                      │
        ▼                      ▼
   ┌─────────┐            ┌─────────┐
   │ Object  │            │Sentiment│
   │ Detect  │            │Analysis │
   └────┬────┘            └────┬────┘
        │                      │
        ▼                      ▼
   ┌─────────┐            ┌─────────┐
   │   OCR   │            │Embedding│
   └────┬────┘            └────┬────┘
        │                      │
        │     ❌ NO SAVE! ❌   │
        │                      │
        ▼                      ▼
   ┌─────────────────────────────┐
   │     Results Discarded!      │
   │   (Only kept in pipeline    │
   │    memory, not database)    │
   └─────────────────────────────┘
                │
                ▼
        ┌───────────────┐
        │  Memory DB    │
        │  (EMPTY!)     │
        └───────────────┘
```

**Problem:** All the analysis happens but results are never written to database!

---

## ✅ FIXED STATE (After Implementation)

```
┌─────────────────────────────────────────────────────────────────┐
│                         VIDEO FILE                              │
│                      (1987_1988.mp4)                           │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
            ┌────────────────┐
            │  Video Extract │
            │  (FFmpeg)      │
            └───────┬────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
   ┌─────────┐            ┌─────────┐
   │ Frames  │            │  Audio  │
   │ (JPG)   │            │  (WAV)  │
   └────┬────┘            └────┬────┘
        │                      │
        │    ✅ Scene Created  │
        │    in Memory DB      │
        │                      │
        ▼                      ▼
   ┌─────────┐            ┌─────────┐
   │ Image   │            │ Audio   │
   │ Caption │◄──────────►│Transcribe│
   └────┬────┘  memory    └────┬────┘
        │      _writer.py       │
        │ save_caption()        │ save_transcription()
        │                       │
        ▼                       ▼
   ┌──────────────────────────────┐
   │    Memory Writer             │
   │  (Centralized Saver)         │
   └────────────┬─────────────────┘
                │
                ▼
   ┌─────────────────────────────┐
   │       Memory DB              │
   │                              │
   │  scenes: ✅ Data!            │
   │    - caption                 │
   │    - objects                 │
   │    - ocr_text                │
   │    - transcription           │
   │    - sentiment               │
   │    - emotions                │
   │                              │
   │  embeddings: ✅ Data!        │
   │  knowledge_graph: ✅ Data!   │
   └────────────┬─────────────────┘
                │
                ▼
         ┌─────────────┐
         │  FastAPI    │
         │  (Returns   │
         │   data!)    │
         └──────┬──────┘
                │
                ▼
         ┌─────────────┐
         │  Command    │
         │  Center     │
         │  (Shows     │
         │   stats!)   │
         └─────────────┘
```

**Solution:** Memory writer intercepts results and saves them!

---

## 🔧 THE FIX (Code Level)

### Before (Current)
```python
# steps/image_caption/step.py

def image_caption(scene_id: str, frame_path: str):
    """Generate caption for frame"""
    
    # Load image
    image = Image.open(frame_path)
    
    # Generate caption
    caption = model.generate(image)
    
    # Return it (but not saved!)
    return caption
    
    # ❌ Result lost after step completes!
```

### After (Fixed)
```python
# steps/image_caption/step.py
from steps.common.memory_writer import save_step_results  # ← Add import

def image_caption(scene_id: str, frame_path: str):
    """Generate caption for frame"""
    
    # Load image
    image = Image.open(frame_path)
    
    # Generate caption
    caption = model.generate(image)
    
    # ✅ SAVE IT!
    save_step_results(scene_id, 'caption', caption)  # ← Add this line
    
    # Still return for pipeline
    return caption
    
    # ✅ Result now persisted in database!
```

**That's it!** Just 2 lines added (import + save call).

---

## 🎯 IMPACT OF FIX

### Before
```
API Query: "Find scenes with people"

Response: {
    "results": [],
    "message": "No data in database"
}
```

### After
```
API Query: "Find scenes with people"

Response: {
    "results": [
        {
            "scene_id": "scene_0042",
            "time": "45.2s - 52.8s",
            "caption": "A family gathering around a dinner table",
            "objects": [
                {"label": "person", "confidence": 0.95},
                {"label": "person", "confidence": 0.93},
                {"label": "table", "confidence": 0.89}
            ],
            "sentiment": "positive (0.87)",
            "emotions": {"joy": 0.76, "surprise": 0.14}
        },
        // ... more results
    ],
    "count": 23
}
```

**Actual, useful, searchable data!** 🎉

---

## 📊 DATA RELATIONSHIPS

```
                   ┌─────────────┐
                   │   Videos    │
                   └──────┬──────┘
                          │
                          │ has many
                          │
                   ┌──────▼──────┐
                   │   Scenes    │
                   │             │
                   │ - start     │
                   │ - end       │
                   │ - meta      │◄─────┐
                   └──────┬──────┘      │
                          │             │
          ┌───────────────┼───────────┐ │
          │               │           │ │
    has   │         has   │     has   │ │ enriched by
          │               │           │ │
    ┌─────▼─────┐  ┌──────▼──────┐  ┌─┴───────────┐
    │  Objects  │  │Transcription│  │  Analysis   │
    │           │  │             │  │  Results    │
    │ - label   │  │ - text      │  │             │
    │ - bbox    │  │ - segments  │  │ - caption   │
    │ - conf.   │  │ - speakers  │  │ - sentiment │
    └───────────┘  └─────────────┘  │ - emotions  │
                                     │ - tags      │
                                     │ - ocr_text  │
                                     └─────────────┘
                          │
                          │ generates
                          │
                   ┌──────▼──────┐
                   │ Embeddings  │
                   │             │
                   │ - vector    │
                   │ - modality  │
                   │ - metadata  │
                   └──────┬──────┘
                          │
                          │ enables
                          │
                   ┌──────▼──────┐
                   │   Search    │
                   │  & Retrieval│
                   └─────────────┘
```

---

## 🔄 PROCESSING FLOW

```
Input Video
    │
    ├─► Scene Detection ──► Scene Records Created ✅
    │
    ├─► Frame Extraction ──┐
    │                      │
    │                      ├─► Image Caption ──► save_caption() ✅
    │                      │
    │                      ├─► Object Detection ──► save_objects() ✅
    │                      │
    │                      └─► OCR ──► save_ocr_text() ✅
    │
    ├─► Audio Extraction ──┐
    │                      │
    │                      ├─► Transcription ──► save_transcription() ✅
    │                      │
    │                      ├─► Speaker ID ──► save_speakers() ✅
    │                      │
    │                      └─► Audio Emotion ──► save_emotions() ✅
    │
    ├─► Embeddings ────────┐
    │                      │
    │                      ├─► Text Embeddings ──► save_embedding() ✅
    │                      │
    │                      ├─► Image Embeddings ──► save_embedding() ✅
    │                      │
    │                      └─► Audio Embeddings ──► save_embedding() ✅
    │
    └─► Knowledge Graph ───┐
                           │
                           ├─► Entity Extraction ──► create_entities() ✅
                           │
                           └─► Relation Mapping ──► create_relations() ✅

All ✅ require memory_writer.py to be integrated!
```

---

## 💾 STORAGE LOCATIONS

```
<project_root>\ (Project Drive)
│
├─ GoodQ_Data/              # ← Main data directory
│  ├─ memory.db             # ← Actual location!
│  ├─ faiss_indices/
│  │  ├─ text.index
│  │  ├─ image.index
│  │  └─ audio.index
│  └─ exports/
│
├─ goodq4all/
│  ├─ data/
│  │  ├─ knowledge_graph.db
│  │  └─ production_kg.db
│  │
│  ├─ logs/                 # ← Extracted media
│  │  ├─ production_run/
│  │  │  ├─ 1987_1988/
│  │  │  │  ├─ frames/     # ← JPG files here
│  │  │  │  └─ audio/      # ← WAV files here
│  │  │  └─ sample/
│  │  └─ step_runs.jsonl   # ← Step execution log
│  │
│  └─ import_inbox/         # ← Drop videos here
│     └─ 1987_1988.mp4     # ← Waiting!
```

---

## 🎯 TESTING CHECKPOINTS

### 1. Utility Test
```bash
python scripts/quick_test_storage.py

Expected:
✅ Scene created
✅ Caption added
✅ Objects added
✅ All tests passed
```

### 2. Single Step Test
```python
# Test one fixed step
from steps.image_caption.step import image_caption

result = image_caption("test_scene", "frame.jpg")
# Check database for saved caption
```

### 3. Pipeline Test (sample.mp4)
```bash
python -m pipelines.ingest sample.mp4

# Verify
python scripts/check_memory_db.py

Expected:
scenes: 4
embeddings: 12
objects: 50+
```

### 4. Full Test (1987_1988.mp4)
```bash
python -m pipelines.ingest 1987_1988.mp4

# Verify
python scripts/check_memory_db.py

Expected:
scenes: 100+
embeddings: 300+
objects: 1000+
transcription: present
```

### 5. Historical API Test
```bash
curl http://localhost:30000/api/search?q=person

Expected:
{
    "results": [ ... actual data ... ],
    "count": > 0
}
```

---

## 🚀 SUCCESS CRITERIA

| Checkpoint | Before | After |
|-----------|---------|-------|
| Memory DB scenes | 0 | 100+ |
| Memory DB embeddings | 0 | 300+ |
| API search results | [] | [data] |
| Command Center stats | All zeros | Real numbers |
| Can query memories | No | Yes! |

---

## 📈 PROGRESSION

```
Week 1: Foundation
├─ Environment setup ✅
├─ Model integration ✅
├─ Pipeline structure ✅
└─ Storage layer 🔄 ← We are here

Week 2: Enhancement
├─ Quick wins (GPS, dates)
├─ Visualizations
└─ Polish UI

Week 3+: Advanced
├─ Chat ingestion
├─ Social media
├─ Knowledge graph
└─ Story generation
```

---

**The fix is simple. The impact is huge. Let's do this!** 🚀
