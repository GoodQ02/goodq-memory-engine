import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.mark.parametrize("labels,expected,missing", [
    (["POSITIVE", "NEGATIVE", "NEUTRAL", None], {"POSITIVE": 1, "NEGATIVE": 1, "NEUTRAL": 1}, 1),
    ([None, "", "unknown"], {"POSITIVE": 0, "NEGATIVE": 0, "NEUTRAL": 0}, 3),
    (["neutral"], {"POSITIVE": 0, "NEGATIVE": 0, "NEUTRAL": 1}, 0),
    ([], {"POSITIVE": 0, "NEGATIVE": 0, "NEUTRAL": 0}, 0),
])
def test_summary_http_preserves_sentiment_availability(tmp_path, monkeypatch, labels, expected, missing):
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    from api.routes import summary
    from api.utils.loaders import DataLoader
    from api.route_effects import ROUTE_EFFECTS, install_route_effect_authority
    from lib.knowledge_graph import KnowledgeGraph

    graph = tmp_path / "knowledge_graph.db"
    records = [{"scene_id": f"scene-{i}", "start": i * 10, "end": (i + 1) * 10,
                "sentiment_label": label} for i, label in enumerate(labels)]
    # A separate scene verifies that entity coverage stays scoped to membership.
    unrelated = {"scene_id": "unrelated", "start": 100, "end": 110, "sentiment_label": "POSITIVE"}
    with KnowledgeGraph(str(graph)) as kg:
        person = kg.add_node("person", "Test Person")
        for row in records:
            media = kg.add_media_node("video_scene", "source.mp4", scene_id=row["scene_id"])
            kg.link_node_to_media(person, media)
    directory = tmp_path / "processing/source"
    directory.mkdir(parents=True)
    (directory / "temporal_index.json").write_text(json.dumps({"segments": records + [unrelated]}), encoding="utf-8")
    monkeypatch.setattr(summary, "_get_kg_db_path", lambda: graph)
    monkeypatch.setattr(summary, "_data_loader", DataLoader(processing_root=str(directory.parent)))
    app = FastAPI()
    paths = {"/api/summary/dashboard", "/api/summary/entity/{entity_id:path}"}
    app.router.routes.extend(r for r in summary.router.routes if r.path in paths)
    install_route_effect_authority(app, registry={(m, r.path): ROUTE_EFFECTS[(m, r.path)] for r in summary.router.routes if r.path in paths for m in r.methods})
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        dashboard = client.get("/api/summary/dashboard")
        profile = client.get("/api/summary/entity/person:Test%20Person")
        assert dashboard.status_code == profile.status_code == 200, (dashboard.text, profile.text)
        for response, extra in [(dashboard, 1), (profile, 0)]:
            body = response.json()
            assert body["sentiment_distribution"] == {**expected, "POSITIVE": expected["POSITIVE"] + extra}
            assert body["sentiment_coverage"] == {
                "total": len(labels) + extra, "classified": len(labels) - missing + extra, "unavailable": missing,
            }
        assert profile.json()["scene_count"] == len(labels)
