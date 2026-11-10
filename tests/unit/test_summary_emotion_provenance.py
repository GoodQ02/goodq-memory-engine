import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.mark.parametrize("empty", [False, True])
def test_summary_emotions_keep_channel_basis_and_unique_scene_counts(tmp_path, monkeypatch, empty):
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    from api.routes import summary
    from api.utils.loaders import DataLoader
    from api.route_effects import ROUTE_EFFECTS, install_route_effect_authority
    from lib.knowledge_graph import KnowledgeGraph

    graph = tmp_path / "knowledge_graph.db"
    records = [] if empty else [
        {"scene_id": "both", "audio_emotion": "joy", "text_emotion_ranking": [{"label": "joy", "score": .9}]},
        {"scene_id": "candidate", "audio_emotion": None, "audio_emotion_ranking": [{"label": "joy", "score": .2}],
         "text_emotion_ranking": [{"label": "anger", "score": .8}, {"label": "joy", "score": .1}]},
        {"scene_id": "missing", "audio_emotion": None, "text_emotion_ranking": []},
    ]
    with KnowledgeGraph(str(graph)) as kg:
        person = kg.add_node("person", "Fixture")
        for row in records:
            media = kg.add_media_node("video_scene", "source.mp4", scene_id=row["scene_id"])
            kg.link_node_to_media(person, media)
    # An unrelated scene stays outside the entity profile; a repeated record must
    # not turn one scene's channel evidence into two scenes.
    all_records = records + ([records[0], {"scene_id": "outside", "audio_emotion": "happy"}] if records else [])
    directory = tmp_path / "processing/source"
    directory.mkdir(parents=True)
    (directory / "temporal_index.json").write_text(json.dumps({"segments": all_records}), encoding="utf-8")
    monkeypatch.setattr(summary, "_get_kg_db_path", lambda: graph)
    monkeypatch.setattr(summary, "_data_loader", DataLoader(processing_root=str(directory.parent)))
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    paths = {"/api/summary/dashboard", "/api/summary/entity/{entity_id:path}"}
    app.router.routes.extend(r for r in summary.router.routes if r.path in paths)
    install_route_effect_authority(app, registry={(m, r.path): ROUTE_EFFECTS[(m, r.path)] for r in app.routes for m in r.methods})
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        for endpoint, outside in [("dashboard", True), ("entity/person:Fixture", False)]:
            response = client.get("/api/summary/" + endpoint)
            assert response.status_code == 200
            rows = response.json()["top_emotions"]
            expected = {} if empty else {("audio", "joy"): 1, ("text", "joy"): 1, ("text", "anger"): 1}
            if not empty and outside:
                expected[("audio", "happy")] = 1
            assert {(r["channel"], r["emotion"]): r["count"] for r in rows} == expected
            assert all(r["count_unit"] == "scenes" for r in rows)
            assert all(r["basis"] == ("stored_label" if r["channel"] == "audio" else "top_ranked") for r in rows)
