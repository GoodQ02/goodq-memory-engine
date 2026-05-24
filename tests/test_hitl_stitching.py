from __future__ import annotations

import json
from pathlib import Path
import pytest
from lib.knowledge_graph import KnowledgeGraph
from lib.identity_ledger import (
    load_manual_mappings,
    save_manual_mappings,
    apply_manual_mappings,
)
from api.routes import system as system_module


def create_test_db(db_path: Path):
    """Set up a temporary knowledge graph with raw unstitched entities."""
    with KnowledgeGraph(str(db_path)) as kg:
        # 1. Add speaker_pattern node
        pattern_id = kg.add_node(
            node_type="speaker_pattern",
            name="voice_pattern_test_speaker_1",
            properties={
                "total_voiced_seconds": 15.0,
                "signature_count": 3
            }
        )
        
        # 2. Add structural speaker node
        speaker_id = kg.add_node(
            node_type="speaker",
            name="scene_01__speaker_01",
            properties={"speaker_label": "Speaker_01"}
        )
        
        # 3. Add voice_pattern_match edge
        kg.add_edge(
            source_id=speaker_id,
            target_id=pattern_id,
            edge_type="voice_pattern_match",
            weight=0.95,
            properties={}
        )
        
        # 4. Add video scene media nodes
        media_id_1 = kg.add_media_node(
            media_type="video_scene",
            media_path="video_test.mp4",
            scene_id="video_test::scene_01",
            timestamp_start=0.0,
            timestamp_end=10.0,
            properties={"video_id": "video_test"}
        )
        media_id_2 = kg.add_media_node(
            media_type="video_scene",
            media_path="video_test.mp4",
            scene_id="video_test::scene_02",
            timestamp_start=10.0,
            timestamp_end=20.0,
            properties={"video_id": "video_test"}
        )
        
        # 5. Link nodes to media
        kg.link_node_to_media(
            node_id=speaker_id,
            media_id=media_id_1,
            confidence=1.0,
            context={"text": "This is a sample transcript excerpt."}
        )
        kg.link_node_to_media(
            node_id=pattern_id,
            media_id=media_id_1,
            confidence=0.95,
            context={}
        )
        kg.link_node_to_media(
            node_id=pattern_id,
            media_id=media_id_2,
            confidence=0.95,
            context={}
        )


def test_manual_mappings_load_save(tmp_path: Path) -> None:
    db_path = tmp_path / "knowledge_graph.db"
    
    # 1. Test load on missing file returns default template
    data = load_manual_mappings(db_path)
    assert data["version"] == 1
    assert data["mappings"] == []
    
    # 2. Test save correctly writes JSON to file next to db
    mappings_data = {
        "version": 1,
        "mappings": [
            {
                "mapping_id": "map_01",
                "source_node_type": "speaker_pattern",
                "source_node_name": "voice_pattern_test_speaker_1",
                "target_person_name": "Alice",
                "status": "active",
                "history": [
                    {
                        "status": "active",
                        "timestamp_utc": "2026-05-24T17:00:00Z",
                        "operator_note": "Initial mapping"
                    }
                ]
            }
        ]
    }
    
    save_manual_mappings(db_path, mappings_data)
    loaded = load_manual_mappings(db_path)
    assert loaded["version"] == 1
    assert len(loaded["mappings"]) == 1
    assert loaded["mappings"][0]["target_person_name"] == "Alice"


def test_apply_manual_mappings(tmp_path: Path) -> None:
    db_path = tmp_path / "knowledge_graph.db"
    create_test_db(db_path)
    
    # Write manual mapping
    mappings_data = {
        "version": 1,
        "mappings": [
            {
                "mapping_id": "map_01",
                "source_node_type": "speaker_pattern",
                "source_node_name": "voice_pattern_test_speaker_1",
                "target_person_name": "Alice",
                "status": "active",
                "history": [{"status": "active", "timestamp_utc": "2026-05-24T17:00:00Z"}]
            }
        ]
    }
    save_manual_mappings(db_path, mappings_data)
    
    # Verify graph before applying mappings (no Alice person or identity edges pointing to Alice)
    with KnowledgeGraph(str(db_path)) as kg:
        cur = kg.conn.cursor()
        person_row = cur.execute("SELECT COUNT(*) FROM nodes WHERE node_type = 'person' AND name = 'Alice'").fetchone()
        assert person_row[0] == 0
        
        # Apply manual mappings
        count = apply_manual_mappings(kg, db_path)
        assert count == 1
        
        # Verify graph after applying mappings
        person_row = cur.execute("SELECT COUNT(*) FROM nodes WHERE node_type = 'person' AND name = 'Alice'").fetchone()
        assert person_row[0] == 1
        
        edge_row = cur.execute(
            """
            SELECT e.weight, e.properties
            FROM edges e
            JOIN nodes s ON e.source_id = s.id
            JOIN nodes t ON e.target_id = t.id
            WHERE s.node_type = 'speaker_pattern' AND t.name = 'Alice' AND e.edge_type = 'identity_evidence'
            """
        ).fetchone()
        assert edge_row is not None
        assert edge_row["weight"] == 1.0
        props = json.loads(edge_row["properties"])
        assert props["source"] == "operator_manual_override"
        assert props["mapping_id"] == "map_01"


def test_get_unstitched_patterns(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "knowledge_graph.db"
    create_test_db(db_path)
    
    monkeypatch.setattr(system_module, "_get_kg_db_path", lambda: db_path)
    
    # Call endpoint handler
    import asyncio
    results = asyncio.run(system_module.get_unstitched_patterns())
    
    assert len(results) == 1
    pattern = results[0]
    assert pattern.node_name == "voice_pattern_test_speaker_1"
    assert pattern.occurrence_count == 1
    assert pattern.voiced_seconds == 15.0
    assert pattern.segment_count == 3
    assert pattern.sample_transcript == "This is a sample transcript excerpt."


def test_preview_stitch_route(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "knowledge_graph.db"
    create_test_db(db_path)
    
    monkeypatch.setattr(system_module, "_get_kg_db_path", lambda: db_path)
    
    # Create request
    req = system_module.StitchPreviewRequest(
        source_node_name="voice_pattern_test_speaker_1",
        target_person_name="Bob"
    )
    
    # Call preview route
    import asyncio
    preview = asyncio.run(system_module.preview_stitch(req))
    
    assert preview.success is True
    assert preview.source_node_name == "voice_pattern_test_speaker_1"
    assert preview.target_person_name == "Bob"
    assert preview.scenes_affected == 2
    assert preview.episodes_affected == 1
    assert len(preview.conflicts) == 0


def test_execute_stitch_route(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "knowledge_graph.db"
    create_test_db(db_path)
    
    monkeypatch.setattr(system_module, "_get_kg_db_path", lambda: db_path)
    
    # Verify execution requires confirm=True
    req_no_confirm = system_module.StitchRequest(
        source_node_name="voice_pattern_test_speaker_1",
        target_person_name="Bob",
        confirm=False
    )
    import asyncio
    from fastapi import HTTPException
    
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(system_module.execute_stitch(req_no_confirm))
    assert exc_info.value.status_code == 400
    
    # Execute stitch with confirm=True
    req_confirm = system_module.StitchRequest(
        source_node_name="voice_pattern_test_speaker_1",
        target_person_name="Bob",
        confirm=True,
        operator_note="Mapping Bob to test speaker pattern"
    )
    
    response = asyncio.run(system_module.execute_stitch(req_confirm))
    assert response.success is True
    assert "Successfully stitched" in response.message
    
    # Verify JSON mapping file was created
    mappings_file = db_path.parent / "manual_identity_mappings.json"
    assert mappings_file.is_file()
    
    with mappings_file.open("r", encoding="utf-8") as f:
        saved_data = json.load(f)
        assert len(saved_data["mappings"]) == 1
        mapping = saved_data["mappings"][0]
        assert mapping["source_node_name"] == "voice_pattern_test_speaker_1"
        assert mapping["target_person_name"] == "Bob"
        assert mapping["status"] == "active"
        assert mapping["history"][-1]["operator_note"] == "Mapping Bob to test speaker pattern"
        
    # Verify edge was created in graph database
    with KnowledgeGraph(str(db_path)) as kg:
        cur = kg.conn.cursor()
        person = cur.execute("SELECT id FROM nodes WHERE node_type = 'person' AND name = 'Bob'").fetchone()
        assert person is not None
        edge = cur.execute(
            "SELECT weight FROM edges WHERE source_id = (SELECT id FROM nodes WHERE name = ?) AND target_id = ?",
            ("voice_pattern_test_speaker_1", int(person["id"]))
        ).fetchone()
        assert edge is not None
        assert edge["weight"] == 1.0
