# Phase 6: Scene-Level Visual Embeddings & Cross-Modal Retrieval Analysis

**Project:** GoodQ4All - Multimodal Memory Intelligence System  
**Phase:** 6 - Final Integration for Public Beta  
**Analysis Date:** December 5, 2025  
**Status:** ANALYSIS COMPLETE - AWAITING IMPLEMENTATION APPROVAL

---

## EXECUTIVE SUMMARY

Phase 6 represents the final major subsystem required to complete GoodQ4All's multimodal retrieval architecture. This analysis provides a complete blueprint for integrating scene-level visual embeddings with the existing audio/text embedding infrastructure, creating a unified cross-modal retrieval engine capable of answering complex queries like:

- *"Show me scenes where people are eating while discussing work"*
- *"Find moments with laughter and outdoor settings"*  
- *"What was on screen when they mentioned 'vacation'?"*

**Current State:** The pipeline successfully segments video/audio (Phase 0-5) and generates image-level CLIP/DINO embeddings. However, scene-level embeddings are missing, preventing retrieval at the semantic video unit level.

**Required Work:** Implement scene-level frame extraction, batch embedding generation, cross-modal fusion, and unified retrieval interface.

**Risk Assessment:** LOW - All required components exist; this is primarily an integration task with well-defined insertion points.

---

## I. CURRENT-STATE AUDIT

### 1.1 Existing Embedding Capabilities

#### ✅ **CLIP Embeddings** (Image-Level)
- **Location:** `goodq4all/steps/image_embed_clip/step.py`
- **Model:** `openai/clip-vit-base-patch16`
- **Dimensions:** 512
- **Environment:** `goodq_core` (CUDA 12.1, Torch 2.5.1)
- **Storage:** FAISS index at `L:/_DATA/goodq4all/data/faiss_indices/clip/faiss_clip.index`
- **ID Mapping:** SQLite at `L:/_DATA/goodq4all/data/databases/clip_id_map.sqlite`
- **GPU Config:** Uses centralized `GPUManager` with memory fraction control
- **Status:** ✅ Operational for single images

#### ✅ **DINO Embeddings** (Image-Level)
- **Location:** `goodq4all/steps/image_embed_dino/step.py`
- **Model:** `facebook/dinov2-base`
- **Dimensions:** 768
- **Environment:** `goodq_core` (CUDA 12.1, Torch 2.5.1)
- **Storage:** FAISS index at `L:/_DATA/goodq4all/data/faiss_indices/dino/faiss_dino.index`
- **ID Mapping:** SQLite at `L:/_DATA/goodq4all/data/databases/dino_id_map.sqlite`
- **GPU Config:** Uses centralized `GPUManager` with memory fraction control
- **Status:** ✅ Operational for single images

#### ✅ **Text Embeddings** (Sentence-Level)
- **Model:** `sentence-transformers/all-MiniLM-L6-v2`
- **Dimensions:** 384
- **Storage:** FAISS + Qdrant dual-write
- **Status:** ✅ Operational

#### ✅ **Audio Embeddings** (CLAP)
- **Model:** CLAP (audio-text joint space)
- **Dimensions:** 512
- **Storage:** FAISS + Qdrant dual-write
- **Environment:** WSL2 audio stack (separate from core)
- **Status:** ✅ Operational

### 1.2 Existing Scene Detection Infrastructure

#### ✅ **Phase 5 Scene Detection**
- **Location:** `goodq4all/steps/audio/segmentation/phase5_video_scene_integration.py`
- **Capabilities:**
  - Per-chunk scene detection with `detect_scenes_for_chunk()`
  - Frame difference analysis using GPU (OpenCV + PyTorch)
  - Scene boundary timestamps with confidence scores
  - Fallback to full-chunk scenes on failure
- **Output:** Scene manifest with start/end/duration/confidence
- **Integration Point:** Called during video ingestion via `video_scene_segmentation` step
- **Status:** ✅ Operational

#### ✅ **Legacy Scene Detection** (Being Phased Out)
- **Location:** `goodq4all/steps/video_scene_detect/step.py` + `gpu_scene_detect.py`
- **Environment:** `goodq_video_scene_detect` (CUDA 11.8, Torch 2.7.1) ⚠️ CUDA MISMATCH
- **Status:** ⚠️ Still exists but Phase 5 provides modern replacement

### 1.3 Temporal Index Structure

#### ✅ **Phase 5 Temporal Index**
- **Output Path:** `L:/_DATA/GoodQ_Data/processing/<video_id>/temporal_index.json`
- **Current Fields:**
  ```json
  {
    "version": 1,
    "video_id": "...",
    "duration": 815.23,
    "scenes": [
      {
        "id": 0,
        "start": 0.0,
        "end": 8.43,
        "duration": 8.43,
        "confidence": 0.92,
        "strategy": "gpu_difference"
      }
    ],
    "audio_segments": [
      {
        "id": 12,
        "start": 120.532,
        "end": 155.923,
        "vad_speech": true,
        "overlap": false,
        "speaker_changes": [],
        "chunk_path": "audio/chunks/segment_12.wav"
      }
    ],
    "scene_to_audio_alignment": [
      {
        "scene_id": 0,
        "audio_chunks": [0, 1, 2],
        "start": 0.0,
        "end": 8.43
      }
    ]
  }
  ```
- **Missing Fields (Phase 6 Will Add):**
  - `scenes[].representative_frames[]` - List of frame indices/timestamps
  - `scenes[].clip_embedding` - 512-dim vector
  - `scenes[].dino_embedding` - 768-dim vector
  - `scenes[].visual_objects[]` - Object labels detected in scene
  - `scenes[].visual_summary` - Text description combining captions
  - `multimodal_index` - Cross-modal retrieval metadata

### 1.4 Vector Storage Infrastructure

#### ✅ **FAISS Indices**
- **Config:** `config.yaml` lines 73-83
- **Paths:**
  - Text: `faiss_indices/text/faiss_text.index`
  - CLIP: `faiss_indices/clip/faiss_clip.index`
  - DINO: `faiss_indices/dino/faiss_dino.index`
  - Audio: `faiss_indices/audio/faiss_audio.index`
- **Index Type:** `IndexHNSWFlat` (Hierarchical Navigable Small World)
  - `efConstruction`: 200
  - `efSearch`: 50
  - `M`: 32
- **ID Strategy:** Content fingerprint-based stable IDs

#### ✅ **Qdrant Integration**
- **Location:** `goodq4all/steps/common/qdrant_client.py`
- **Config:** `config.yaml` lines 121-142
- **Host:** `http://localhost:6333`
- **Collections:**
  - `goodq_text` (384-dim)
  - `goodq_image` (512-dim)
  - `goodq_audio` (512-dim)
- **Write Strategy:** Dual-write to FAISS + Qdrant
- **Status:** ✅ Operational client ready for scene embeddings

### 1.5 Pipeline Integration Points

#### ✅ **Ingestion Pipeline**
- **Location:** `goodq4all/pipelines/ingest_multimodal_conda.py`
- **Current Flow:**
  ```python
  if mod == "video":
      # Phase 5: Video scene detection aligned with audio segmentation
      scene_result = run_conda_step("goodq_core", "video_scene_segmentation", enriched, cfg)
      enriched.update(scene_result)
  ```
- **Insertion Point for Phase 6:** Immediately after Phase 5, before universal steps
- **Line Number:** After line 75 in `process_items_step()`

#### ✅ **Step Runner**
- **Location:** `goodq4all/cli/step_runner.py`
- **Pattern:** Conditional imports with step name mapping
- **Required Addition:** New conditional block for `scene_visual_embeddings`

---

## II. SCENE EMBEDDING INTEGRATION PLAN

### 2.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     PHASE 6 FLOW                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Load temporal_index.json from Phase 5                  │
│  2. For each scene:                                         │
│     a. Extract representative frames (3 strategies)         │
│     b. Batch frames through CLIP (GPU)                      │
│     c. Batch frames through DINO (GPU)                      │
│     d. Pool embeddings (mean/max/attention)                 │
│     e. Store scene-level vectors                            │
│  3. Update temporal_index.json with embeddings              │
│  4. Write to FAISS indices (scene-level)                    │
│  5. Write to Qdrant collections                             │
│  6. Build cross-modal retrieval metadata                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Frame Extraction Strategy

**Module:** `goodq4all/steps/video/scene_frame_extractor.py` (NEW)

#### Strategy 1: Keyframe Selection (Primary)
```python
def extract_keyframes(
    video_path: str,
    scene_start: float,
    scene_end: float,
    max_frames: int = 5
) -> List[np.ndarray]:
    """
    Extract keyframes using motion analysis
    - Identify frames with maximum visual change within scene
    - Ensures diversity in frame selection
    - GPU-accelerated using PyTorch optical flow
    """
```

#### Strategy 2: Uniform Sampling (Fallback)
```python
def extract_uniform_frames(
    video_path: str,
    scene_start: float,
    scene_end: float,
    num_frames: int = 5
) -> List[np.ndarray]:
    """
    Uniformly sample frames across scene duration
    - scene_start + (scene_duration / (num_frames + 1)) * i
    - Fast, deterministic, no GPU required
    """
```

#### Strategy 3: Middle Frame (Fast Fallback)
```python
def extract_middle_frame(
    video_path: str,
    scene_start: float,
    scene_end: float
) -> np.ndarray:
    """
    Extract single representative frame at scene midpoint
    - Fastest option for long videos
    - scene_start + (scene_end - scene_start) / 2
    """
```

**Recommendation:** Use Strategy 1 (keyframes) for scenes < 30s, Strategy 2 (uniform) for scenes 30-300s, Strategy 3 (middle) for scenes > 300s.

### 2.3 Batch Embedding Generation

**Module:** `goodq4all/steps/video/scene_embedder.py` (NEW)

```python
def embed_scene_batch_clip(
    frames: List[np.ndarray],
    device: str = "cuda",
    batch_size: int = 16
) -> np.ndarray:
    """
    Generate CLIP embeddings for scene frames in batches
    
    Args:
        frames: List of RGB frames (H, W, 3)
        device: "cuda" or "cpu"
        batch_size: Number of frames per GPU batch
        
    Returns:
        Array of shape (num_frames, 512) - CLIP embeddings
    """
    # Reuse existing CLIP model from image_embed_clip
    from goodq4all.steps.image_embed_clip.step import _CLIP, _load
    _load()
    
    # Batch process with GPU memory management
    embeddings = []
    for i in range(0, len(frames), batch_size):
        batch = frames[i:i+batch_size]
        # Convert to PIL Images
        pil_batch = [Image.fromarray(f) for f in batch]
        # Process batch
        inputs = _CLIP["proc"](images=pil_batch, return_tensors="pt", padding=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad(), torch.cuda.amp.autocast():
            feats = _CLIP["model"].get_image_features(**inputs)
        embeddings.append(feats.cpu().numpy())
    
    return np.vstack(embeddings).astype("float32")


def embed_scene_batch_dino(
    frames: List[np.ndarray],
    device: str = "cuda",
    batch_size: int = 16
) -> np.ndarray:
    """
    Generate DINO embeddings for scene frames in batches
    
    Returns:
        Array of shape (num_frames, 768) - DINO embeddings
    """
    # Similar implementation using existing DINO model
    from goodq4all.steps.image_embed_dino.step import _DINO, _load
    _load()
    # ... batch processing logic ...
```

### 2.4 Embedding Pooling Strategies

**Module:** `goodq4all/steps/video/embedding_pooler.py` (NEW)

```python
def pool_embeddings(
    embeddings: np.ndarray,
    strategy: str = "mean"
) -> np.ndarray:
    """
    Pool multiple frame embeddings into single scene embedding
    
    Args:
        embeddings: Array of shape (num_frames, embedding_dim)
        strategy: "mean", "max", "attention", "concat"
        
    Returns:
        Single embedding vector representing the scene
    """
    if strategy == "mean":
        return embeddings.mean(axis=0)
    elif strategy == "max":
        return embeddings.max(axis=0)
    elif strategy == "attention":
        # Weighted average with learned attention (future enhancement)
        return embeddings.mean(axis=0)  # Fallback to mean for now
    elif strategy == "concat":
        # Concatenate all embeddings (increases dimensionality)
        return embeddings.flatten()
    else:
        return embeddings.mean(axis=0)
```

**Recommendation:** Use `mean` pooling as default. It preserves dimensionality and provides robust scene representation.

### 2.5 Main Integration Module

**Module:** `goodq4all/steps/video/scene_visual_embeddings.py` (NEW)

```python
"""
Phase 6: Scene-Level Visual Embeddings
Generates CLIP and DINO embeddings for video scenes
"""
from __future__ import annotations
from typing import Dict, List, Any
import os
import json
import numpy as np

from goodq4all.steps.video.scene_frame_extractor import (
    extract_keyframes,
    extract_uniform_frames,
    extract_middle_frame
)
from goodq4all.steps.video.scene_embedder import (
    embed_scene_batch_clip,
    embed_scene_batch_dino
)
from goodq4all.steps.video.embedding_pooler import pool_embeddings


def run_scene_visual_embeddings(
    item: Dict[str, Any],
    cfg: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate scene-level CLIP and DINO embeddings
    
    Expected in item:
        - source_path: Video file path
        - temporal_index_path: Path to Phase 5 temporal index
        
    Returns:
        Updated item with scene embeddings stored
    """
    video_path = item.get("source_path")
    temporal_index_path = item.get("temporal_index_path")
    
    if not video_path or not os.path.isfile(video_path):
        return {"scene_embeddings_meta": {"status": "no_video"}}
    
    if not temporal_index_path or not os.path.isfile(temporal_index_path):
        return {"scene_embeddings_meta": {"status": "no_temporal_index"}}
    
    # Load temporal index from Phase 5
    with open(temporal_index_path, 'r') as f:
        temporal_index = json.load(f)
    
    scenes = temporal_index.get("scenes", [])
    if not scenes:
        return {"scene_embeddings_meta": {"status": "no_scenes"}}
    
    # Get config
    phase6_cfg = cfg.get("phase6", {}) or {}
    max_frames_per_scene = phase6_cfg.get("max_frames_per_scene", 5)
    pooling_strategy = phase6_cfg.get("pooling_strategy", "mean")
    batch_size = phase6_cfg.get("batch_size", 16)
    
    # Process each scene
    enriched_scenes = []
    for scene in scenes:
        scene_id = scene.get("id")
        scene_start = scene.get("start")
        scene_end = scene.get("end")
        scene_duration = scene.get("duration")
        
        # Select frame extraction strategy
        if scene_duration < 30.0:
            frames = extract_keyframes(video_path, scene_start, scene_end, max_frames_per_scene)
        elif scene_duration < 300.0:
            frames = extract_uniform_frames(video_path, scene_start, scene_end, max_frames_per_scene)
        else:
            frames = [extract_middle_frame(video_path, scene_start, scene_end)]
        
        if not frames:
            # Fallback: no embeddings for this scene
            enriched_scenes.append({**scene, "embedding_status": "extraction_failed"})
            continue
        
        # Generate embeddings
        clip_embeddings = embed_scene_batch_clip(frames, batch_size=batch_size)
        dino_embeddings = embed_scene_batch_dino(frames, batch_size=batch_size)
        
        # Pool to scene-level
        scene_clip = pool_embeddings(clip_embeddings, pooling_strategy)
        scene_dino = pool_embeddings(dino_embeddings, pooling_strategy)
        
        # Store in FAISS and Qdrant
        clip_faiss_id = _store_clip_embedding(scene_clip, scene_id, video_path, cfg)
        dino_faiss_id = _store_dino_embedding(scene_dino, scene_id, video_path, cfg)
        
        # Update scene metadata
        enriched_scene = {
            **scene,
            "num_frames_sampled": len(frames),
            "clip_embedding": scene_clip.tolist(),
            "dino_embedding": scene_dino.tolist(),
            "clip_faiss_id": clip_faiss_id,
            "dino_faiss_id": dino_faiss_id,
            "embedding_status": "success"
        }
        enriched_scenes.append(enriched_scene)
    
    # Update temporal index
    temporal_index["scenes"] = enriched_scenes
    temporal_index["phase6_complete"] = True
    
    # Write updated temporal index
    with open(temporal_index_path, 'w') as f:
        json.dump(temporal_index, f, indent=2)
    
    return {
        "scene_embeddings_meta": {
            "status": "success",
            "scenes_processed": len(enriched_scenes),
            "temporal_index_path": temporal_index_path
        }
    }


def _store_clip_embedding(embedding: np.ndarray, scene_id: int, video_path: str, cfg: Dict[str, Any]) -> int:
    """Store CLIP embedding in FAISS and Qdrant"""
    # Reuse logic from image_embed_clip with scene-specific ID
    # ... implementation ...
    pass


def _store_dino_embedding(embedding: np.ndarray, scene_id: int, video_path: str, cfg: Dict[str, Any]) -> int:
    """Store DINO embedding in FAISS and Qdrant"""
    # Reuse logic from image_embed_dino with scene-specific ID
    # ... implementation ...
    pass
```

---

## III. CROSS-MODAL FUSION PLAN

### 3.1 Unified Multimodal Object Schema

**Enhancement to temporal_index.json:**

```json
{
  "version": 2,
  "video_id": "abc123",
  "duration": 815.23,
  "scenes": [
    {
      "id": 0,
      "start": 0.0,
      "end": 8.43,
      "duration": 8.43,
      "confidence": 0.92,
      
      // NEW: Visual embeddings
      "num_frames_sampled": 5,
      "clip_embedding": [0.12, -0.45, ...],  // 512-dim
      "dino_embedding": [0.33, 0.21, ...],   // 768-dim
      "clip_faiss_id": 12345,
      "dino_faiss_id": 67890,
      
      // NEW: Visual semantics (from existing object_detect/caption steps)
      "visual_objects": ["person", "laptop", "coffee mug"],
      "dominant_colors": ["blue", "white", "gray"],
      "scene_type": "indoor_office",
      
      // Existing: Audio alignment
      "audio_chunks": [0, 1],
      "speakers": ["SPEAKER_01"],
      "transcript_snippet": "Let's discuss the quarterly results...",
      "audio_emotion": "neutral",
      
      // NEW: Cross-modal metadata
      "multimodal_summary": "Office scene with person at laptop discussing quarterly results"
    }
  ],
  
  // NEW: Cross-modal retrieval index
  "multimodal_index": {
    "scene_to_text": {
      "0": ["quarterly", "results", "discuss", "office"]
    },
    "scene_to_audio": {
      "0": [0, 1]  // Audio chunk IDs
    },
    "scene_to_visual": {
      "0": {
        "clip_id": 12345,
        "dino_id": 67890,
        "objects": ["person", "laptop", "coffee mug"]
      }
    }
  }
}
```

### 3.2 Cross-Modal Harmonizer Module

**Module:** `goodq4all/steps/video/cross_modal_harmonizer.py` (NEW)

```python
"""
Phase 6: Cross-Modal Fusion
Merges scene embeddings with audio/text/visual metadata
"""
from __future__ import annotations
from typing import Dict, List, Any
import json


def harmonize_multimodal_data(
    temporal_index: Dict[str, Any],
    cfg: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build unified multimodal index for retrieval
    
    Combines:
    - Scene visual embeddings (CLIP, DINO)
    - Audio transcripts and embeddings (CLAP)
    - Text embeddings (sentence transformers)
    - Object detections
    - Speaker diarization
    
    Returns:
        Enhanced temporal_index with multimodal_index field
    """
    scenes = temporal_index.get("scenes", [])
    audio_segments = temporal_index.get("audio_segments", [])
    
    multimodal_index = {
        "scene_to_text": {},
        "scene_to_audio": {},
        "scene_to_visual": {}
    }
    
    for scene in scenes:
        scene_id = str(scene.get("id"))
        
        # Visual index
        multimodal_index["scene_to_visual"][scene_id] = {
            "clip_id": scene.get("clip_faiss_id"),
            "dino_id": scene.get("dino_faiss_id"),
            "objects": scene.get("visual_objects", [])
        }
        
        # Audio alignment
        audio_chunks = scene.get("audio_chunks", [])
        multimodal_index["scene_to_audio"][scene_id] = audio_chunks
        
        # Text extraction from transcript
        transcript_text = scene.get("transcript_snippet", "")
        keywords = extract_keywords(transcript_text)
        multimodal_index["scene_to_text"][scene_id] = keywords
    
    temporal_index["multimodal_index"] = multimodal_index
    return temporal_index


def extract_keywords(text: str) -> List[str]:
    """Simple keyword extraction (can be enhanced with NLP)"""
    # Remove common words, extract meaningful terms
    words = text.lower().split()
    stopwords = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for"}
    return [w for w in words if w not in stopwords and len(w) > 3]
```

---

## IV. RETRIEVAL ENGINE BLUEPRINT

### 4.1 Query Architecture

```
┌─────────────────────────────────────────────────────────┐
│              MULTIMODAL QUERY FLOW                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  User Query: "Find scenes with people eating outdoors" │
│       ↓                                                 │
│  1. Parse query into modality components:              │
│     - Visual: "people eating outdoors"                  │
│     - Text: "eating", "outdoors"                        │
│     - Audio: (none specified)                           │
│       ↓                                                 │
│  2. Generate query embeddings:                          │
│     - CLIP text encoder("people eating outdoors")      │
│     - Text embedding("eating outdoors")                 │
│       ↓                                                 │
│  3. Search individual modalities:                       │
│     - FAISS CLIP index → top 20 scenes                  │
│     - FAISS text index → top 20 scenes                  │
│     - Keyword match → scenes with "eating", "outdoors"  │
│       ↓                                                 │
│  4. Fusion & Re-ranking:                                │
│     - Combine scores with weights                       │
│     - Apply temporal constraints                        │
│     - Filter by metadata                                │
│       ↓                                                 │
│  5. Return ranked results with context                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Retrieval Module

**Module:** `goodq4all/retrieval/multimodal_search.py` (NEW)

```python
"""
Phase 6: Multimodal Retrieval Engine
Unified search across visual, audio, and text modalities
"""
from __future__ import annotations
from typing import Dict, List, Any, Optional
import numpy as np
import faiss


class MultimodalRetriever:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self.clip_index = self._load_faiss_index("faiss_clip_path")
        self.dino_index = self._load_faiss_index("faiss_dino_path")
        self.text_index = self._load_faiss_index("faiss_index_path")
        self.audio_index = self._load_faiss_index("faiss_audio_path")
    
    def search(
        self,
        query: str,
        modalities: List[str] = ["visual", "text", "audio"],
        top_k: int = 10,
        fusion_strategy: str = "weighted_sum"
    ) -> List[Dict[str, Any]]:
        """
        Multi-modal semantic search
        
        Args:
            query: Natural language query
            modalities: Which modalities to search ["visual", "text", "audio"]
            top_k: Number of results to return
            fusion_strategy: How to combine scores ("weighted_sum", "max", "rrf")
            
        Returns:
            List of scene results with scores and metadata
        """
        results = {}
        
        # Visual search (CLIP)
        if "visual" in modalities:
            clip_results = self._search_clip(query, top_k * 2)
            for res in clip_results:
                scene_id = res["scene_id"]
                if scene_id not in results:
                    results[scene_id] = {"scores": {}, "metadata": res["metadata"]}
                results[scene_id]["scores"]["clip"] = res["score"]
        
        # Text search
        if "text" in modalities:
            text_results = self._search_text(query, top_k * 2)
            for res in text_results:
                scene_id = res["scene_id"]
                if scene_id not in results:
                    results[scene_id] = {"scores": {}, "metadata": res["metadata"]}
                results[scene_id]["scores"]["text"] = res["score"]
        
        # Audio search
        if "audio" in modalities:
            audio_results = self._search_audio(query, top_k * 2)
            for res in audio_results:
                scene_id = res["scene_id"]
                if scene_id not in results:
                    results[scene_id] = {"scores": {}, "metadata": res["metadata"]}
                results[scene_id]["scores"]["audio"] = res["score"]
        
        # Fusion
        fused_results = self._fuse_scores(results, fusion_strategy)
        
        # Re-rank and return top-k
        ranked = sorted(fused_results, key=lambda x: x["final_score"], reverse=True)
        return ranked[:top_k]
    
    def _search_clip(self, query: str, k: int) -> List[Dict[str, Any]]:
        """Search CLIP index with text query"""
        # Use CLIP text encoder to embed query
        from transformers import CLIPModel, CLIPProcessor
        processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch16")
        model = CLIPModel.from_pretrained("openai/clip-vit-base-patch16")
        
        inputs = processor(text=[query], return_tensors="pt", padding=True)
        with torch.no_grad():
            text_features = model.get_text_features(**inputs)
        
        query_vec = text_features.cpu().numpy().astype("float32")
        
        # Search FAISS
        distances, indices = self.clip_index.search(query_vec, k)
        
        # Load scene metadata from temporal indices
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            scene_meta = self._lookup_scene_by_clip_id(idx)
            results.append({
                "scene_id": scene_meta["id"],
                "score": 1.0 / (1.0 + dist),  # Convert distance to similarity
                "metadata": scene_meta
            })
        return results
    
    def _fuse_scores(
        self,
        results: Dict[str, Dict[str, Any]],
        strategy: str
    ) -> List[Dict[str, Any]]:
        """Combine scores from multiple modalities"""
        weights = {"clip": 0.4, "text": 0.3, "audio": 0.3}
        
        fused = []
        for scene_id, data in results.items():
            scores = data["scores"]
            
            if strategy == "weighted_sum":
                final_score = sum(scores.get(mod, 0) * weights.get(mod, 0) for mod in weights)
            elif strategy == "max":
                final_score = max(scores.values())
            else:
                final_score = sum(scores.values()) / len(scores)
            
            fused.append({
                "scene_id": scene_id,
                "final_score": final_score,
                "individual_scores": scores,
                "metadata": data["metadata"]
            })
        
        return fused
```

### 4.3 Query Interface Enhancement

**Module:** `goodq4all/cli/retrieve.py` (ENHANCE EXISTING)

Add new command:

```python
@click.command()
@click.argument("query")
@click.option("--modalities", "-m", multiple=True, default=["visual", "text"], help="Modalities to search")
@click.option("--top-k", "-k", default=10, help="Number of results")
@click.option("--output", "-o", type=click.Path(), help="Output JSON path")
def multimodal_search(query: str, modalities: List[str], top_k: int, output: Optional[str]):
    """
    Multimodal semantic search across scenes
    
    Example:
        goodq retrieve multimodal "people eating outdoors" -m visual -m text -k 5
    """
    from goodq4all.retrieval.multimodal_search import MultimodalRetriever
    from goodq4all.steps.common.config_loader import load_configs
    
    cfg = load_configs({})
    retriever = MultimodalRetriever(cfg)
    
    results = retriever.search(query, modalities=list(modalities), top_k=top_k)
    
    if output:
        with open(output, 'w') as f:
            json.dump(results, f, indent=2)
    else:
        for i, res in enumerate(results, 1):
            print(f"{i}. Scene {res['scene_id']} (score: {res['final_score']:.3f})")
            print(f"   Time: {res['metadata']['start']:.2f}s - {res['metadata']['end']:.2f}s")
            print(f"   Objects: {', '.join(res['metadata'].get('visual_objects', []))}")
            print()
```

---

## V. PIPELINE INTEGRATION POINTS

### 5.1 Config Updates

**File:** `config.yaml`

Add Phase 6 section:

```yaml
phase6:
  enabled: true
  max_frames_per_scene: 5
  pooling_strategy: "mean"  # mean, max, attention
  batch_size: 16
  frame_extraction_strategy: "adaptive"  # keyframe, uniform, middle, adaptive
  
  # Scene embedding storage
  scene_clip_index: /mnt/l/goodq4all/data/faiss_indices/scene_clip/scene_clip.index
  scene_dino_index: /mnt/l/goodq4all/data/faiss_indices/scene_dino/scene_dino.index
  scene_id_map_db: /mnt/l/goodq4all/data/databases/scene_id_map.sqlite
  
  # Qdrant collections
  qdrant_scene_collection: "goodq_scenes"
  
  # Fusion weights
  fusion_weights:
    clip: 0.4
    text: 0.3
    audio: 0.3
```

### 5.2 Step Runner Registration

**File:** `goodq4all/cli/step_runner.py`

Add after line 150:

```python
if step_name == "scene_visual_embeddings":
    from goodq4all.steps.video.scene_visual_embeddings import run_scene_visual_embeddings
    assert item is not None
    return run_scene_visual_embeddings(item, cfg)

if step_name == "cross_modal_harmonization":
    from goodq4all.steps.video.cross_modal_harmonizer import harmonize_multimodal_data
    assert item is not None
    return harmonize_multimodal_data(item, cfg)
```

### 5.3 Pipeline Integration

**File:** `goodq4all/pipelines/ingest_multimodal_conda.py`

Modify `process_items_step()` at line 72-75:

```python
if mod == "video":
    # Phase 5: Video scene detection aligned with audio segmentation
    scene_result = run_conda_step("goodq_core", "video_scene_segmentation", enriched, cfg)
    enriched.update(scene_result)
    
    # Phase 6: Scene-level visual embeddings (NEW)
    if cfg.get("phase6", {}).get("enabled", True):
        embed_result = run_conda_step("goodq_core", "scene_visual_embeddings", enriched, cfg)
        enriched.update(embed_result)
        
        # Cross-modal harmonization (NEW)
        harmony_result = run_conda_step("goodq_core", "cross_modal_harmonization", enriched, cfg)
        enriched.update(harmony_result)
```

---

## VI. PERFORMANCE OPTIMIZATION STRATEGY

### 6.1 GPU Memory Management

**Current GPU Config:** Centralized via `GPUManager` in `gpu_config.py`

**Phase 6 Considerations:**
- CLIP model: ~600MB VRAM
- DINO model: ~350MB VRAM
- Frame buffers: ~100MB per batch (16 frames @ 224x224)
- Total: ~1.05GB for concurrent operation

**Optimization:**
```python
# In scene_embedder.py
def embed_scene_batch_clip(frames, device="cuda", batch_size=16):
    # Dynamic batch sizing based on available VRAM
    available_mem = torch.cuda.get_device_properties(0).total_memory
    used_mem = torch.cuda.memory_allocated(0)
    free_mem = available_mem - used_mem
    
    if free_mem < 2e9:  # Less than 2GB free
        batch_size = 8  # Reduce batch size
    
    # ... rest of implementation
```

### 6.2 Frame Extraction Performance

**Strategy Timing (estimated):**
- Keyframe extraction: ~50ms per scene (GPU optical flow)
- Uniform sampling: ~20ms per scene (direct frame seek)
- Middle frame: ~5ms per scene (single seek)

**Recommendation:** Use adaptive strategy based on scene duration and total video length.

### 6.3 Batch Processing

**Scene Processing Order:**
1. Group scenes by duration (small, medium, large)
2. Process small scenes with keyframe extraction (high quality)
3. Process medium scenes with uniform sampling (balanced)
4. Process large scenes with middle frame (fast)

**Estimated Throughput:**
- 1 hour video ≈ 50-100 scenes
- Processing time: ~5-10 minutes on RTX 4070 Ti
- Breakdown:
  - Frame extraction: 2 min
  - CLIP embedding: 2 min
  - DINO embedding: 1 min
  - FAISS indexing: 30 sec
  - Qdrant upload: 30 sec
  - JSON I/O: 10 sec

### 6.4 Parallel Execution Model

**Current Limitation:** Sequential scene processing

**Future Enhancement (Post-Public Beta):**
```python
from concurrent.futures import ThreadPoolExecutor

def process_scenes_parallel(scenes, video_path, cfg):
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(process_single_scene, scene, video_path, cfg)
            for scene in scenes
        ]
        results = [f.result() for f in futures]
    return results
```

**Risk:** GPU contention - requires careful memory management.

---

## VII. RISK ASSESSMENT

### 7.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **GPU OOM during batch embedding** | Medium | High | Dynamic batch sizing, graceful fallback to CPU |
| **Frame extraction errors on corrupted video** | Low | Medium | Try/catch with fallback to skip scene |
| **FAISS index corruption** | Low | High | Atomic writes, backup before update |
| **Temporal index size explosion** | Medium | Low | Store embeddings separately, reference by ID |
| **CUDA version mismatch** | Low | High | All Phase 6 uses `goodq_core` (CUDA 12.1) |
| **Cross-modal alignment drift** | Low | Medium | Timestamp validation, confidence thresholds |

### 7.2 Performance Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Slow frame extraction** | Medium | Medium | Adaptive strategy, skip keyframe for long scenes |
| **CLIP/DINO model load time** | Low | Low | Models already loaded by existing image steps |
| **Large FAISS index search latency** | Medium | Medium | HNSW indexing (already implemented) |
| **Qdrant upload bottleneck** | Low | Low | Async batch uploads |

### 7.3 Data Quality Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Poor frame selection** | Medium | Medium | Multiple frame sampling, pooling strategy |
| **Scene boundary mismatch** | Low | Low | Phase 5 already validated scene detection |
| **Missing audio alignment** | Low | High | Fallback to scene timestamp overlap |
| **Duplicate embeddings** | Low | Low | Content fingerprint-based IDs |

---

## VIII. ROLLBACK PLAN

### 8.1 Disabling Phase 6

**Config Flag:**
```yaml
phase6:
  enabled: false
```

**Pipeline Behavior:** Video ingestion proceeds without scene embeddings. Scenes still detected by Phase 5, but no visual embeddings generated.

### 8.2 Partial Rollback

**Scenario:** CLIP embeddings work, DINO embeddings fail

**Solution:**
```python
# In scene_visual_embeddings.py
try:
    dino_embeddings = embed_scene_batch_dino(frames)
except Exception as e:
    logger.warning(f"DINO embedding failed: {e}")
    dino_embeddings = None  # Skip DINO, continue with CLIP
```

### 8.3 Index Corruption Recovery

**Backup Strategy:**
```bash
# Before Phase 6 activation
cp -r L:/_DATA/goodq4all/data/faiss_indices L:/_DATA/goodq4all/data/faiss_indices.backup_pre_phase6
```

**Restore:**
```bash
rm -rf L:/_DATA/goodq4all/data/faiss_indices
mv L:/_DATA/goodq4all/data/faiss_indices.backup_pre_phase6 L:/_DATA/goodq4all/data/faiss_indices
```

---

## IX. PUBLIC BETA READINESS CHECKLIST

### 9.1 Missing Components for Public Beta

#### ✅ **Already Implemented**
- [x] Multimodal ingestion pipeline
- [x] Scene detection (Phase 5)
- [x] Audio segmentation (Phase 0-4)
- [x] CLIP/DINO models loaded
- [x] FAISS infrastructure
- [x] Qdrant integration
- [x] Temporal index format

#### 🔄 **Phase 6 Will Add**
- [ ] Scene-level visual embeddings
- [ ] Cross-modal fusion
- [ ] Unified retrieval interface
- [ ] Multimodal search CLI

#### ⚠️ **Still Missing (Post-Phase 6)**
- [ ] Web UI for query interface
- [ ] Query result visualization (timeline, scenes)
- [ ] Export capabilities (clips, highlights)
- [ ] User documentation (tutorial, API docs)
- [ ] Error messages user-friendly
- [ ] Installation automation (one-click setup)

### 9.2 Documentation Needs

**Required Documentation:**
1. **Phase 6 Implementation Guide** - Technical deep-dive
2. **Multimodal Search Tutorial** - User guide with examples
3. **API Reference** - All retrieval functions
4. **Performance Tuning Guide** - GPU memory, batch sizes
5. **Troubleshooting Guide** - Common errors and fixes

**Estimated Effort:** 8-12 hours of documentation writing post-implementation.

### 9.3 Testing Requirements

**Unit Tests (NEW):**
- `test_scene_frame_extractor.py` - Keyframe, uniform, middle strategies
- `test_scene_embedder.py` - CLIP/DINO batch processing
- `test_embedding_pooler.py` - Mean, max, attention pooling
- `test_cross_modal_harmonizer.py` - Index building
- `test_multimodal_retriever.py` - Query execution

**Integration Tests (NEW):**
- `test_phase6_end_to_end.py` - Full video → scene embeddings → query
- `test_phase6_with_phase5.py` - Phase 5 output → Phase 6 input

**Performance Tests (NEW):**
- `test_gpu_memory_usage.py` - Validate no OOM on 4K video
- `test_batch_throughput.py` - Measure scenes/second
- `test_retrieval_latency.py` - Query response time < 200ms

**Estimated Effort:** 16-20 hours of test development and validation.

### 9.4 Entry Point Simplification

**Current State:** Requires manual conda env activation, config editing

**Public Beta Needs:**
```bash
# Ideal user experience
pip install goodq4all
goodq init  # Interactive setup wizard
goodq ingest /path/to/videos
goodq search "people eating outdoors"
```

**Blockers:**
- Conda env management too complex for average user
- Config file requires deep understanding
- No interactive setup wizard

**Recommendation:** Phase 7 should focus on packaging and UX.

---

## X. IMPLEMENTATION PLAN

### Phase 6.1: Core Infrastructure (Week 1)
**Estimated Time:** 12-16 hours

**Tasks:**
1. ✅ Create directory structure:
   - `goodq4all/steps/video/scene_frame_extractor.py`
   - `goodq4all/steps/video/scene_embedder.py`
   - `goodq4all/steps/video/embedding_pooler.py`
   - `goodq4all/steps/video/scene_visual_embeddings.py`
   - `goodq4all/steps/video/cross_modal_harmonizer.py`

2. ✅ Implement frame extraction strategies:
   - Keyframe selection (GPU optical flow)
   - Uniform sampling
   - Middle frame fallback
   - Adaptive strategy selector

3. ✅ Implement batch embedders:
   - Reuse CLIP model from `image_embed_clip.py`
   - Reuse DINO model from `image_embed_dino.py`
   - Add batch processing logic
   - Add GPU memory management

4. ✅ Implement pooling strategies:
   - Mean pooling (default)
   - Max pooling
   - Placeholder for attention pooling

5. ✅ Test individual modules:
   - Extract frames from sample video
   - Generate embeddings for frame batch
   - Pool embeddings to scene level

### Phase 6.2: Pipeline Integration (Week 1)
**Estimated Time:** 8-10 hours

**Tasks:**
1. ✅ Update `config.yaml` with Phase 6 section
2. ✅ Register steps in `step_runner.py`
3. ✅ Integrate into `ingest_multimodal_conda.py`
4. ✅ Update temporal index schema
5. ✅ Implement cross-modal harmonizer
6. ✅ Test end-to-end: video → scenes → embeddings → temporal_index.json

### Phase 6.3: Retrieval Engine (Week 2)
**Estimated Time:** 16-20 hours

**Tasks:**
1. ✅ Create `goodq4all/retrieval/multimodal_search.py`
2. ✅ Implement CLIP text encoding for queries
3. ✅ Implement multi-modal FAISS search
4. ✅ Implement score fusion strategies
5. ✅ Add metadata enrichment
6. ✅ Update `cli/retrieve.py` with multimodal command
7. ✅ Test retrieval on sample database

### Phase 6.4: Testing & Validation (Week 2)
**Estimated Time:** 12-16 hours

**Tasks:**
1. ✅ Write unit tests
2. ✅ Write integration tests
3. ✅ Performance benchmarking
4. ✅ GPU memory profiling
5. ✅ Validate on 1-hour video
6. ✅ Validate on multiple videos
7. ✅ Edge case testing (corrupted video, missing audio, etc.)

### Phase 6.5: Documentation & Polish (Week 3)
**Estimated Time:** 8-12 hours

**Tasks:**
1. ✅ Write implementation report (this document)
2. ✅ Update README with Phase 6 capabilities
3. ✅ Create multimodal search tutorial
4. ✅ Document config options
5. ✅ Create troubleshooting guide
6. ✅ Update roadmap with Phase 7 vision

**Total Estimated Time:** 56-74 hours (~2-3 weeks at 20-30 hours/week)

---

## XI. SUCCESS CRITERIA

### 11.1 Functional Requirements

- [ ] Scene-level CLIP embeddings generated for all scenes
- [ ] Scene-level DINO embeddings generated for all scenes
- [ ] Embeddings stored in FAISS indices
- [ ] Embeddings stored in Qdrant collections
- [ ] Temporal index updated with embedding metadata
- [ ] Cross-modal index built (scene ↔ text ↔ audio ↔ visual)
- [ ] Multimodal search returns relevant results
- [ ] Query latency < 500ms for 100-scene database

### 11.2 Performance Requirements

- [ ] Process 1-hour video in < 15 minutes (including all phases)
- [ ] GPU memory usage < 4GB during embedding generation
- [ ] FAISS index size < 50MB per hour of video
- [ ] Temporal index JSON < 5MB per hour of video

### 11.3 Quality Requirements

- [ ] Retrieval precision@5 > 70% (manual evaluation)
- [ ] Frame extraction success rate > 95%
- [ ] Embedding generation success rate > 98%
- [ ] Cross-modal alignment accuracy > 90%

### 11.4 Integration Requirements

- [ ] Phase 6 integrates seamlessly with Phase 5
- [ ] No breaking changes to existing pipeline
- [ ] Backward compatible with videos processed pre-Phase 6
- [ ] Config flag allows disabling Phase 6

---

## XII. NEXT STEPS (POST-PHASE 6)

### Phase 7: User Experience & Packaging
**Goal:** Make GoodQ4All accessible to non-technical users

**Planned Features:**
- One-click installer (conda-forge package or Docker)
- Interactive setup wizard
- Web UI with timeline visualization
- Query builder interface
- Export tools (clips, highlights, JSON)
- Progress indicators and user-friendly error messages

### Phase 8: Advanced Retrieval
**Goal:** State-of-the-art multimodal search

**Planned Features:**
- Fine-tuned CLIP model on user's data
- Learned fusion weights (replace manual weights)
- Temporal reasoning ("scenes before/after X")
- Negative queries ("not containing X")
- Fuzzy matching for names/places
- Query expansion and suggestion

### Phase 9: Knowledge Graph Enhancement
**Goal:** Rich semantic relationships

**Planned Features:**
- Entity co-occurrence graphs
- Temporal relationship extraction
- Cross-video entity resolution
- Event timeline reconstruction
- Automated highlight generation

### Phase 10: Community & Ecosystem
**Goal:** Build open-source community

**Planned Features:**
- Plugin architecture for custom analyzers
- Contributed model zoo
- Shared datasets for benchmarking
- Community forum
- Regular release schedule

---

## XIII. CONCLUSION

Phase 6 represents the **final major technical milestone** before public beta release. Upon completion, GoodQ4All will have:

✅ **End-to-end multimodal ingestion** (video, audio, image, text)  
✅ **Scene-level visual embeddings** (CLIP, DINO)  
✅ **Cross-modal retrieval** (visual ↔ audio ↔ text)  
✅ **Unified temporal index** (frame-level precision)  
✅ **Production-ready pipeline** (validated on archival video)

**Remaining Work for Public Beta:**
- Phase 6 implementation (56-74 hours)
- Documentation (8-12 hours)
- Testing (12-16 hours)
- **Total: ~80-100 hours** (~3-4 weeks at 20-30 hours/week)

**Post-Beta Roadmap:**
- Phase 7: UX & Packaging (installer, web UI)
- Phase 8: Advanced retrieval (fine-tuning, temporal reasoning)
- Phase 9: Knowledge graph enhancement
- Phase 10: Community building

---

## XIV. APPROVAL REQUIRED

This analysis is **COMPLETE and READY FOR IMPLEMENTATION**.

**Decision Points:**
1. ✅ Approve Phase 6 architecture as designed
2. ✅ Approve file structure and module naming
3. ✅ Approve config schema additions
4. ✅ Approve pipeline integration points
5. ✅ Approve retrieval engine design

**Upon approval, I will:**
1. Create all module files with full implementations (no placeholders)
2. Update config.yaml, step_runner.py, ingest_multimodal_conda.py
3. Run syntax validation (`python -m py_compile`)
4. Create integration tests
5. Generate implementation report
6. Commit and push to repository

**Awaiting user command to proceed with Phase 6 implementation.**

---

**Report Generated:** December 5, 2025  
**Author:** GitHub Copilot CLI (Codex Agent)  
**Version:** 1.0.0  
**Status:** ANALYSIS COMPLETE - READY FOR IMPLEMENTATION
