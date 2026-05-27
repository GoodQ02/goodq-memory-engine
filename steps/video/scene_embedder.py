"""
Phase 6: Scene Embedder
Generates CLIP and DINO embeddings for video scene frames.
Runs in the visual embedding environment with batch processing for GPU efficiency.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import os
import logging
import numpy as np

logger = logging.getLogger(__name__)

# Global model cache
_MODELS = {
    "clip": {"model": None, "processor": None, "device": "cpu"},
    "dino": {"model": None, "processor": None, "device": "cpu"}
}


def _resolve_model_device(step_name: str) -> str:
    """
    Resolve the execution device for Phase 6 model loading.

    Prefer the shared GPU manager so we preserve per-step budgeting, but do not
    let its import-time auto-configuration abort Phase 6a. If the GPU manager is
    unavailable, fall back to a direct torch CUDA probe and then CPU.
    """
    try:
        from steps.common.gpu_config import configure_gpu as setup_step_gpu
    except Exception as e:
        logger.warning(
            "[PHASE6] GPU manager unavailable for %s; falling back to direct torch probe "
            "exc_type=%s exc=%s",
            step_name,
            type(e).__name__,
            e,
        )
    else:
        try:
            gpu_config = setup_step_gpu(step_name)
            return str(gpu_config.get("device", "cpu"))
        except Exception as e:
            logger.warning(
                "[PHASE6] GPU manager failed for %s; falling back to direct torch probe "
                "exc_type=%s exc=%s",
                step_name,
                type(e).__name__,
                e,
            )

    try:
        import torch

        if torch.cuda.is_available():
            return "cuda:0"
    except Exception as e:
        logger.warning(
            "[PHASE6] Torch device probe failed for %s; using CPU "
            "exc_type=%s exc=%s",
            step_name,
            type(e).__name__,
            e,
        )

    return "cpu"


def _load_clip_model():
    """Load CLIP model using GPU manager."""
    if _MODELS["clip"]["model"] is not None:
        return

    device = _resolve_model_device("scene_embedder_clip")
    
    try:
        import torch
        from transformers import CLIPModel, CLIPProcessor
        from pathlib import Path
        import yaml
        
        # Resolve repo_id from registry
        repo_root = Path(__file__).resolve().parents[2]
        registry_path = repo_root / "configs" / "model_registry.yaml"
        repo_id = "openai/clip-vit-large-patch14"  # Default fallback
        if registry_path.exists():
            try:
                with open(registry_path, "r", encoding="utf-8") as f:
                    registry = yaml.safe_load(f) or {}
                repo_id = registry.get("huggingface_models", {}).get("clip_vit", {}).get("repo_id") or repo_id
            except Exception:
                pass
        
        processor = CLIPProcessor.from_pretrained(repo_id)
        try:
            model = CLIPModel.from_pretrained(repo_id, use_safetensors=True)
        except Exception as safetensors_exc:
            logger.warning(
                "[PHASE6] CLIP safetensors load unavailable; falling back to cached default weights "
                "exc_type=%s exc=%s",
                type(safetensors_exc).__name__,
                safetensors_exc,
            )
            model = CLIPModel.from_pretrained(repo_id)
        model = model.to(device).eval()
        
        _MODELS["clip"].update({
            "model": model,
            "processor": processor,
            "device": device
        })
        
        logger.info(f"[OK] CLIP model ({repo_id}) loaded on {device}")
    except Exception as e:
        logger.error(f"[FAIL] Failed to load CLIP model: {e}")
        _MODELS["clip"].update({"model": None, "processor": None, "device": "cpu"})


def _load_dino_model():
    """Load DINO model using GPU manager."""
    if _MODELS["dino"]["model"] is not None:
        return

    device = _resolve_model_device("scene_embedder_dino")
    
    try:
        import torch
        from transformers import AutoImageProcessor, AutoModel
        from pathlib import Path
        import yaml
        
        # Resolve repo_id from registry
        repo_root = Path(__file__).resolve().parents[2]
        registry_path = repo_root / "configs" / "model_registry.yaml"
        repo_id = "facebook/dinov2-large"  # Default fallback
        if registry_path.exists():
            try:
                with open(registry_path, "r", encoding="utf-8") as f:
                    registry = yaml.safe_load(f) or {}
                repo_id = registry.get("huggingface_models", {}).get("dinov2", {}).get("repo_id") or repo_id
            except Exception:
                pass
        
        processor = AutoImageProcessor.from_pretrained(repo_id)
        model = AutoModel.from_pretrained(repo_id).to(device).eval()
        
        _MODELS["dino"].update({
            "model": model,
            "processor": processor,
            "device": device
        })
        
        logger.info(f"[OK] DINO model ({repo_id}) loaded on {device}")
    except Exception as e:
        logger.error(f"[FAIL] Failed to load DINO model: {e}")
        _MODELS["dino"].update({"model": None, "processor": None, "device": "cpu"})


def embed_frames_clip(frame_paths: List[str], batch_size: int = 8) -> List[np.ndarray]:
    """
    Generate CLIP embeddings for a list of frame images with AMP and zero-vector fallbacks.
    
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
    from contextlib import nullcontext
    
    model = _MODELS["clip"]["model"]
    processor = _MODELS["clip"]["processor"]
    device = _MODELS["clip"]["device"]
    
    # Resolve expected projection dimension (default to 768 for Large, 512 for Base)
    dim = getattr(model.config, "projection_dim", 768)
    amp_enabled = (device == "cuda") and (os.getenv("GOODQ_CLIP_DISABLE_AMP", "").strip() != "1")
    autocast_ctx = torch.amp.autocast(device_type="cuda", dtype=torch.float16) if amp_enabled else nullcontext()
    
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
            # All frames in batch failed to load - pad with zero vectors
            embeddings.extend([np.zeros(dim) for _ in range(len(batch_paths))])
            continue
        
        # Process batch
        try:
            inputs = processor(images=images, return_tensors="pt", padding=True)
            inputs = {k: v.to(device) for k, v in inputs.items()}

            with torch.inference_mode():
                with autocast_ctx:
                    outputs = model.get_image_features(**inputs)

            # transformers may return either a tensor or an output object with pooler_output.
            if hasattr(outputs, "pooler_output"):
                features = outputs.pooler_output
            elif isinstance(outputs, tuple):
                features = outputs[0]
            else:
                features = outputs

            if not torch.is_tensor(features):
                raise TypeError(f"Unexpected CLIP output type: {type(features).__name__}")

            batch_embeddings = features.detach().cpu().numpy().astype("float32")

            # Normalize embeddings
            norms = np.linalg.norm(batch_embeddings, axis=1, keepdims=True)
            batch_embeddings = batch_embeddings / (norms + 1e-8)

            # Re-align in case some images failed to load during batch loop
            aligned_batch = []
            img_idx = 0
            for idx in range(len(batch_paths)):
                if idx in valid_indices:
                    aligned_batch.append(batch_embeddings[img_idx])
                    img_idx += 1
                else:
                    aligned_batch.append(np.zeros(dim))
            embeddings.extend(aligned_batch)

        except Exception as e:
            logger.error(f"CLIP embedding batch failed: {e}")
            # Pad entire batch with zero vectors to prevent index misalignment
            embeddings.extend([np.zeros(dim) for _ in range(len(batch_paths))])
    
    logger.info(f"Generated {len(embeddings)} CLIP embeddings")
    return embeddings


def embed_frames_dino(frame_paths: List[str], batch_size: int = 8) -> List[np.ndarray]:
    """
    Generate DINO embeddings for a list of frame images with AMP and dynamic dims.
    
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
    from contextlib import nullcontext
    
    model = _MODELS["dino"]["model"]
    processor = _MODELS["dino"]["processor"]
    device = _MODELS["dino"]["device"]
    
    # Resolve expected hidden_size (default to 1024 for Large, 768 for Base)
    dim = getattr(model.config, "hidden_size", 1024)
    amp_enabled = (device == "cuda") and (os.getenv("GOODQ_DINO_DISABLE_AMP", "").strip() != "1")
    autocast_ctx = torch.amp.autocast(device_type="cuda", dtype=torch.float16) if amp_enabled else nullcontext()
    
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
            # All frames in batch failed to load - pad with zero vectors
            embeddings.extend([np.zeros(dim) for _ in range(len(batch_paths))])
            continue
        
        # Process batch
        try:
            inputs = processor(images=images, return_tensors="pt")
            inputs = {k: v.to(device) for k, v in inputs.items()}
            
            with torch.inference_mode():
                with autocast_ctx:
                    outputs = model(**inputs)
                    # Use CLS token (first token) as image embedding
                    batch_embeddings = outputs.last_hidden_state[:, 0].cpu().numpy().astype("float32")
            
            # Normalize embeddings
            norms = np.linalg.norm(batch_embeddings, axis=1, keepdims=True)
            batch_embeddings = batch_embeddings / (norms + 1e-8)
            
            # Re-align in case some images failed to load during batch loop
            aligned_batch = []
            img_idx = 0
            for idx in range(len(batch_paths)):
                if idx in valid_indices:
                    aligned_batch.append(batch_embeddings[img_idx])
                    img_idx += 1
                else:
                    aligned_batch.append(np.zeros(dim))
            embeddings.extend(aligned_batch)
            
        except Exception as e:
            logger.error(f"DINO embedding batch failed: {e}")
            # Add zero embeddings for failed batch to keep alignment
            embeddings.extend([np.zeros(dim) for _ in range(len(batch_paths))])
    
    logger.info(f"Generated {len(embeddings)} DINO embeddings")
    return embeddings


def embed_scene_frames(
    scene_frames: Dict[int, List[Dict[str, Any]]],
    model_type: str = 'clip',
    batch_size: int = 8
) -> Dict[int, List[np.ndarray]]:
    """
    Generate embeddings for all frames across multiple scenes in flattened batches.
    
    Args:
        scene_frames: Dict mapping scene_id -> list of frame metadata dicts
        model_type: 'clip' or 'dino'
        batch_size: Batch size for GPU processing
        
    Returns:
        Dict mapping scene_id -> list of embedding vectors
    """
    # 1. Flatten all frames across all scenes to process in a single unified sequence
    flat_frames = []  # list of tuples (scene_id, frame_idx, path)
    for scene_id, frames in scene_frames.items():
        if not isinstance(frames, list):
            continue
        for idx, f in enumerate(frames):
            if isinstance(f, dict) and 'path' in f:
                flat_frames.append((scene_id, idx, f['path']))
                
    if not flat_frames:
        logger.warning(f"[PHASE6] embed_scene_frames: No valid frames found across any scenes")
        return {}
        
    logger.info(f"[PHASE6] Embedding {len(flat_frames)} frames across {len(scene_frames)} scenes with {model_type.upper()} in parallel batches (size={batch_size})")
    
    # 2. Extract just the paths for the batched embedding functions
    frame_paths = [path for _, _, path in flat_frames]
    
    # 3. Process the entire sequence of frames
    if model_type == 'dino':
        all_embeddings = embed_frames_dino(frame_paths, batch_size)
    else:  # clip (default)
        all_embeddings = embed_frames_clip(frame_paths, batch_size)
        
    # 4. Map the resulting embeddings back to their respective scenes
    scene_embeddings = {scene_id: [] for scene_id in scene_frames}
    for i, (scene_id, idx, path) in enumerate(flat_frames):
        if i < len(all_embeddings):
            scene_embeddings[scene_id].append(all_embeddings[i])
        else:
            # Fallback in case of list length mismatch (should not happen with zero-vector padding)
            dim = 1024 if model_type == 'dino' else 768
            scene_embeddings[scene_id].append(np.zeros(dim))
            
    return scene_embeddings
