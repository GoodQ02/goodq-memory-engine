from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from typing import List, Optional


def _load_route_module(module_name: str):
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    module_path = repo_root / "api" / "routes" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"tests.{module_name}_route_enrichment", module_path)
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

    def search_multimodal(self, query: str, top_k: int, modalities: list[str] | None = None):
        return [
            {
                "score": 0.51,
                "modality": "text",
                "payload": {
                    "video_id": "hashed-video-id",
                    "scene_id": "hashed-scene-id",
                },
            }
        ]

    def search_text(self, query: str, top_k: int):
        return [
            {
                "score": 0.72,
                "modality": "text",
                "payload": {
                    "video_id": "video_001",
                    "scene_id": 7,
                    "representative_frame": (
                        r"L:\_DATA\GoodQ_Data\processing\video_001\video\frames"
                        r"\scene_0007_frame_01.jpg"
                    ),
                },
                "provenance": {"ref": r"L:\_DATA\GoodQ_Data\epochs\demo\memory.db"},
            }
        ]


class _FakeDataLoader:
    def list_processed_videos(self):
        return ["family_memory_probe"]

    def get_video_metadata(self, video_id: str):
        assert video_id == "family_memory_probe"
        return {
            "video_id": video_id,
            "title": "Family Memory Probe",
            "total_scenes": 1,
        }

    def load_temporal_index(self, video_id: str):
        assert video_id == "family_memory_probe"
        return {
            "segments": [
                {
                    "scene_id": "hashed-scene-id",
                    "start": 12.5,
                    "end": 42.25,
                    "full_transcript": "Grandma laughs while everyone gathers in the kitchen.",
                    "tags": ["kitchen", "family gathering"],
                    "objects": ["table", "birthday cake"],
                    "audio_emotion": "happy",
                    "scene_present_entities": [
                        {"text": "Grandma", "type": "PERSON"},
                        {"text": "Kitchen", "type": "LOCATION"},
                    ],
                    "relationships": [
                        {
                            "type": "co_present",
                            "entities": ["Grandma", "Kitchen"],
                            "source": "scene_kg",
                        }
                    ],
                    "scene_context_llm": {
                        "summary": "A warm family kitchen memory.",
                        "primary_tags": ["family", "kitchen"],
                    },
                    "scene_context_epistemic": {
                        "state": "supported",
                        "dominant_evidence": "mixed",
                    },
                    "scene_context_arbitration": {
                        "resolved_by": "mixed",
                    },
                }
            ]
        }


def test_multimodal_search_enriches_hashed_results_from_timeline(monkeypatch) -> None:
    monkeypatch.setattr(search_module, "get_search_engine", lambda: _FakeSearchEngine())
    monkeypatch.setattr(search_module, "get_data_loader", lambda: _FakeDataLoader())
    search_module.MultimodalSearchRequest.model_rebuild(
        _types_namespace={"List": List, "Optional": Optional, "dict": dict}
    )

    request = search_module.MultimodalSearchRequest(query="kitchen", top_k=1)

    response = asyncio.run(search_module.search_multimodal(request))

    result = response.results[0]
    assert result.video_id == "hashed-video-id"
    assert result.timeline_video_id == "family_memory_probe"
    assert result.display_title == "Family Memory Probe"
    assert result.start == 12.5
    assert result.end == 42.25
    assert result.timestamp == 12.5
    assert result.transcript == "Grandma laughs while everyone gathers in the kitchen."
    assert result.keywords == ["kitchen", "family gathering"]
    assert result.objects == ["table", "birthday cake"]
    assert result.audio_emotion == "happy"
    assert result.context == {
        "start": 12.5,
        "end": 42.25,
        "duration": 29.75,
        "transcript": "Grandma laughs while everyone gathers in the kitchen.",
        "tags": ["kitchen", "family gathering"],
        "objects": ["table", "birthday cake"],
        "audio_emotion": "happy",
        "scene_present_entities": [
            {"text": "Grandma", "type": "PERSON"},
            {"text": "Kitchen", "type": "LOCATION"},
        ],
        "relationships": [
            {"type": "co_present", "entities": ["Grandma", "Kitchen"], "source": "scene_kg"}
        ],
        "kg_evidence": {
            "source": "timeline_scene_entities",
            "entity_count": 2,
            "relationship_count": 1,
            "relationship_state": "observed",
        },
        "scene_context_llm": {
            "summary": "A warm family kitchen memory.",
            "primary_tags": ["family", "kitchen"],
        },
        "scene_context_epistemic": {"state": "supported", "dominant_evidence": "mixed"},
        "scene_context_arbitration": {"resolved_by": "mixed"},
    }
    assert result.scene_present_entities == [
        {"text": "Grandma", "type": "PERSON"},
        {"text": "Kitchen", "type": "LOCATION"},
    ]
    assert result.kg_relationships == [
        {"type": "co_present", "entities": ["Grandma", "Kitchen"], "source": "scene_kg"}
    ]
    assert result.kg_evidence == {
        "source": "timeline_scene_entities",
        "entity_count": 2,
        "relationship_count": 1,
        "relationship_state": "observed",
    }
    assert result.scene_context_epistemic == {"state": "supported", "dominant_evidence": "mixed"}
    assert result.scene_context_arbitration == {"resolved_by": "mixed"}
    assert result.confidence["overall"] == 0.51
    assert result.confidence["source"] == "timeline_segment"
    assert result.confidence["evidence_state"] == "supported"
    assert result.confidence["dominant_evidence"] == "mixed"
    assert result.provenance == {
        "search_video_id": "hashed-video-id",
        "timeline_video_id": "family_memory_probe",
        "scene_id": "hashed-scene-id",
        "enrichment": "timeline_segment",
        "kg_source": "timeline_scene_entities",
        "entity_count": 2,
        "relationship_count": 1,
    }


def test_text_search_redacts_provenance_paths_and_projects_frame_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(search_module, "get_search_engine", lambda: _FakeSearchEngine())
    monkeypatch.setattr(search_module, "get_data_loader", lambda: _FakeDataLoader())

    response = asyncio.run(search_module.search_text(q="kitchen", top_k=1))

    result = response.results[0]
    payload = result.model_dump() if hasattr(result, "model_dump") else result.dict()
    serialized = json.dumps(payload)
    assert "L:" not in serialized
    assert "_DATA" not in serialized
    assert result.representative_frame == "/api/media/video/video_001/frame/scene_0007_frame_01.jpg"
    assert getattr(result, "representative_frame_available", None) is True
    assert getattr(result, "representative_frame_endpoint", None) == (
        "/api/media/video/video_001/frame/scene_0007_frame_01.jpg"
    )
    assert getattr(result, "representative_frame_path_redacted", None) is True
    assert result.provenance["ref"] == "<local-only>"
    assert result.provenance["raw_paths"] == "redacted"
