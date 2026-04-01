<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-02-12 -->

# Vision Processing Pipeline

**Status**: ✅ PRODUCTION OPERATIONAL  
**Last Updated**: December 15, 2025  
**Location**: `steps/image_*`, `steps/object_detect`, `steps/face_embed`, `steps/tagger`

---

## Overview

The GoodQ vision pipeline processes keyframes extracted from video scenes through seven specialized GPU-accelerated steps. Each step runs independently and contributes specific data to the scene understanding system.

**Processing Flow**: Scene Keyframe → 7 Parallel Vision Steps → Unified Scene Data

---

## Vision Processing Steps

### 1. Image OCR (`image_ocr`)

**Purpose**: Extract text from images using Tesseract OCR  
**Model**: Tesseract OCR Engine  
**Device**: CPU (OCR is CPU-optimized)  
**Location**: `steps/image_ocr/step.py`

**Configuration**:
```yaml
tool_paths:
  tesseract_cmd: "<project_root>/tools/tesseract/tesseract.exe"
```

**Output Fields**:
- `ocr_text`: Extracted text string (or `None` if no text detected)

**Example Output**:
```python
{
    "ocr_text": "Welcome to the Conference\nKeynote Speaker: Dr. Jane Smith"
}
```

**Graceful Handling**:
- Returns `None` if Tesseract not available
- Returns `None` if image unreadable
- No pipeline failure on OCR errors

---

### 2. Image Caption (`image_caption`)

**Purpose**: Generate natural language descriptions of image content  
**Model**: Salesforce BLIP (Base)  
**Device**: GPU (CUDA)  
**Location**: `steps/image_caption/step.py`

**GPU Configuration**:
- Memory Fraction: Auto-configured via GPU manager
- Batch Size: 1 (per-frame processing)
- Precision: FP32

**Model Details**:
- **HuggingFace ID**: `Salesforce/blip-image-captioning-base`
- **Cache Location**: `<GOODQ_DATA_ROOT>/models/transformers/`
- **Memory Usage**: ~2GB VRAM

**Output Fields**:
- `caption`: Natural language description
- `caption_meta`: Processing metadata

**Example Output**:
```python
{
    "caption": "a person sitting at a desk with a laptop computer",
    "caption_meta": {
        "model": "Salesforce/blip-image-captioning-base",
        "device": "cuda",
        "status": "ok"
    }
}
```

**Fallback Behavior**:
- Falls back to CPU if GPU unavailable
- Returns empty string on model load failure

---

### 3. Object Detection (`object_detect`)

**Purpose**: Detect and localize objects in images with bounding boxes  
**Model**: YOLOv8n (Ultralytics)  
**Device**: GPU (CUDA)  
**Location**: `steps/object_detect/step.py`

**GPU Configuration**:
- Memory Fraction: Auto-configured
- Inference Mode: FP16 (half precision)
- Batch Size: 1

**Model Details**:
- **Model File**: `yolov8n.pt`
- **Cache Location**: `<GOODQ_DATA_ROOT>/models/yolov8n.pt`
- **Classes**: 80 COCO classes
- **Input Size**: 640x640

**Configuration**:
```yaml
models:
  external_models:
    yolo_v8n:
      local_path: "yolov8n.pt"
      url: "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt"
```

**Output Fields**:
- `objects`: List of detected objects with bounding boxes
- `objects_meta`: Detection metadata

**Example Output**:
```python
{
    "objects": [
        {
            "class": "person",
            "confidence": 0.92,
            "bbox": [120, 45, 340, 480]
        },
        {
            "class": "laptop",
            "confidence": 0.87,
            "bbox": [200, 300, 450, 420]
        }
    ],
    "objects_meta": {
        "model": "yolov8n",
        "device": "cuda",
        "total_objects": 2
    }
}
```

---

### 4. Face Embedding (`face_embed`)

**Purpose**: Detect faces and generate 128-dim embeddings for recognition  
**Models**: face_recognition (primary), facenet-pytorch (fallback)  
**Device**: CPU (dlib), GPU (facenet-pytorch)  
**Location**: `steps/face_embed/step.py`

**Primary Engine** (face_recognition + dlib):
- **Encoding**: 128-dimensional face embeddings
- **Detection**: HOG-based face detection
- **Performance**: Fast, CPU-optimized

**Fallback Engine** (facenet-pytorch):
- **Model**: MTCNN + InceptionResnetV1
- **Device**: GPU accelerated
- **Use Case**: When dlib unavailable

**Output Fields**:
- `faces`: List of face detections with embeddings
- `faces_meta`: Detection metadata

**Example Output**:
```python
{
    "faces": [
        {
            "bbox": [120, 45, 220, 180],
            "encoding": [0.123, -0.456, ..., 0.789]  # 128 dims
        },
        {
            "bbox": [400, 60, 500, 195],
            "encoding": [0.234, -0.567, ..., 0.890]  # 128 dims
        }
    ],
    "faces_meta": {
        "status": "ok",
        "engine": "face_recognition",
        "total_faces": 2
    }
}
```

**Bbox Format**: `[left, top, right, bottom]` in pixels

---

### 5. DINO Embeddings (`image_embed_dino`)

**Purpose**: Generate semantic vision embeddings for similarity search  
**Model**: Facebook DINOv2-base  
**Device**: GPU (CUDA)  
**Location**: `steps/image_embed_dino/step.py`

**Model Details**:
- **HuggingFace ID**: `facebook/dinov2-base`
- **Embedding Dim**: 768
- **Architecture**: Vision Transformer
- **Use Case**: Semantic image search, scene similarity

**GPU Configuration**:
- Memory Fraction: Auto-configured
- Precision: FP32
- Pooling: CLS token

**Output Fields**:
- `dino_embedding`: 768-dim vector
- `dino_meta`: Processing metadata

**Example Output**:
```python
{
    "dino_embedding": [0.012, -0.345, ..., 0.678],  # 768 dims
    "dino_meta": {
        "model": "facebook/dinov2-base",
        "device": "cuda",
        "embedding_dim": 768
    }
}
```

**Integration**:
- Stored in Qdrant for vector search
- Used for "find similar scenes" queries
- Cross-modal harmonization with CLIP

---

### 6. CLIP Embeddings (`image_embed_clip`)

**Purpose**: Generate multimodal (vision + text) embeddings  
**Model**: OpenAI CLIP-ViT-B/32  
**Device**: GPU (CUDA)  
**Location**: `steps/image_embed_clip/step.py`

**Model Details**:
- **HuggingFace ID**: `openai/clip-vit-base-patch32`
- **Embedding Dim**: 512
- **Architecture**: Vision Transformer + Text Encoder
- **Use Case**: Text-to-image search, cross-modal retrieval

**GPU Configuration**:
- Memory Fraction: Auto-configured
- Precision: FP32
- Shared embedding space with text

**Output Fields**:
- `clip_embedding`: 512-dim vector
- `clip_meta`: Processing metadata

**Example Output**:
```python
{
    "clip_embedding": [0.123, -0.456, ..., 0.789],  # 512 dims
    "clip_meta": {
        "model": "openai/clip-vit-base-patch32",
        "device": "cuda",
        "embedding_dim": 512
    }
}
```

**Integration**:
- Qdrant storage for hybrid search
- Query: "Show me scenes with a person at a desk" → matches via CLIP
- Multimodal search across vision + audio + text

---

### 7. Entity Tagging (`tagger`)

**Purpose**: Extract named entities (people, places, objects) from text  
**Models**: Transformer-based NER pipelines  
**Device**: GPU (CUDA) for transformers  
**Location**: `steps/tagger/step.py`

**Primary Mode** (Standard NER):
- **Model**: `dslim/bert-base-NER` or similar
- **Entities**: PERSON, ORG, LOC, MISC
- **Strategy**: Token classification with aggregation

**Enhanced Mode** (`step_llm_enhanced.py`):
- **Backend**: vLLM with Qwen2.5-7B-Instruct
- **Enhanced Extraction**: Contextual entity resolution
- **Status**: Available but not default

**Input Sources** (priority order):
1. `transcript` - Audio transcription
2. `ocr_text` - Extracted text from image
3. `caption` - BLIP-generated description

**Output Fields**:
- `tags`: List of entity strings
- `tags_meta`: Extraction metadata

**Example Output**:
```python
{
    "tags": ["Dr. Jane Smith", "Stanford University", "Machine Learning Conference"],
    "tags_meta": {
        "model": "dslim/bert-base-NER",
        "source": "transcript",
        "total_tags": 3
    }
}
```

**Deduplication**:
- Case-insensitive deduplication
- Whitespace normalization
- Entity merging across modalities

---

## GPU Memory Management

**Centralized Configuration**: `steps/common/gpu_config.py`

All vision steps use the centralized GPU manager for:
- **Memory Allocation**: Dynamic per-step fractions
- **Cache Clearing**: Automatic between heavy operations
- **Device Selection**: Fallback to CPU if GPU unavailable

**Typical Memory Usage** (RTX 4070 Ti SUPER, 16GB):
```
image_caption (BLIP):     ~2GB
object_detect (YOLO):     ~1.5GB
image_embed_dino (DINO):  ~2.5GB
image_embed_clip (CLIP):  ~1.8GB
face_embed (facenet):     ~1GB
tagger (BERT-NER):        ~800MB
-----------------------------------
Total Peak:               ~9.6GB (with sequential processing)
```

**Memory Safety**:
- Models loaded on-demand
- Cache cleared between steps
- Shared with audio pipeline (WSL2 manages 85% utilization)

---

## Model Caching

**Cache Locations**:
```
<GOODQ_DATA_ROOT>/models/                          # Base model directory
  ├── transformers/                 # HuggingFace models
  │   ├── blip-image-captioning-base/
  │   ├── dinov2-base/
  │   ├── clip-vit-base-patch32/
  │   └── bert-base-NER/
  ├── yolov8n.pt                    # YOLO weights
  └── facenet/                      # Face recognition models
```

**Environment Variables**:
```bash
HF_HOME=<GOODQ_DATA_ROOT>/models
TORCH_HOME=<GOODQ_DATA_ROOT>/models
TRANSFORMERS_CACHE=<GOODQ_DATA_ROOT>/models/transformers
```

**First-Run Behavior**:
- Models auto-download from HuggingFace/GitHub
- ~5GB total download (one-time)
- Subsequent runs use cached models

---

## Integration with Scene Processing

**Called From**: `cli/run_ingestion.py` (main loop)

**Processing Order** (per scene):
1. Extract keyframe → `${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video>/video/scene_XXXX.jpg`
2. Run 7 vision steps in sequence
3. Aggregate results into scene data
4. Pass to entity extraction → knowledge graph
5. Store embeddings in Qdrant

**Data Flow**:
```
Keyframe (JPG)
    ├─> image_ocr          → ocr_text
    ├─> image_caption      → caption
    ├─> object_detect      → objects[]
    ├─> face_embed         → faces[]
    ├─> image_embed_dino   → dino_embedding[]
    ├─> image_embed_clip   → clip_embedding[]
    └─> tagger             → tags[]
          ↓
    Scene Data Bundle
          ↓
    Entity Extraction → Knowledge Graph
          ↓
    Qdrant Vector Storage
```

---

## Troubleshooting

### Issue: "CUDA out of memory"
**Solution**: 
- Check GPU utilization: `nvidia-smi`
- Ensure vLLM/audio services not hogging VRAM
- Reduce batch sizes in config (already set to 1)

### Issue: "Model not found"
**Solution**:
- Verify `HF_HOME=<GOODQ_DATA_ROOT>/models` is set
- Check internet connection for first-run downloads
- Manually download models if behind firewall

### Issue: "Tesseract not found"
**Solution**:
- Install Tesseract OCR: https://github.com/tesseract-ocr/tesseract
- Update `config.yaml` with correct path
- OCR will gracefully skip if unavailable

### Issue: "Face detection fails"
**Solution**:
- Install dlib: `pip install dlib` (requires CMake + VS Build Tools)
- Fallback to facenet-pytorch (GPU-based, no dlib)
- Face step returns empty array if no faces detected (not an error)

---

## Performance Benchmarks

**Test Setup**: RTX 4070 Ti SUPER, 16GB VRAM, CUDA 12.8

| Step             | Avg Time/Frame | GPU Memory | Model Size |
|------------------|----------------|------------|------------|
| image_ocr        | 0.3s          | 0MB (CPU)  | N/A        |
| image_caption    | 0.8s          | 2GB        | 990MB      |
| object_detect    | 0.5s          | 1.5GB      | 6MB        |
| face_embed       | 0.6s          | 0MB (CPU)  | N/A        |
| image_embed_dino | 1.2s          | 2.5GB      | 340MB      |
| image_embed_clip | 0.9s          | 1.8GB      | 350MB      |
| tagger           | 0.4s          | 800MB      | 420MB      |
| **Total**        | **4.7s**      | **Peak 2.5GB** | **2.1GB** |

*Note: Sequential processing prevents memory overlap*

---

## Future Enhancements

### Planned (Not Yet Implemented)
- **Scene Visual Embeddings Pooler**: Aggregate multi-frame embeddings
- **Cross-Modal Harmonizer**: Fuse CLIP + DINO + audio embeddings
- **Batch Processing**: Process multiple keyframes simultaneously
- **Model Quantization**: INT8 inference for faster processing

### Available But Not Wired
- **LLM-Enhanced Tagger**: `step_llm_enhanced.py` with vLLM backend
- **Embedding Pooler**: `steps/video/embedding_pooler.py`
- **Visual Embeddings**: `steps/video/scene_visual_embeddings.py`

See `docs/implementation/PHASE_6B_COMPONENTS.md` for details on latent capabilities.

---

## Related Documentation

- **GPU Configuration**: `docs/guides/gpu/GPU_MANAGEMENT_GUIDE.md`
- **Scene Processing**: `docs/architecture/SCENE_PROCESSING_FLOW.md`
- **Entity Extraction**: `docs/components/ENTITY_EXTRACTION.md`
- **Embedding Storage**: `docs/components/QDRANT_INTEGRATION.md`

---

**Last Verified**: December 15, 2025  
**Verification Method**: Live ingestion run with 30 scenes processed  
**Status**: ✅ All vision steps operational and producing expected output
