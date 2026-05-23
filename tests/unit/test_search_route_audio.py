from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from typing import List, Optional


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


search_module = _load_route_module("search")


class _FakeSearchEngine:
    def __init__(self):
        self.weight_text = 0.5
        self.weight_visual = 0.4
        self.weight_audio = 0.1
        self.calls: list[tuple[str, int, list[str] | None]] = []
        self.diagnostics = {
            "audio": {
                "status": "unavailable",
                "label": "Audio text-query encoder unavailable",
                "reason": "torch_safetensors_required",
            }
        }

    def search_multimodal(self, query: str, top_k: int, modalities: list[str] | None = None):
        self.calls.append((query, top_k, modalities))
        return [
            {
                "id": "video_001:101",
                "score": 0.77,
                "modality": "audio",
                "payload": {
                    "video_id": "video_001",
                    "scene_id": 101,
                    "timestamp": 12.5,
                    "keywords": ["argument", "crowd"],
                    "objects": ["street"],
                },
            }
        ]

    def last_search_diagnostics(self):
        return self.diagnostics


def test_multimodal_search_route_supports_audio_requests(monkeypatch) -> None:
    engine = _FakeSearchEngine()
    monkeypatch.setattr(search_module, "get_search_engine", lambda: engine)
    search_module.MultimodalSearchRequest.model_rebuild(
        _types_namespace={"List": List, "Optional": Optional, "dict": dict}
    )

    request = search_module.MultimodalSearchRequest(
        query="crowd reaction",
        top_k=3,
        modalities=["audio"],
    )

    response = asyncio.run(search_module.search_multimodal(request))

    assert engine.calls == [("crowd reaction", 3, ["audio"])]
    assert response.modalities_searched == ["audio"]
    assert response.total_results == 1
    assert response.results[0].modality == "audio"
    assert response.results[0].scene_id == 101
    assert response.diagnostics == engine.diagnostics
