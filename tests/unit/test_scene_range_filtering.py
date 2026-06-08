from __future__ import annotations

import pytest
import sys
import importlib.util
from pathlib import Path
from typing import Dict, Any

def _load_module(module_name: str):
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    module_path = repo_root / "cli" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"cli.{module_name}", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

run_ingestion_module = _load_module("run_ingestion")

def test_scene_index_range_filtering():
    # Simulate the filtering logic added to run_ingestion.py
    scenes = [
        {"index": 0, "start": 0.0, "end": 10.0},
        {"index": 1, "start": 10.0, "end": 20.0},
        {"index": 2, "start": 20.0, "end": 30.0},
        {"index": 3, "start": 30.0, "end": 40.0},
        {"index": 4, "start": 40.0, "end": 50.0},
    ]

    # Helper function matching the one implemented in run_ingestion.py
    def get_scene_index_value(s: Dict[str, Any]) -> int:
        val = s.get("index")
        if val is None:
            return -1
        try:
            return int(val)
        except (ValueError, TypeError):
            return -1

    # Filter with start=1, end=3
    scene_start_index = 1
    scene_end_index = 3
    filtered = [
        scene for scene in scenes
        if scene_start_index <= get_scene_index_value(scene) <= scene_end_index
    ]
    assert len(filtered) == 3
    assert [s["index"] for s in filtered] == [1, 2, 3]

    # Filter with start=2, end=None
    scene_start_index = 2
    scene_end_index = None
    start_idx = scene_start_index if scene_start_index is not None else 0
    end_idx = scene_end_index if scene_end_index is not None else 10**12
    filtered = [
        scene for scene in scenes
        if start_idx <= get_scene_index_value(scene) <= end_idx
    ]
    assert len(filtered) == 3
    assert [s["index"] for s in filtered] == [2, 3, 4]

    # Filter with start=None, end=2
    scene_start_index = None
    scene_end_index = 2
    start_idx = scene_start_index if scene_start_index is not None else 0
    end_idx = scene_end_index if scene_end_index is not None else 10**12
    filtered = [
        scene for scene in scenes
        if start_idx <= get_scene_index_value(scene) <= end_idx
    ]
    assert len(filtered) == 3
    assert [s["index"] for s in filtered] == [0, 1, 2]
