import asyncio
import json
import sqlite3

import pytest

from lib.knowledge_graph import KnowledgeGraph
from lib.identity_resolver import IdentityResolver
from lib import identity_resolver
from api.routes import search
from tests.unit.test_identity_search_ranking import _NoopLoader


def reviewed(tmp_path):
    db = tmp_path / "knowledge_graph.db"
    with KnowledgeGraph(str(db)) as kg:
        person = kg.add_node("person", "Kathy")
        pattern = kg.add_node("speaker_pattern", "voice-a")
        speaker = kg.add_node("speaker", "scene-a__speaker_01")
        scene = kg.add_node("scene", "scene-a")
        kg.add_edge(pattern, person, "identity_evidence", properties={"source": "operator_manual_override", "mapping_id": "map-a"})
        kg.add_edge(speaker, pattern, "voice_pattern_match")
        kg.add_edge(speaker, scene, "speaks_in")
    mapping = tmp_path / "manual_identity_mappings.json"
    mapping.write_text(json.dumps({"mappings": [{"mapping_id": "map-a", "status": "active", "source_node_type": "speaker_pattern", "source_node_name": "voice-a", "target_person_name": "Kathy"}]}))
    resolver = IdentityResolver(str(tmp_path / "missing.yaml"), str(db), enabled=True)
    return resolver, db, mapping


def test_reviewed_voice_without_roster_is_typed_and_revocation_is_immediate(tmp_path):
    resolver, _, path = reviewed(tmp_path)
    evidence = resolver.get_identity_scene_evidence("Kathy")
    assert evidence["scene-a"][0]["evidence_types"] == ["voice"]
    assert evidence["scene-a"][0]["strength"] == "voice"
    assert resolver.get_identity_scene_evidence("Jose") == {}
    data = json.loads(path.read_text());data["mappings"][0]["status"] = "revoked";path.write_text(json.dumps(data))
    assert resolver.get_identity_scene_evidence("Kathy") == {}


@pytest.mark.parametrize("bad", ["candidate", "wrong_mapping", "missing_turn", "different_person"])
def test_voice_requires_exact_review_and_scene_speaker_chain(tmp_path, bad):
    resolver, db, _ = reviewed(tmp_path)
    with sqlite3.connect(db) as conn:
        if bad == "candidate": conn.execute("UPDATE edges SET edge_type='identity_candidate' WHERE edge_type='identity_evidence'")
        elif bad == "wrong_mapping": conn.execute("UPDATE edges SET properties='{}' WHERE edge_type='identity_evidence'")
        elif bad == "missing_turn": conn.execute("DELETE FROM edges WHERE edge_type='speaks_in'")
        else: conn.execute("UPDATE nodes SET name='Jose' WHERE node_type='person'")
    assert resolver.get_identity_scene_evidence("Kathy") == {}


def test_people_route_never_constructs_an_encoder_and_preserves_voice(tmp_path, monkeypatch):
    resolver, db, _ = reviewed(tmp_path)
    monkeypatch.setattr(identity_resolver, "_resolver", resolver)
    monkeypatch.setattr(search, "_config", {"identity_search": {"enabled": True}})
    monkeypatch.setattr(search, "get_data_loader", lambda: _NoopLoader())
    def forbidden(): raise AssertionError("People mode must not instantiate the search/model engine")
    monkeypatch.setattr(search, "get_search_engine", forbidden)
    response = asyncio.run(search.search_multimodal(search.MultimodalSearchRequest(query="Kathy", modalities=["identity"])))
    assert response.total_results == 1
    assert response.results[0].identity_match == "voice"
    assert response.results[0].vector_score is None
    assert response.results[0].identity_only
    assert response.diagnostics["identity"]["inference_performed"] is False


def test_voice_augments_multimodal_without_becoming_appearance(tmp_path, monkeypatch):
    resolver, _, _ = reviewed(tmp_path)
    monkeypatch.setattr(identity_resolver, "_resolver", resolver)
    monkeypatch.setattr(search, "_config", {"identity_search": {"enabled": True}})
    monkeypatch.setattr(search, "get_data_loader", lambda: _NoopLoader())
    class Engine:
        weight_text, weight_visual, weight_audio = .5, .4, .1
        def search_multimodal(self, **kwargs): return [{"score": .6, "modality": "text", "payload": {"scene_id": "other"}}]
    monkeypatch.setattr(search, "get_search_engine", lambda: Engine())
    response = asyncio.run(search.search_multimodal(search.MultimodalSearchRequest(query="Kathy", top_k=2)))
    voice = next(r for r in response.results if r.scene_id == "scene-a")
    assert voice.identity_match == "voice" and voice.identity_evidence[0]["evidence_types"] == ["voice"]
    assert any(r.scene_id == "other" for r in response.results)


def test_roster_person_keeps_all_three_evidence_channels(tmp_path):
    resolver, db, _ = reviewed(tmp_path)
    roster = tmp_path / "family_roster.yaml"
    roster.write_text("identities:\n- id: person-kathy\n  display_name: Kathy\n  aliases: [Mom]\n")
    resolver._roster_path = roster
    with KnowledgeGraph(str(db)) as kg:
        person = kg.add_node("Person", "person-kathy")
        scene = kg.add_node("scene", "scene-a")
        kg.add_edge(person, scene, "person_appears_in_scene")
        kg.add_edge(person, scene, "person_mentioned_in_scene")
    item = resolver.get_identity_scene_evidence("Mom")["scene-a"][0]
    assert item["person_id"] == "person-kathy"
    assert item["evidence_types"] == ["appearance", "voice", "mention"]
