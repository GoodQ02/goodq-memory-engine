from __future__ import annotations

import hashlib
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from api.routes import scenes
from lib.knowledge_graph import KnowledgeGraph


@pytest.fixture
def graph_client(tmp_path, monkeypatch):
    path = tmp_path / "knowledge_graph.db"
    with KnowledgeGraph(str(path)) as kg:
        video = kg.add_node("video", "source-a")
        scene = kg.add_node("scene", "scene-a", {"video_id": "source-a"})
        other = kg.add_node("scene", "scene-b", {"video_id": "source-b"})
        speaker = kg.add_node("speaker", "scene-a__speaker_00")
        pattern = kg.add_node("speaker_pattern", "pattern-1")
        person = kg.add_node("person", "Alice")
        kg.add_edge(video, scene, "video_contains_scene")
        kg.add_edge(speaker, scene, "speaks_in", properties={"scene_id": "scene-a"})
        kg.add_edge(speaker, pattern, "voice_pattern_match", properties={
            "scene_id": "scene-a", "source": "speaker_voice_signature",
            "selected_segments": [{"start": 12, "end": 14, "secret_path": "private"}],
        })
        kg.add_edge(pattern, person, "identity_evidence", properties={"source": "automatic"})
        kg.add_edge(person, other, "appears_in", properties={"scene_id": "scene-b"})
        kg.add_edge(person, scene, "unknown_future_type", properties={"private_path": "private", "vector": [1]})
    class Loader:
        active = True
        source = "source-a"
        def load_temporal_index(self, video_id):
            return {"segments": [{"scene_id": "scene-a", "start": 10, "end": 20}]} if video_id == "video-a" else None
        def load_scene_manifest(self, video_id):
            return {"video_hash": self.source}
        def is_search_result_active(self, payload):
            return self.active
    loader = Loader()
    monkeypatch.setattr(scenes, "get_data_loader", lambda: loader)
    monkeypatch.setattr(scenes, "load_configs", lambda _: {"epoch_id": "epoch-test", "paths": {"knowledge_graph_db": str(path)}})
    app = FastAPI(); app.include_router(scenes.router)
    return TestClient(app), path, loader


URL = "/api/videos/video-a/scenes/scene-a/relationships"


def test_stored_edges_keep_types_provenance_and_scene_scope_through_route(graph_client):
    client, path, _ = graph_client
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    response = client.get(URL)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok" and data["epoch_id"] == "epoch-test"
    assert {r["type"] for r in data["relationships"]} == {
        "video_contains_scene", "speaks_in", "voice_pattern_match", "identity_evidence", "unknown_future_type"}
    assert all(r["review_status"] == "unreviewed" for r in data["relationships"])
    assert all(r["evidence"]["scene_id"] == "scene-a" for r in data["relationships"])
    assert all(r["evidence"]["source_hash"] == "source-a" for r in data["relationships"])
    assert "scene-b" not in response.text and "private" not in response.text and "vector" not in response.text
    voice = next(r for r in data["relationships"] if r["type"] == "voice_pattern_match")
    assert voice["evidence"]["selected_segments"] == [{"start": 12, "end": 14}]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("mode,expected", [
    ("active", "reviewed_active"), ("revoked", "reviewed_revoked"),
    ("wrong_target", "review_not_matched"), ("wrong_source", "review_not_matched"),
    ("missing", "review_not_matched"), ("corrupt", "review_unavailable"),
    ("duplicate", "review_not_matched"),
])
def test_review_requires_exact_saved_mapping_and_rereads_revocation(graph_client, mode, expected):
    client, path, _ = graph_client
    with KnowledgeGraph(str(path)) as kg:
        kg.conn.execute("UPDATE edges SET properties=? WHERE edge_type='identity_evidence'",
                        (json.dumps({"source": "operator_manual_override", "mapping_id": "map-1"}),))
        kg.conn.commit()
    mapping = {"mapping_id": "map-1", "source_node_type": "speaker_pattern",
               "source_node_name": "pattern-1", "target_person_name": "Alice", "status": "active"}
    ledger = path.parent / "manual_identity_mappings.json"
    ledger.write_text(json.dumps({"mappings": [mapping]}), encoding="utf-8")
    def review():
        return next(r["review_status"] for r in client.get(URL).json()["relationships"] if r["type"] == "identity_evidence")
    assert review() == "reviewed_active"
    if mode == "revoked": mapping["status"] = "revoked"
    if mode == "wrong_target": mapping["target_person_name"] = "Bob"
    if mode == "wrong_source": mapping["source_node_name"] = "pattern-other"
    ledger.write_text(json.dumps({"mappings": [] if mode == "missing" else [mapping] * (2 if mode == "duplicate" else 1)}), encoding="utf-8")
    if mode == "corrupt": ledger.write_text("{broken", encoding="utf-8")
    assert review() == expected


def test_wrong_source_retirement_missing_and_truncation_are_visible(graph_client):
    client, path, loader = graph_client
    limited = client.get(URL + "?limit=1").json()
    assert limited["truncated"] and len(limited["relationships"]) == 1
    assert client.get(URL + "?limit=201").status_code == 422
    assert client.get(URL.replace("scene-a", "missing")).status_code == 404
    assert client.get(URL.replace("video-a", "wrong-video")).status_code == 404
    loader.source = "source-b"
    assert client.get(URL).json()["status"] == "source_mismatch"
    loader.active = False
    assert client.get(URL).status_code == 404
    loader.active = True; loader.source = "source-a"
    path.unlink()
    assert client.get(URL).json()["status"] == "unavailable"


def test_corrupt_graph_fails_visibly_without_leaking_paths(graph_client):
    client, path, _ = graph_client
    path.write_bytes(b"not a database")
    response = client.get(URL)
    assert response.status_code == 503
    assert response.json() == {"detail": "Stored relationship evidence unavailable"}


def test_manifest_bound_slug_is_accepted_but_conflicting_source_is_not(graph_client):
    client, path, _ = graph_client
    with KnowledgeGraph(str(path)) as kg:
        kg.conn.execute("UPDATE nodes SET name='video-a' WHERE node_type='video'")
        kg.conn.commit()
    assert client.get(URL).json()["status"] == "ok"
    with KnowledgeGraph(str(path)) as kg:
        kg.conn.execute("UPDATE nodes SET name='different-source' WHERE node_type='video'")
        kg.conn.commit()
    assert client.get(URL).json()["status"] == "source_mismatch"


def test_missing_or_invalid_voice_times_are_not_fabricated_as_zero(graph_client):
    client, path, _ = graph_client
    with KnowledgeGraph(str(path)) as kg:
        kg.conn.execute("UPDATE edges SET properties=? WHERE edge_type='voice_pattern_match'",
                        (json.dumps({"scene_id": "scene-a", "selected_segments": [
                            {}, {"start": 4}, {"start": None, "end": 5},
                            {"start": True, "end": 4}, {"start": 5, "end": 3},
                            {"start": -1, "end": 3}, {"start": 0, "end": 2},
                        ]}),))
        kg.conn.commit()
    data = client.get(URL).json()
    voice = next(r for r in data["relationships"] if r["type"] == "voice_pattern_match")
    assert voice["evidence"]["selected_segments"] == [{"start": 0, "end": 2}]
