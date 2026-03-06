from __future__ import annotations

import sqlite3
from pathlib import Path

from lib.kg_realtime_integration import update_kg_for_scene


def test_update_kg_for_scene_persists_scene_location_character_edges(tmp_path: Path):
    kg_db = tmp_path / "kg_test.db"
    cfg = {"paths": {"knowledge_graph_db": str(kg_db)}}

    scene_data = {
        "index": 7,
        "start": 10.0,
        "end": 24.0,
        "caption": "Jerry and George talk at Monk's Cafe",
        "faces": [
            {"identity": "jerry", "confidence": 0.94},
            {"identity": "george", "confidence": 0.92},
        ],
        "entities": [
            {"name": "Jerry", "type": "PERSON"},
            {"name": "George", "type": "PERSON"},
            {"name": "Monk's Cafe", "type": "LOCATION"},
        ],
        "locations": ["Monk's Cafe"],
        "speaker_transcript": [
            {"speaker": "SPEAKER_00", "start": 10.1, "end": 12.2, "text": "So we are here again."},
            {"speaker": "SPEAKER_01", "start": 12.3, "end": 14.5, "text": "Yes, at Monk's."},
        ],
    }

    result = update_kg_for_scene(
        scene_data=scene_data,
        scene_id="scene_test_0007",
        video_id="video_test",
        video_path="samples/ingestion/Sein_Experiment/01x01 - Good News, Bad News.mp4",
        cfg=cfg,
    )

    assert result["status"] == "success"
    assert result["ingest_counts"]["edges_added"] > 0

    conn = sqlite3.connect(str(kg_db))
    cur = conn.cursor()

    edge_counts = {
        row[0]: row[1]
        for row in cur.execute(
            "SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type"
        ).fetchall()
    }
    assert edge_counts.get("appears_in", 0) >= 2
    assert edge_counts.get("located_in", 0) >= 1
    assert edge_counts.get("interacts_with", 0) >= 1

    scene_node = cur.execute(
        "SELECT id FROM nodes WHERE node_type = ? AND name = ?",
        ("scene", "scene_test_0007"),
    ).fetchone()
    assert scene_node is not None

    location_node = cur.execute(
        "SELECT id FROM nodes WHERE node_type = ? AND name = ?",
        ("location", "Monk's Cafe"),
    ).fetchone()
    assert location_node is not None

    conn.close()
