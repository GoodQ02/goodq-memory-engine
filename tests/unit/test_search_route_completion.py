"""Completion metadata must follow the timeline resolved for a search result."""
import json

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routes import search
from api.utils.loaders import DataLoader


@pytest.mark.parametrize("complete", [True, False])
@pytest.mark.parametrize("route", ["multimodal", "text", "visual"])
def test_search_completion_uses_resolved_timeline_without_changing_payload_identity(
    tmp_path, monkeypatch, complete, route
):
    processing = tmp_path / "processing"
    timeline = processing / "timeline-directory"
    timeline.mkdir(parents=True)
    (timeline / "temporal_index.json").write_text(json.dumps({
        "title": "Fixture source",
        "phase6_complete": complete,
        "segments": [{"scene_id": "scene-hash", "start": 12.5, "end": 42.25}],
    }), encoding="utf-8")

    class Engine:
        weight_text = .5
        weight_visual = .4
        weight_audio = .1

        def _reset_search_diagnostics(self):
            pass

        def search_multimodal(self, query, **kwargs):
            return [{
                "score": .9, "modality": "visual",
                "payload": {"video_id": "source-content-hash", "scene_id": "scene-hash"},
            }]

        search_visual = search_multimodal
        search_text = search_multimodal

    monkeypatch.setattr(search, "_search_engine", Engine())
    monkeypatch.setattr(search, "_config", {"identity_search": {"enabled": False}})
    monkeypatch.setattr(search, "_data_loader", DataLoader(processing_root=str(processing)))
    client = TestClient(app, client=("127.0.0.1", 50000))
    if route == "multimodal":
        response = client.post("/api/search/multimodal", json={"query": "fixture"})
    else:
        response = client.get(f"/api/search/{route}", params={"q": "fixture"})

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["video_id"] == "source-content-hash"
    assert result["scene_id"] == "scene-hash"
    assert result["timeline_video_id"] == "timeline-directory"
    assert (result["start"], result["end"]) == (12.5, 42.25)
    assert result["phase6_complete"] is complete
