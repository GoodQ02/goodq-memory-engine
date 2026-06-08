from __future__ import annotations

import pytest
import sys
import importlib.util
from pathlib import Path
from fastapi import HTTPException
from unittest.mock import MagicMock, patch
import asyncio

def _load_route_module(module_name: str):
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    module_path = repo_root / "api" / "routes" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"tests.{module_name}_route", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

media_module = _load_route_module("media")

def test_media_get_scene_frame_contained(tmp_path):
    data_root = (tmp_path / "data").resolve()
    data_root.mkdir(parents=True, exist_ok=True)
    frame_path = data_root / "video_1" / "scene_0" / "frame_0.jpg"
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    frame_path.write_bytes(b"image")

    mock_loader = MagicMock()
    mock_loader.data_root = data_root
    mock_loader.get_frame_path.return_value = frame_path

    with patch.object(media_module, "get_data_loader", return_value=mock_loader):
        res = asyncio.run(media_module.get_scene_frame("video_1", 0, 0))
        assert res.path == str(frame_path)

def test_media_get_scene_frame_escaped(tmp_path):
    data_root = (tmp_path / "data").resolve()
    data_root.mkdir(parents=True, exist_ok=True)
    # File sits outside data_root
    frame_path = (tmp_path / "outside" / "frame_0.jpg").resolve()
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    frame_path.write_bytes(b"image")

    mock_loader = MagicMock()
    mock_loader.data_root = data_root
    mock_loader.get_frame_path.return_value = frame_path

    with patch.object(media_module, "get_data_loader", return_value=mock_loader):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(media_module.get_scene_frame("video_1", 0, 0))
        assert exc.value.status_code == 403
        assert "Access denied" in exc.value.detail

def test_media_get_audio_chunk_contained(tmp_path):
    data_root = (tmp_path / "data").resolve()
    data_root.mkdir(parents=True, exist_ok=True)
    chunk_path = data_root / "video_1" / "audio" / "chunk_0.wav"
    chunk_path.parent.mkdir(parents=True, exist_ok=True)
    chunk_path.write_bytes(b"audio")

    mock_loader = MagicMock()
    mock_loader.data_root = data_root
    mock_loader.get_audio_chunk_path.return_value = chunk_path

    with patch.object(media_module, "get_data_loader", return_value=mock_loader):
        res = asyncio.run(media_module.get_audio_chunk("video_1", 0))
        assert res.path == str(chunk_path)

def test_media_get_audio_chunk_escaped(tmp_path):
    data_root = (tmp_path / "data").resolve()
    data_root.mkdir(parents=True, exist_ok=True)
    chunk_path = (tmp_path / "outside" / "chunk_0.wav").resolve()
    chunk_path.parent.mkdir(parents=True, exist_ok=True)
    chunk_path.write_bytes(b"audio")

    mock_loader = MagicMock()
    mock_loader.data_root = data_root
    mock_loader.get_audio_chunk_path.return_value = chunk_path

    with patch.object(media_module, "get_data_loader", return_value=mock_loader):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(media_module.get_audio_chunk("video_1", 0))
        assert exc.value.status_code == 403
        assert "Access denied" in exc.value.detail
