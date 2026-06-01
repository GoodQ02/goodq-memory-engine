"""
Phase 6: Embedding Pooler
Aggregates multiple frame embeddings into scene-level representations.
Supports mean, max, concat, and attention-based pooling.
"""
from __future__ import annotations
from typing import List, Dict, Any
import numpy as np
import logging

logger = logging.getLogger(__name__)


def pool_embeddings_mean(embeddings: List[np.ndarray]) -> np.ndarray:
    """
    Average pooling across frame embeddings.
    
    Args:
        embeddings: List of embedding vectors
        
    Returns:
        Mean-pooled embedding vector
    """
    if not embeddings:
        raise ValueError("Cannot pool empty embedding list")
    
    stacked = np.stack(embeddings, axis=0)
    return np.mean(stacked, axis=0)


def pool_embeddings_max(embeddings: List[np.ndarray]) -> np.ndarray:
    """
    Max pooling across frame embeddings.
    
    Args:
        embeddings: List of embedding vectors
        
    Returns:
        Max-pooled embedding vector
    """
    if not embeddings:
        raise ValueError("Cannot pool empty embedding list")
    
    stacked = np.stack(embeddings, axis=0)
    return np.max(stacked, axis=0)


def pool_embeddings_concat(embeddings: List[np.ndarray], max_frames: int = 5) -> np.ndarray:
    """
    Concatenate frame embeddings (truncate if too many).
    
    Args:
        embeddings: List of embedding vectors
        max_frames: Maximum number of frames to concatenate
        
    Returns:
        Concatenated embedding vector
    """
    if not embeddings:
        raise ValueError("Cannot pool empty embedding list")
    
    # Truncate or pad to max_frames
    if len(embeddings) > max_frames:
        embeddings = embeddings[:max_frames]
    elif len(embeddings) < max_frames:
        # Pad with zeros
        dim = embeddings[0].shape[0]
        padding = [np.zeros(dim) for _ in range(max_frames - len(embeddings))]
        embeddings = embeddings + padding
    
    return np.concatenate(embeddings, axis=0)


def pool_embeddings_attention(embeddings: List[np.ndarray], temperature: float = 1.0) -> np.ndarray:
    """
    Attention-weighted pooling using simple self-attention.
    
    Args:
        embeddings: List of embedding vectors
        temperature: Temperature for softmax attention weights
        
    Returns:
        Attention-pooled embedding vector
    """
    if not embeddings:
        raise ValueError("Cannot pool empty embedding list")
    
    if len(embeddings) == 1:
        return embeddings[0]
    
    stacked = np.stack(embeddings, axis=0)  # Shape: (num_frames, dim)
    
    # Compute attention scores (simplified: use mean as query)
    query = np.mean(stacked, axis=0, keepdims=True)  # Shape: (1, dim)
    
    # Compute similarities (dot product)
    scores = np.dot(stacked, query.T).squeeze()  # Shape: (num_frames,)
    
    # Apply temperature and softmax
    scores = scores / temperature
    exp_scores = np.exp(scores - np.max(scores))  # Numerical stability
    attention_weights = exp_scores / np.sum(exp_scores)
    
    # Weighted sum
    pooled = np.sum(stacked * attention_weights[:, np.newaxis], axis=0)
    
    return pooled


def pool_scene_embeddings(
    frame_embeddings: List[np.ndarray],
    strategy: str = 'mean',
    **kwargs
) -> np.ndarray:
    """
    Main entry point for scene-level embedding pooling.
    
    Args:
        frame_embeddings: List of frame embedding vectors
        strategy: Pooling strategy ('mean', 'max', 'concat', 'attention')
        **kwargs: Additional parameters for specific strategies
        
    Returns:
        Scene-level embedding vector
    """
    if not frame_embeddings:
        raise ValueError("Cannot pool empty frame embedding list")
    
    logger.info(f"Pooling {len(frame_embeddings)} frame embeddings using '{strategy}' strategy")
    
    if strategy == 'max':
        return pool_embeddings_max(frame_embeddings)
    elif strategy == 'concat':
        max_frames = kwargs.get('max_frames', 5)
        return pool_embeddings_concat(frame_embeddings, max_frames)
    elif strategy == 'attention':
        temperature = kwargs.get('temperature', 1.0)
        return pool_embeddings_attention(frame_embeddings, temperature)
    else:  # 'mean' (default)
        return pool_embeddings_mean(frame_embeddings)


MIN_VALID_VISUAL_FRAMES = 1


def pool_multiple_scenes(
    scene_frame_embeddings: Dict[int, List[Any]],
    strategy: str = 'mean',
    **kwargs
) -> Dict[int, np.ndarray]:
    """
    Pool embeddings for multiple scenes, enforcing MIN_VALID_VISUAL_FRAMES and validating array types.
    
    Args:
        scene_frame_embeddings: Dict mapping scene_id -> list of frame embeddings/errors
        strategy: Pooling strategy
        **kwargs: Additional pooling parameters (e.g. cfg, min_valid_visual_frames)
        
    Returns:
        Dict mapping scene_id -> pooled scene embedding
    """
    pooled_scenes = {}
    
    cfg = kwargs.get('cfg')
    min_valid = MIN_VALID_VISUAL_FRAMES
    if isinstance(cfg, dict):
        min_valid = cfg.get('phase6', {}).get('min_valid_visual_frames', min_valid)
    # Support direct kwarg override
    min_valid = kwargs.get('min_valid_visual_frames', min_valid)
    
    for scene_id, frame_embeds in scene_frame_embeddings.items():
        if frame_embeds:
            # Coerce lists of floats (e.g. from mock tests) to numpy arrays for compatibility
            coerced_embeds = [
                np.array(emb, dtype=np.float32) if isinstance(emb, list) else emb
                for emb in frame_embeds
            ]
            
            # Filter and validate arrays strictly (must be 1D, containing only finite numbers)
            valid_embeds = [
                emb for emb in coerced_embeds 
                if isinstance(emb, np.ndarray) and emb.ndim == 1 and np.all(np.isfinite(emb))
            ]
            
            if len(valid_embeds) < min_valid:
                logger.warning(
                    f"Scene {scene_id} skipped: Insufficient valid frame embeddings "
                    f"({len(valid_embeds)} valid arrays found, required minimum is {min_valid})"
                )
                continue
                
            try:
                pooled = pool_scene_embeddings(valid_embeds, strategy, **kwargs)
                pooled_scenes[scene_id] = pooled
                logger.info(f"Scene {scene_id}: Pooled {len(valid_embeds)} frames -> {pooled.shape}")
            except Exception as e:
                logger.error(f"Failed to pool embeddings for scene {scene_id}: {e}")
    
    return pooled_scenes
