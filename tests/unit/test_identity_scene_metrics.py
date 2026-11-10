"""Scene counts follow persisted membership, not graph write/signature counts."""
from fastapi.testclient import TestClient

from api.main import app
from api.routes import summary, system
from lib.knowledge_graph import KnowledgeGraph


def test_http_scene_counts_deduplicate_identity_paths_and_turns(tmp_path, monkeypatch):
    graph = tmp_path / "knowledge_graph.db"
    with KnowledgeGraph(str(graph)) as kg:
        person = kg.add_node("person", "Kathy")
        place = kg.add_node("location", "Kitchen")
        pattern = kg.add_node("speaker_pattern", "pattern", properties={"signature_count": 99})
        speaker = kg.add_node("speaker", "scene__speaker")
        kg.add_edge(pattern, person, "identity_evidence")
        turn = {"speaker": "Speaker_01", "start": 2.0, "end": 4.0}
        kg.add_edge(speaker, pattern, "voice_pattern_match", properties={
            "scene_id": "scene", "selected_segments": [turn, turn, {**turn, "start": 5.0, "end": 6.0}]})
        media = kg.add_media_node("video_scene", "source.wav", scene_id="scene",
                                  timestamp_start=0.0, timestamp_end=75.509)
        for node in [person, pattern, speaker, place]:
            kg.link_node_to_media(node, media)
        kg.conn.execute("UPDATE nodes SET occurrence_count=77, first_seen=0, last_seen=0")
        kg.conn.commit()

    class Loader:
        def list_processed_videos(self):
            return ["source"]

        def load_temporal_index(self, _video):
            scene = {"scene_id": "scene", "start": 0.0, "end": 75.509}
            return {"segments": [scene, dict(scene)]}

    monkeypatch.setattr(summary, "_get_kg_db_path", lambda: graph)
    monkeypatch.setattr(summary, "_data_loader", Loader())
    monkeypatch.setattr(system, "_get_kg_db_path", lambda: graph)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        dashboard = client.get("/api/summary/dashboard")
        assert dashboard.status_code == 200, dashboard.text
        data = dashboard.json()
        assert data["people"][0]["scene_count"] == data["places"][0]["scene_count"] == 1
        assert data["people"][0]["occurrence_count"] == 154  # Historical field unchanged.
        profile = client.get("/api/summary/entity/person:Kathy").json()
        assert profile["scene_count"] == len(profile["scenes"]) == 1
        assert profile["scenes"][0]["end"] == 75.509
        assert profile["co_occurrences"][0]["co_occurrence_count"] == 1

        # Revoked projection: the anonymous pattern becomes visible again.
        with KnowledgeGraph(str(graph)) as kg:
            kg.conn.execute("DELETE FROM edges WHERE edge_type='identity_evidence'")
            kg.conn.commit()
        patterns = client.get("/api/system/identity/unstitched").json()
        assert patterns[0]["scene_count"] == 1
        assert patterns[0]["segment_count"] == 2


def test_scene_membership_excludes_retired_media_and_empty_patterns(tmp_path):
    from lib.summary_aggregator import entity_scene_ids
    graph = tmp_path / "knowledge_graph.db"
    with KnowledgeGraph(str(graph)) as kg:
        person = kg.add_node("person", "Kathy")
        pattern = kg.add_node("speaker_pattern", "pattern")
        kg.add_edge(pattern, person, "identity_evidence")
        media = kg.add_media_node("video_scene", "source.wav", scene_id="retired")
        kg.link_node_to_media(pattern, media)
        assert entity_scene_ids(kg.conn, [person]) == {"retired"}
        assert entity_scene_ids(kg.conn, [person], {media}) == set()
        assert entity_scene_ids(kg.conn, []) == set()
