"""
Phase 6: Scene Embedder
Generates CLIP and DINO embeddings for video scene frames.
Runs on goodq_core (CUDA 12.1) with batch processing for GPU efficiency.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import os
import logging
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Global model cache
_MODELS = {
    "clip": {"model": None, "processor": None, "device": "cpu"},
    "dino": {"model": None, "processor": None, "device": "cpu"}
}


def _load_clip_model():
    """Load CLIP model using GPU manager."""
    if _MODELS["clip"]["model"] is not None:
        return
    
    try:
        from steps.common.gpu_config import configure_gpu as setup_step_gpu
    except ImportError:
        def setup_step_gpu(name):
            return {"device": "cpu", "step_name": name}
    
    gpu_config = setup_step_gpu("scene_embedder_clip")
    device = gpu_config["device"]
    
    try:
        import torch
        from transformers import CLIPModel, CLIPProcessor
        
        processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch16")
        model = CLIPModel.from_pretrained("openai/clip-vit-base-patch16", use_safetensors=True).to(device).eval()
        
        _MODELS["clip"].update({
            "model": model,
            "processor": processor,
            "device": device
        })
        
        logger.info(f"[OK] CLIP model loaded on {device}")
    except Exception as e:
        logger.error(f"[FAIL] Failed to load CLIP model: {e}")
        _MODELS["clip"].update({"model": None, "processor": None, "device": "cpu"})


def _load_dino_model():
    """Load DINO model using GPU manager."""
    if _MODELS["dino"]["model"] is not None:
        return
    
    try:
        from steps.common.gpu_config import configure_gpu as setup_step_gpu
    except ImportError:
        def setup_step_gpu(name):
            return {"device": "cpu", "step_name": name}
    
    gpu_config = setup_step_gpu("scene_embedder_dino")
    device = gpu_config["device"]
    
    try:
        import torch
        from transformers import AutoImageProcessor, AutoModel
        
        processor = AutoImageProcessor.from_pretrained("facebook/dinov2-base")
        model = AutoModel.from_pretrained("facebook/dinov2-base").to(device).eval()
        
        _MODELS["dino"].update({
            "model": model,
            "processor": processor,
            "device": device
        })
        
        logger.info(f"[OK] DINO model loaded on {device}")
    except Exception as e:
        logger.error(f"[FAIL] Failed to load DINO model: {e}")
        _MODELS["dino"].update({"model": None, "processor": None, "device": "cpu"})


def embed_frames_clip(frame_paths: List[str], batch_size: int = 8) -> List[np.ndarray]:
    """
    Generate CLIP embeddings for a list of frame images.
    
    Args:
        frame_paths: List of paths to frame images
        batch_size: Batch size for GPU processing
        
    Returns:
        List of CLIP embedding vectors
    """
    _load_clip_model()
    
    if _MODELS["clip"]["model"] is None:
        logger.warning("CLIP model unavailable, returning empty embeddings")
        return []
    
    import torch
    from PIL import Image
    
    model = _MODELS["clip"]["model"]
    processor = _MODELS["clip"]["processor"]
    device = _MODELS["clip"]["device"]
    
    embeddings = []
    
    # Process in batches
    for i in range(0, len(frame_paths), batch_size):
        batch_paths = frame_paths[i:i + batch_size]
        
        # Load images
        images = []
        valid_indices = []
        for idx, path in enumerate(batch_paths):
            try:
                img = Image.open(path).convert("RGB")
                images.append(img)
                valid_indices.append(idx)
            except Exception as e:
                logger.warning(f"Failed to load frame {path}: {e}")
        
        if not images:
            continue
        
        # Process batch
        try:
            inputs = processor(images=images, return_tensors="pt", padding=True)
            inputs = {k: v.to(device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = model.get_image_features(**inputs)
                batch_embeddings = outputs.cpu().numpy()
            
            # Normalize embeddings
            norms = np.linalg.norm(batch_embeddings, axis=1, keepdims=True)
            batch_embeddings = batch_embeddings / (norms + 1e-8)
            
            embeddings.extend(batch_embeddings)
            
        except Exception as e:
            logger.error(f"CLIP embedding batch failed: {e}")
            # Add zero embeddings for failed batch
            embeddings.extend([np.zeros(512) for _ in range(len(images))])
    
    logger.info(f"Generated {len(embeddings)} CLIP embeddings")
    return embeddings


def embed_frames_dino(frame_paths: List[str], batch_size: int = 8) -> List[np.ndarray]:
    """
    Generate DINO embeddings for a list of frame images.
    
    Args:
        frame_paths: List of paths to frame images
        batch_size: Batch size for GPU processing
        
    Returns:
        List of DINO embedding vectors
    """
    _load_dino_model()
    
    if _MODELS["dino"]["model"] is None:
        logger.warning("DINO model unavailable, returning empty embeddings")
        return []
    
    import torch
    from PIL import Image
    
    model = _MODELS["dino"]["model"]
    processor = _MODELS["dino"]["processor"]
    device = _MODELS["dino"]["device"]
    
    embeddings = []
    
    # Process in batches
    for i in range(0, len(frame_paths), batch_size):
        batch_paths = frame_paths[i:i + batch_size]
        
        # Load images
        images = []
        valid_indices = []
        for idx, path in enumerate(batch_paths):
            try:
                img = Image.open(path).convert("RGB")
                images.append(img)
                valid_indices.append(idx)
            except Exception as e:
                logger.warning(f"Failed to load frame {path}: {e}")
        
        if not images:
            continue
        
        # Process batch
        try:
            inputs = processor(images=images, return_tensors="pt")
            inputs = {k: v.to(device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = model(**inputs)
                # Use CLS token (first token) as image embedding
                batch_embeddings = outputs.last_hidden_state[:, 0].cpu().numpy()
            
            # Normalize embeddings
            norms = np.linalg.norm(batch_embeddings, axis=1, keepdims=True)
            batch_embeddings = batch_embeddings / (norms + 1e-8)
            
            embeddings.extend(batch_embeddings)
            
        except Exception as e:
            logger.error(f"DINO embedding batch failed: {e}")
            # Add zero embeddings for failed batch
            embeddings.extend([np.zeros(768) for _ in range(len(images))])
    
    logger.info(f"Generated {len(embeddings)} DINO embeddings")
    return embeddings


def embed_scene_frames(
    scene_frames: Dict[int, List[Dict[str, Any]]],
    model_type: str = 'clip',
    batch_size: int = 8
) -> Dict[int, List[np.ndarray]]:
    """
    Generate embeddings for all frames across multiple scenes.
    
    Args:
        scene_frames: Dict mapping scene_id -> list of frame metadata dicts
        model_type: 'clip' or 'dino'
        batch_size: Batch size for GPU processing
        
    Returns:
        Dict mapping scene_id -> list of embedding vectors
    """
    scene_embeddings = {}
    
    for scene_id, frames in scene_frames.items():
        frame_paths = [f['path'] for f in frames if 'path' in f]
        
        if not frame_paths:
            logger.warning(f"Scene {scene_id}: No valid frame paths")
            continue
        
        logger.info(f"Scene {scene_id}: Embedding {len(frame_paths)} frames with {model_type.upper()}")
        
        if model_type == 'dino':
            embeddings = embed_frames_dino(frame_paths, batch_size)
        else:  # clip (default)
            embeddings = embed_frames_clip(frame_paths, batch_size)
        
        if embeddings:
            scene_embeddings[scene_id] = embeddings
    
    return scene_embeddings
