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
    assert edge_counts.get("identity_evidence", 0) >= 2

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

    synthetic_speaker_people = cur.execute(
        "SELECT COUNT(*) FROM nodes WHERE node_type = ? AND lower(name) LIKE 'speaker_%'",
        ("person",),
    ).fetchone()
    assert synthetic_speaker_people is not None
    assert synthetic_speaker_people[0] == 0

    face_nodes = cur.execute(
        "SELECT COUNT(*) FROM nodes WHERE node_type = ?",
        ("face",),
    ).fetchone()
    assert face_nodes is not None
    assert face_nodes[0] == 2

    conn.close()


def test_update_kg_for_scene_links_named_speaker_to_person_identity(tmp_path: Path):
    kg_db = tmp_path / "kg_identity.db"
    cfg = {"paths": {"knowledge_graph_db": str(kg_db)}}

    scene_data = {
        "index": 3,
        "start": 0.0,
        "end": 8.0,
        "caption": "Jerry speaks on the phone",
        "entities": [{"name": "Jerry", "type": "PERSON"}],
        "speaker_transcript": [
            {"speaker": "Jerry", "start": 0.0, "end": 3.0, "text": "Hello there."},
        ],
    }

    result = update_kg_for_scene(
        scene_data=scene_data,
        scene_id="scene_identity_0003",
        video_id="video_test",
        video_path="samples/ingestion/Sein_Experiment/01x01 - Good News, Bad News.mp4",
        cfg=cfg,
    )

    assert result["status"] == "success"

    conn = sqlite3.connect(str(kg_db))
    cur = conn.cursor()

    speaker_node = cur.execute(
        "SELECT id FROM nodes WHERE node_type = ? AND name = ?",
        ("speaker", "Jerry"),
    ).fetchone()
    person_node = cur.execute(
        "SELECT id FROM nodes WHERE node_type = ? AND name = ?",
        ("person", "Jerry"),
    ).fetchone()
    assert speaker_node is not None
    assert person_node is not None

    identity_edge = cur.execute(
        "SELECT COUNT(*) FROM edges WHERE source_id = ? AND target_id = ? AND edge_type = ?",
        (speaker_node[0], person_node[0], "identity_evidence"),
    ).fetchone()
    assert identity_edge is not None
    assert identity_edge[0] == 1

    conn.close()


def test_update_kg_for_scene_scopes_placeholder_speakers_per_scene(tmp_path: Path):
    kg_db = tmp_path / "kg_scoped_speakers.db"
    cfg = {"paths": {"knowledge_graph_db": str(kg_db)}}

    for scene_id in ("scene_scope_0001", "scene_scope_0002"):
        result = update_kg_for_scene(
            scene_data={
                "index": 1,
                "start": 0.0,
                "end": 5.0,
                "speaker_transcript": [
                    {"speaker": "SPEAKER_00", "start": 0.0, "end": 2.0, "text": "Hello."},
                ],
            },
            scene_id=scene_id,
            video_id="video_test",
            video_path="samples/ingestion/Sein_Experiment/01x01 - Good News, Bad News.mp4",
            cfg=cfg,
        )
        assert result["status"] == "success"

    conn = sqlite3.connect(str(kg_db))
    cur = conn.cursor()

    speaker_nodes = cur.execute(
        "SELECT name FROM nodes WHERE node_type = ? ORDER BY name",
        ("speaker",),
    ).fetchall()
    assert [row[0] for row in speaker_nodes] == [
        "scene_scope_0001__speaker_00",
        "scene_scope_0002__speaker_00",
    ]

    placeholder_people = cur.execute(
        "SELECT COUNT(*) FROM nodes WHERE node_type = ? AND lower(name) LIKE 'speaker_%'",
        ("person",),
    ).fetchone()
    assert placeholder_people is not None
    assert placeholder_people[0] == 0

    conn.close()


def test_update_kg_for_scene_emits_identity_candidate_for_single_person_single_speaker(tmp_path: Path):
    kg_db = tmp_path / "kg_identity_candidate_speaker.db"
    cfg = {"paths": {"knowledge_graph_db": str(kg_db)}}

    result = update_kg_for_scene(
        scene_data={
            "index": 22,
            "start": 0.0,
            "end": 4.0,
            "entities": [{"name": "Bill", "type": "PERSON"}],
            "speaker_transcript": [
                {"speaker": "SPEAKER_00", "start": 0.0, "end": 4.0, "text": "Bill is here."},
            ],
        },
        scene_id="scene_identity_candidate_0022",
        video_id="video_test",
        video_path="samples/ingestion/Sein_Experiment/01x01 - Good News, Bad News.mp4",
        cfg=cfg,
    )

    assert result["status"] == "success"

    conn = sqlite3.connect(str(kg_db))
    cur = conn.cursor()

    speaker_node = cur.execute(
        "SELECT id FROM nodes WHERE node_type = ? AND name = ?",
        ("speaker", "scene_identity_candidate_0022__speaker_00"),
    ).fetchone()
    person_node = cur.execute(
        "SELECT id FROM nodes WHERE node_type = ? AND name = ?",
        ("person", "Bill"),
    ).fetchone()
    assert speaker_node is not None
    assert person_node is not None

    candidate_edge = cur.execute(
        "SELECT COUNT(*) FROM edges WHERE source_id = ? AND target_id = ? AND edge_type = ?",
        (speaker_node[0], person_node[0], "identity_candidate"),
    ).fetchone()
    assert candidate_edge is not None
    assert candidate_edge[0] == 1

    conn.close()


def test_update_kg_for_scene_skips_identity_candidate_when_multiple_people_present(tmp_path: Path):
    kg_db = tmp_path / "kg_identity_candidate_conflict.db"
    cfg = {"paths": {"knowledge_graph_db": str(kg_db)}}

    result = update_kg_for_scene(
        scene_data={
            "index": 23,
            "start": 0.0,
            "end": 6.0,
            "entities": [
                {"name": "Jerry", "type": "PERSON"},
                {"name": "George", "type": "PERSON"},
            ],
            "speaker_transcript": [
                {"speaker": "SPEAKER_00", "start": 0.0, "end": 6.0, "text": "We are both here."},
            ],
        },
        scene_id="scene_identity_candidate_conflict",
        video_id="video_test",
        video_path="samples/ingestion/Sein_Experiment/01x01 - Good News, Bad News.mp4",
        cfg=cfg,
    )

    assert result["status"] == "success"

    conn = sqlite3.connect(str(kg_db))
    cur = conn.cursor()
    candidate_edges = cur.execute(
        "SELECT COUNT(*) FROM edges WHERE edge_type = ?",
        ("identity_candidate",),
    ).fetchone()
    assert candidate_edges is not None
    assert candidate_edges[0] == 0
    conn.close()


def test_update_kg_for_scene_skips_weak_identity_candidate_for_brittle_person_labels(tmp_path: Path):
    kg_db = tmp_path / "kg_identity_candidate_brittle_names.db"
    cfg = {"paths": {"knowledge_graph_db": str(kg_db)}}

    first = update_kg_for_scene(
        scene_data={
            "index": 24,
            "start": 0.0,
            "end": 5.0,
            "entities": [{"name": "God", "type": "PERSON"}],
            "faces": [{"confidence": 0.91}],
        },
        scene_id="scene_identity_candidate_brittle_face",
        video_id="video_test",
        video_path="samples/ingestion/Sein_Experiment/01x01 - Good News, Bad News.mp4",
        cfg=cfg,
    )
    assert first["status"] == "success"

    second = update_kg_for_scene(
        scene_data={
            "index": 25,
            "start": 0.0,
            "end": 5.0,
            "entities": [{"name": "F", "type": "PERSON"}],
            "speaker_transcript": [
                {"speaker": "SPEAKER_00", "start": 0.0, "end": 5.0, "text": "Hi there."},
            ],
        },
        scene_id="scene_identity_candidate_brittle_speaker",
        video_id="video_test",
        video_path="samples/ingestion/Sein_Experiment/01x01 - Good News, Bad News.mp4",
        cfg=cfg,
    )
    assert second["status"] == "success"

    conn = sqlite3.connect(str(kg_db))
    cur = conn.cursor()
    candidate_edges = cur.execute(
        """
        SELECT COUNT(*)
        FROM edges e
        JOIN nodes t ON t.id = e.target_id
        WHERE e.edge_type = ?
          AND t.node_type = ?
          AND t.name IN (?, ?)
        """,
        ("identity_candidate", "person", "God", "F"),
    ).fetchone()
    assert candidate_edges is not None
    assert candidate_edges[0] == 0
    conn.close()


def test_update_kg_for_scene_accumulates_identity_support_after_repeated_agreement(tmp_path: Path):
    kg_db = tmp_path / "kg_identity_support_accumulator.db"
    cfg = {"paths": {"knowledge_graph_db": str(kg_db)}}

    for scene_id in ("scene_identity_support_0001", "scene_identity_support_0002"):
        result = update_kg_for_scene(
            scene_data={
                "index": 30,
                "start": 0.0,
                "end": 4.0,
                "entities": [{"name": "Bill", "type": "PERSON"}],
                "speaker_transcript": [
                    {"speaker": "SPEAKER_00", "start": 0.0, "end": 4.0, "text": "Bill is here."},
                ],
            },
            scene_id=scene_id,
            video_id="video_test",
            video_path="samples/ingestion/Sein_Experiment/01x01 - Good News, Bad News.mp4",
            cfg=cfg,
        )
        assert result["status"] == "success"

    conn = sqlite3.connect(str(kg_db))
    cur = conn.cursor()

    supported_edges = cur.execute(
        """
        SELECT e.weight, e.properties
        FROM edges e
        JOIN nodes t ON t.id = e.target_id
        WHERE e.edge_type = ? AND t.node_type = ? AND t.name = ?
        ORDER BY e.id
        """,
        ("identity_supported", "person", "Bill"),
    ).fetchall()
    assert len(supported_edges) == 2

    for weight, props_raw in supported_edges:
        assert float(weight) >= 0.55
        assert '"supporting_scene_count": 2' in props_raw
        assert '"source": "identity_candidate_accumulator"' in props_raw
        assert '"candidate_source": "scene_single_person_single_speaker"' in props_raw

    conn.close()


def test_update_kg_for_scene_identity_support_skips_conflicting_source(tmp_path: Path):
    kg_db = tmp_path / "kg_identity_support_conflict.db"
    cfg = {"paths": {"knowledge_graph_db": str(kg_db)}}

    first = update_kg_for_scene(
        scene_data={
            "index": 31,
            "start": 0.0,
            "end": 4.0,
            "entities": [{"name": "Bill", "type": "PERSON"}],
            "speaker_transcript": [
                {"speaker": "SPEAKER_00", "start": 0.0, "end": 4.0, "text": "Bill is here."},
            ],
        },
        scene_id="scene_identity_support_conflict_0001",
        video_id="video_test",
        video_path="samples/ingestion/Sein_Experiment/01x01 - Good News, Bad News.mp4",
        cfg=cfg,
    )
    assert first["status"] == "success"

    conn = sqlite3.connect(str(kg_db))
    cur = conn.cursor()
    conflicting_speaker = cur.execute(
        "SELECT id FROM nodes WHERE node_type = ? AND name = ?",
        ("speaker", "scene_identity_support_conflict_0001__speaker_00"),
    ).fetchone()
    george_person = cur.execute(
        "SELECT id FROM nodes WHERE node_type = ? AND name = ?",
        ("person", "George"),
    ).fetchone()
    if george_person is None:
        cur.execute(
            "INSERT INTO nodes (node_type, name, properties, occurrence_count, first_seen, last_seen, created_at) VALUES (?, ?, ?, 1, NULL, NULL, datetime('now'))",
            ("person", "George", "{}"),
        )
        george_person = (cur.lastrowid,)
    cur.execute(
        "INSERT INTO edges (source_id, target_id, edge_type, weight, properties, created_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
        (int(conflicting_speaker[0]), int(george_person[0]), "identity_evidence", 0.95, '{"source":"manual_conflict"}'),
    )
    conn.commit()
    conn.close()

    second = update_kg_for_scene(
        scene_data={
            "index": 32,
            "start": 0.0,
            "end": 4.0,
            "entities": [{"name": "Bill", "type": "PERSON"}],
            "speaker_transcript": [
                {"speaker": "SPEAKER_00", "start": 0.0, "end": 4.0, "text": "Bill is still here."},
            ],
        },
        scene_id="scene_identity_support_conflict_0002",
        video_id="video_test",
        video_path="samples/ingestion/Sein_Experiment/01x01 - Good News, Bad News.mp4",
        cfg=cfg,
    )
    assert second["status"] == "success"

    conn = sqlite3.connect(str(kg_db))
    cur = conn.cursor()
    supported_edges = cur.execute(
        "SELECT COUNT(*) FROM edges WHERE edge_type = ?",
        ("identity_supported",),
    ).fetchone()
    assert supported_edges is not None
    assert supported_edges[0] == 0
    conn.close()
