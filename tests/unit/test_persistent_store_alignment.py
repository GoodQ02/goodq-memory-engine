import json
import sqlite3
from pathlib import Path

from cli import persistent_store_alignment_audit
from lib.persistent_store_alignment import build_persistent_store_alignment


def _write_scene_results(path: Path) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "video_id": "video-a",
                    "scenes": [
                        {"scene_id": "scene-a1"},
                        {"scene_id": "scene-a2"},
                    ],
                },
                {
                    "video_id": "video-b",
                    "temporal_index": {"segments": [{"scene_id": "scene-b1"}]},
                },
            ]
        ),
        encoding="utf-8",
    )


def _create_memory_db(path: Path, *, include_all_scenes: bool = False) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE scenes(id TEXT PRIMARY KEY, video_hash TEXT);
        CREATE TABLE segments(id TEXT PRIMARY KEY, scene_id TEXT, video_hash TEXT);
        CREATE TABLE embeddings(hash TEXT PRIMARY KEY, scene_id TEXT, modality TEXT);
        CREATE TABLE memory_commit_events(scene_id TEXT, modality TEXT, committed INTEGER);
        """
    )
    scenes = [("scene-a1", "video-a"), ("scene-a2", "video-a")]
    if include_all_scenes:
        scenes.append(("scene-b1", "video-b"))
    conn.executemany("INSERT INTO scenes(id, video_hash) VALUES (?,?)", scenes)
    conn.executemany(
        "INSERT INTO segments(id, scene_id, video_hash) VALUES (?,?,?)",
        [("seg-a1", "scene-a1", "video-a"), ("seg-a2", "scene-a2", "video-a")],
    )
    conn.executemany(
        "INSERT INTO embeddings(hash, scene_id, modality) VALUES (?,?,?)",
        [("emb-a1", "scene-a1", "frame_text"), ("emb-a2", "scene-a2", "audio")],
    )
    conn.executemany(
        "INSERT INTO memory_commit_events(scene_id, modality, committed) VALUES (?,?,?)",
        [
            ("scene-a1", "frame_text", 1),
            ("scene-a2", "audio", 1),
            ("scene-a2", "audio", 1),
            ("scene-a2", "audio", 1),
            ("scene-a2", "audio", 1),
        ],
    )
    conn.commit()
    conn.close()


def _create_kg_db(path: Path, *, include_all_scenes: bool = False) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE media_nodes(id INTEGER PRIMARY KEY, scene_id TEXT);
        CREATE TABLE node_media(node_id INTEGER, media_id INTEGER);
        """
    )
    rows = [(1, "scene-a1"), (2, "scene-b1")]
    if include_all_scenes:
        rows.append((3, "scene-a2"))
    conn.executemany("INSERT INTO media_nodes(id, scene_id) VALUES (?,?)", rows)
    conn.executemany("INSERT INTO node_media(node_id, media_id) VALUES (?,?)", [(10, 1), (11, 2)])
    conn.commit()
    conn.close()


def test_persistent_store_alignment_reports_memory_and_kg_scene_gaps(tmp_path: Path):
    scene_results = tmp_path / "scene_ingest_results.json"
    memory_db = tmp_path / "memory.db"
    kg_db = tmp_path / "knowledge_graph.db"
    _write_scene_results(scene_results)
    _create_memory_db(memory_db)
    _create_kg_db(kg_db)

    report = build_persistent_store_alignment(
        scene_results_path=scene_results,
        memory_db_path=memory_db,
        knowledge_graph_db_path=kg_db,
    )

    assert report["mode"] == "read_only_persistent_store_alignment"
    assert report["status"] == "warn"
    assert report["alignment"]["canonical_scene_count"] == 3
    assert report["memory"]["scene_rows_present"] == 2
    assert report["memory"]["missing_scene_count"] == 1
    assert report["knowledge_graph"]["scene_rows_present"] == 2
    assert report["knowledge_graph"]["missing_scene_count"] == 1
    assert report["memory"]["embedding_rows_by_modality"] == {"audio": 1, "frame_text": 1}
    assert report["memory"]["current_run_proof"] is False
    assert report["knowledge_graph"]["current_run_proof"] is False
    assert "commit_events_accumulated_across_runs_possible" in report["memory"]["warnings"]
    assert report["safety_boundary"]["databases_mutated"] is False


def test_persistent_store_alignment_reports_ok_when_scene_presence_matches(tmp_path: Path):
    scene_results = tmp_path / "scene_ingest_results.json"
    memory_db = tmp_path / "memory.db"
    kg_db = tmp_path / "knowledge_graph.db"
    _write_scene_results(scene_results)
    _create_memory_db(memory_db, include_all_scenes=True)
    _create_kg_db(kg_db, include_all_scenes=True)

    report = build_persistent_store_alignment(
        scene_results_path=scene_results,
        memory_db_path=memory_db,
        knowledge_graph_db_path=kg_db,
    )

    assert report["status"] == "ok"
    assert report["memory"]["missing_scene_count"] == 0
    assert report["knowledge_graph"]["missing_scene_count"] == 0


def test_persistent_store_alignment_cli_json_output_parses(tmp_path: Path, capsys):
    scene_results = tmp_path / "scene_ingest_results.json"
    memory_db = tmp_path / "memory.db"
    kg_db = tmp_path / "knowledge_graph.db"
    _write_scene_results(scene_results)
    _create_memory_db(memory_db, include_all_scenes=True)
    _create_kg_db(kg_db, include_all_scenes=True)

    exit_code = persistent_store_alignment_audit.main(
        [
            "--scene-results",
            str(scene_results),
            "--memory-db",
            str(memory_db),
            "--knowledge-graph-db",
            str(kg_db),
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["safety_boundary"]["raw_run_roots_scanned"] is False
