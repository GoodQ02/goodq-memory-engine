from __future__ import annotations
import sys
import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image

import steps.video.scene_embedder as scene_embedder
import steps.video.embedding_pooler as embedding_pooler


def test_embed_frames_clip_isolation(monkeypatch):
    """
    Test that frame-level failures (e.g. image loading exceptions)
    return structured error dictionaries, and do not crash the batch.
    """
    # Mock models and processor
    mock_model = MagicMock()
    mock_model.config.projection_dim = 512
    
    # Mock the CLIP get_image_features output
    mock_output = MagicMock()
    mock_output.pooler_output = MagicMock()
    mock_output.pooler_output.detach().cpu().numpy.return_value = np.ones((2, 512), dtype=np.float32)
    mock_model.get_image_features.return_value = mock_output
    
    mock_proc = MagicMock()
    mock_proc.return_value = {}
    
    # Inject mock CLIP model and config
    scene_embedder._MODELS["clip"] = {
        "model": mock_model,
        "processor": mock_proc,
        "device": "cpu"
    }
    
    # Mock Image.open to fail for one image, succeed for two
    original_open = Image.open
    def fake_open(fp):
        if "fail" in str(fp):
            raise FileNotFoundError("Mock image load failure")
        # Return a small mock image
        return Image.new("RGB", (10, 10))
        
    monkeypatch.setattr(Image, "open", fake_open)
    
    try:
        frame_paths = ["/path/to/img1.jpg", "/path/to/img_fail.jpg", "/path/to/img2.jpg"]
        results = scene_embedder.embed_frames_clip(frame_paths, batch_size=3)
        
        assert len(results) == 3
        # First and third should be valid normalized numpy arrays
        assert isinstance(results[0], np.ndarray)
        assert results[0].shape == (512,)
        assert isinstance(results[2], np.ndarray)
        assert results[2].shape == (512,)
        
        # Second should be a structured error dict
        assert isinstance(results[1], dict)
        assert results[1]["status"] == "error"
        assert "FileNotFoundError" in results[1]["exc_type"]
        assert results[1]["modality"] == "clip"
        assert results[1]["path"] == "/path/to/img_fail.jpg"
        
    finally:
        scene_embedder._MODELS["clip"] = {"model": None, "processor": None, "device": "cpu"}


def test_embed_frames_clip_batch_fallback(monkeypatch):
    """
    Test that if batch inference fails, the system retries individual images,
    isolating the single failing frame while returning successful ones.
    """
    # Mock model where batch inference fails, but individual inference succeeds
    mock_model = MagicMock()
    mock_model.config.projection_dim = 512
    
    def fake_get_image_features(**kwargs):
        # Inspect how many images are passed.
        # If kwargs contains multiple images (e.g. pixel_values has batch dimension > 1,
        # or we simulate via a flag), we fail.
        # Let's count calls or check tensor shape.
        pixel_values = kwargs.get("pixel_values")
        # In mock_proc we'll mock pixel_values to have a shape matching number of inputs
        if pixel_values is not None and pixel_values.shape[0] > 1:
            raise RuntimeError("Mock batch inference CUDA OOM / corruption error")
        
        # Single image inference
        mock_output = MagicMock()
        mock_output.pooler_output = MagicMock()
        mock_output.pooler_output.detach().cpu().numpy.return_value = np.ones((1, 512), dtype=np.float32)
        return mock_output

    mock_model.get_image_features.side_effect = fake_get_image_features
    
    # Mock processor to return a dict with mock tensor support for to()
    def fake_proc(images, **kwargs):
        num_images = len(images) if isinstance(images, list) else 1
        mock_tensor = MagicMock()
        # Mock shape to behave like a tensor shape where index 0 is batch dimension
        mock_tensor.shape = (num_images, 3, 224, 224)
        mock_tensor.to.return_value = mock_tensor
        return {"pixel_values": mock_tensor}
        
    mock_proc = fake_proc
    
    # Mock Image.open
    def fake_open(fp):
        if "bad_inference" in str(fp):
            # To simulate an individual inference failure, we can make fake_get_image_features raise
            # when this specific path is processed, or simply fail the open.
            # Let's fail the open for bad_inference to test mixed loading / inference failures
            raise ValueError("Corrupt file on load")
        return Image.new("RGB", (10, 10))
        
    monkeypatch.setattr(Image, "open", fake_open)
    
    # Inject mock
    scene_embedder._MODELS["clip"] = {
        "model": mock_model,
        "processor": mock_proc,
        "device": "cpu"
    }
    
    # Also patch torch.is_tensor and torch.amp.autocast to bypass torch internals
    monkeypatch.setattr("torch.is_tensor", lambda x: True)
    
    try:
        frame_paths = ["/path/to/img1.jpg", "/path/to/bad_inference.jpg", "/path/to/img2.jpg"]
        results = scene_embedder.embed_frames_clip(frame_paths, batch_size=3)
        
        assert len(results) == 3
        # img1 and img2 should succeed because individual inference succeeded
        assert isinstance(results[0], np.ndarray)
        assert results[0].shape == (512,)
        assert isinstance(results[2], np.ndarray)
        assert results[2].shape == (512,)
        
        # bad_inference should be an error
        assert isinstance(results[1], dict)
        assert results[1]["status"] == "error"
        assert results[1]["path"] == "/path/to/bad_inference.jpg"
        
    finally:
        scene_embedder._MODELS["clip"] = {"model": None, "processor": None, "device": "cpu"}


def test_pool_multiple_scenes_validation(monkeypatch):
    """
    Test that pool_multiple_scenes filters out structured error dictionaries,
    invalid array shapes, and non-finite values (infs/NaNs), pooling only the valid arrays.
    It should also enforce MIN_VALID_VISUAL_FRAMES threshold.
    """
    # 512-dim vectors
    vec_valid1 = np.ones(512, dtype=np.float32)
    vec_valid2 = np.ones(512, dtype=np.float32) * 2.0
    
    # Invalid arrays
    vec_wrong_dim = np.ones((512, 1), dtype=np.float32)  # 2D instead of 1D
    vec_nan = np.array([np.nan] * 512, dtype=np.float32)
    vec_inf = np.array([np.inf] * 512, dtype=np.float32)
    
    # Error dict
    error_dict = {
        "status": "error",
        "error": "Failed to load image",
        "path": "/some/path",
        "modality": "clip"
    }
    
    # Prepare scene frame embeddings
    scene_frame_embeddings = {
        1: [vec_valid1, error_dict, vec_valid2],  # Valid mean is 1.5
        2: [vec_wrong_dim, vec_nan, vec_inf],      # No valid embeddings
        3: [vec_valid1],                           # 1 valid embedding
    }
    
    # Run with default MIN_VALID_VISUAL_FRAMES = 1
    pooled = embedding_pooler.pool_multiple_scenes(scene_frame_embeddings, strategy="mean", min_valid_visual_frames=1)
    
    # Scene 1: Valid pooled array should exist, and mean of 1 and 2 is 1.5
    assert 1 in pooled
    assert pooled[1].shape == (512,)
    assert np.allclose(pooled[1], 1.5)
    
    # Scene 2: Omitted because it has 0 valid embeddings
    assert 2 not in pooled
    
    # Scene 3: Pooled successfully with 1 frame
    assert 3 in pooled
    assert np.allclose(pooled[3], 1.0)
    
    # Run with MIN_VALID_VISUAL_FRAMES = 2
    pooled_strict = embedding_pooler.pool_multiple_scenes(scene_frame_embeddings, strategy="mean", min_valid_visual_frames=2)
    
    # Scene 1 has 2 valid frames (vec_valid1 and vec_valid2), so it is included
    assert 1 in pooled_strict
    # Scene 3 has only 1 valid frame, so it should be omitted under strict policy!
    assert 3 not in pooled_strict
