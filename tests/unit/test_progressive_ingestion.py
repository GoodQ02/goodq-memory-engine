import tempfile
import json
import sqlite3
from pathlib import Path
import pytest

from cli import run_ingestion
from steps.common.atomic_io import atomic_write_json
from steps.video.scene_visual_embeddings import _mirror_scene_vector_status

def test_window_grouping_logic():
    # Test deterministic overlap window index calculation
    chunk_size = 300.0
    chunk_overlap = 10.0
    step = chunk_size - chunk_overlap
    
    scenes = [
        {"start": 0.0, "end": 50.0},
        {"start": 289.0, "end": 295.0},
        {"start": 290.0, "end": 310.0},
        {"start": 300.0, "end": 350.0},
        {"start": 580.0, "end": 610.0},
    ]
    
    grouped = {}
    for scene in scenes:
        window_idx = int(scene["start"] // step)
        grouped.setdefault(window_idx, []).append(scene)
        
    # Expect:
    # 0.0 -> window 0
    # 289.0 -> window 0 (289 // 290 = 0)
    # 290.0 -> window 1 (290 // 290 = 1)
    # 300.0 -> window 1 (300 // 290 = 1)
    # 580.0 -> window 2 (580 // 290 = 2)
    assert len(grouped[0]) == 2
    assert len(grouped[1]) == 2
    assert len(grouped[2]) == 1


def test_checkpoint_read_write(tmp_path):
    checkpoint_path = tmp_path / "progressive_ingestion_state.json"

    state_record = {
        "checkpoint_version": 2,
        "run_id": "test_run",
        "video_hash": "test_hash",
        "windows": {
            "2": {
                "window_idx": 2,
                "window_status": "committed",
                "scene_ids": ["s1", "s2"],
                "persistence_targets": {
                    "memory_db": "committed",
                    "knowledge_graph": "committed",
                    "vectors": "committed",
                    "scene_manifest": "committed",
                    "temporal_index": "committed",
                },
            }
        },
    }
    
    atomic_write_json(checkpoint_path, state_record)
    assert checkpoint_path.exists()
    
    loaded = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert loaded["run_id"] == "test_run"
    assert loaded["windows"]["2"]["window_idx"] == 2


def _write_scene_stores(epoch_root: Path, scene_ids: list[str]) -> None:
    memory_db = epoch_root / "memory.db"
    conn = sqlite3.connect(memory_db)
    conn.execute("CREATE TABLE scenes (id TEXT PRIMARY KEY, video_hash TEXT)")
    conn.executemany(
        "INSERT INTO scenes(id, video_hash) VALUES (?, 'video-hash')",
        [(scene_id,) for scene_id in scene_ids],
    )
    conn.commit()
    conn.close()

    graph_db = epoch_root / "knowledge_graph.db"
    conn = sqlite3.connect(graph_db)
    conn.execute("CREATE TABLE media_nodes (scene_id TEXT)")
    conn.executemany(
        "INSERT INTO media_nodes(scene_id) VALUES (?)",
        [(scene_id,) for scene_id in scene_ids],
    )
    conn.commit()
    conn.close()


def _write_window_artifacts(
    processing_dir: Path,
    scene_ids: list[str],
    *,
    vectors_committed: bool = True,
):
    video_dir = processing_dir / "video"
    video_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = video_dir / "scene_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "phase6_complete": vectors_committed,
                "phase6_status": "complete" if vectors_committed else "failed",
                "phase6_vector_commit": {
                    "enabled": True,
                    "vector_points_attempted": len(scene_ids) * 2,
                    "qdrant_ok": vectors_committed,
                },
                "scenes": [
                    {
                        "scene_id": scene_id,
                        "clip_id": f"clip-{scene_id}",
                        "dino_id": f"dino-{scene_id}",
                        "qdrant_ok": vectors_committed,
                    }
                    for scene_id in scene_ids
                ],
            }
        ),
        encoding="utf-8",
    )
    temporal_path = video_dir / "temporal_index.json"
    temporal_path.write_text(
        json.dumps(
            {"segments": [{"scene_id": scene_id} for scene_id in scene_ids]}
        ),
        encoding="utf-8",
    )
    return manifest_path, temporal_path


def test_isolated_checkpoint_marks_suppressed_stores_not_applicable(tmp_path):
    epoch_root = tmp_path / "epoch_isolated"
    processing_dir = epoch_root / "processing" / "video-a"
    epoch_root.mkdir()
    scene_ids = ["scene-1", "scene-2"]
    manifest_path, temporal_path = _write_window_artifacts(processing_dir, scene_ids)
    cfg = {
        "ingestion_isolation": True,
        "paths": {
            "db_path": str(epoch_root / "memory.db"),
            "knowledge_graph_db": str(epoch_root / "knowledge_graph.db"),
        },
    }

    record = run_ingestion._build_progressive_checkpoint_record(
        cfg=cfg,
        run_id="run-isolated",
        video_hash="video-hash",
        window_idx=0,
        window_start=0.0,
        window_end=300.0,
        scene_ids=scene_ids,
        graph_applicable=False,
        graph_failed=False,
        vectors_applicable=True,
        scene_manifest_path=manifest_path,
        temporal_index_applicable=True,
        temporal_index_committed=True,
        temporal_index_path=temporal_path,
    )

    assert not (epoch_root / "memory.db").exists()
    assert not (epoch_root / "knowledge_graph.db").exists()
    assert record["window_status"] == "committed"
    assert record["persistence_targets"] == {
        "memory_db": "not_applicable",
        "knowledge_graph": "not_applicable",
        "vectors": "committed",
        "scene_manifest": "committed",
        "temporal_index": "committed",
    }


def test_nonisolated_checkpoint_probes_actual_sqlite_graph_and_artifacts(tmp_path):
    epoch_root = tmp_path / "epoch_materialized"
    processing_dir = epoch_root / "processing" / "video-a"
    epoch_root.mkdir()
    scene_ids = ["scene-1", "scene-2"]
    _write_scene_stores(epoch_root, scene_ids)
    manifest_path, temporal_path = _write_window_artifacts(processing_dir, scene_ids)
    cfg = {
        "ingestion_isolation": False,
        "paths": {
            "db_path": str(epoch_root / "memory.db"),
            "knowledge_graph_db": str(epoch_root / "knowledge_graph.db"),
        },
    }

    record = run_ingestion._build_progressive_checkpoint_record(
        cfg=cfg,
        run_id="run-materialized",
        video_hash="video-hash",
        window_idx=0,
        window_start=0.0,
        window_end=300.0,
        scene_ids=scene_ids,
        graph_applicable=True,
        graph_failed=False,
        vectors_applicable=True,
        scene_manifest_path=manifest_path,
        temporal_index_applicable=True,
        temporal_index_committed=True,
        temporal_index_path=temporal_path,
    )

    assert record["window_status"] == "committed"
    assert set(record["persistence_targets"].values()) == {"committed"}

    temporal_path.unlink()
    _write_window_artifacts(
        processing_dir,
        scene_ids,
        vectors_committed=False,
    )[1].unlink()
    failed = run_ingestion._build_progressive_checkpoint_record(
        cfg=cfg,
        run_id="run-materialized",
        video_hash="video-hash",
        window_idx=1,
        window_start=290.0,
        window_end=590.0,
        scene_ids=scene_ids,
        graph_applicable=True,
        graph_failed=False,
        vectors_applicable=True,
        scene_manifest_path=manifest_path,
        temporal_index_applicable=True,
        temporal_index_committed=True,
        temporal_index_path=temporal_path,
    )
    assert failed["window_status"] == "failed"
    assert failed["persistence_targets"]["vectors"] == "failed"
    assert failed["persistence_targets"]["temporal_index"] == "failed"


def test_vector_checkpoint_requires_manifest_commit_evidence(tmp_path):
    processing_dir = tmp_path / "processing" / "video-a"
    scene_ids = ["scene-1"]
    manifest_path, temporal_path = _write_window_artifacts(
        processing_dir,
        scene_ids,
        vectors_committed=False,
    )

    record = run_ingestion._build_progressive_checkpoint_record(
        cfg={"ingestion_isolation": True, "paths": {}},
        run_id="run-vector-proof",
        video_hash="video-hash",
        window_idx=0,
        window_start=0.0,
        window_end=300.0,
        scene_ids=scene_ids,
        graph_applicable=False,
        graph_failed=False,
        vectors_applicable=True,
        scene_manifest_path=manifest_path,
        temporal_index_applicable=True,
        temporal_index_committed=True,
        temporal_index_path=temporal_path,
    )

    assert record["window_status"] == "failed"
    assert record["persistence_targets"]["vectors"] == "failed"


def test_vector_checkpoint_is_not_applicable_when_retrieval_is_disabled(tmp_path):
    processing_dir = tmp_path / "processing" / "video-a"
    scene_ids = ["scene-1"]
    manifest_path, temporal_path = _write_window_artifacts(processing_dir, scene_ids)

    record = run_ingestion._build_progressive_checkpoint_record(
        cfg={"ingestion_isolation": True, "paths": {}},
        run_id="run-no-vector-target",
        video_hash="video-hash",
        window_idx=0,
        window_start=0.0,
        window_end=300.0,
        scene_ids=scene_ids,
        graph_applicable=False,
        graph_failed=False,
        vectors_applicable=False,
        scene_manifest_path=manifest_path,
        temporal_index_applicable=True,
        temporal_index_committed=True,
        temporal_index_path=temporal_path,
    )

    assert record["window_status"] == "committed"
    assert record["persistence_targets"]["vectors"] == "not_applicable"


def test_resume_accepts_only_v2_windows_with_current_persistence_evidence(tmp_path):
    processing_dir = tmp_path / "processing" / "video-a"
    manifest_path, temporal_path = _write_window_artifacts(
        processing_dir,
        ["scene-1", "scene-2"],
    )
    cfg = {
        "ingestion_isolation": True,
        "phase6": {"enabled": True, "retrieval": {"enable": True}},
        "paths": {},
    }
    state = {
        "checkpoint_version": 2,
        "video_hash": "video-hash",
        "windows": {
            "0": {
                "window_idx": 0,
                "window_status": "committed",
                "scene_ids": ["scene-1"],
                "persistence_targets": {
                    "memory_db": "not_applicable",
                    "knowledge_graph": "not_applicable",
                    "vectors": "committed",
                    "scene_manifest": "committed",
                    "temporal_index": "committed",
                },
            },
            "1": {
                "window_idx": 1,
                "window_status": "failed",
                "scene_ids": ["scene-failed"],
                "persistence_targets": {
                    "memory_db": "not_applicable",
                    "knowledge_graph": "not_applicable",
                    "vectors": "failed",
                    "scene_manifest": "committed",
                    "temporal_index": "failed",
                },
            },
            "2": {
                "window_idx": 2,
                "window_status": "committed",
                "scene_ids": ["scene-2"],
                "persistence_targets": {
                    "memory_db": "not_applicable",
                    "knowledge_graph": "not_applicable",
                    "vectors": "committed",
                    "scene_manifest": "committed",
                    "temporal_index": "committed",
                },
            },
        },
    }
    assert run_ingestion._completed_checkpoint_window_indices(
        state,
        "video-hash",
        cfg=cfg,
        processing_dir=processing_dir,
    ) == {0, 2}
    assert run_ingestion._progressive_checkpoint_cleanup_ready(
        state_data=state,
        video_hash="video-hash",
        cfg=cfg,
        processing_dir=processing_dir,
        expected_window_indices=[0, 2],
        phase6_complete=True,
    )
    assert run_ingestion._completed_checkpoint_window_indices(
        state,
        "other-video",
        cfg=cfg,
        processing_dir=processing_dir,
    ) == set()

    temporal_path.unlink()
    assert run_ingestion._completed_checkpoint_window_indices(
        state,
        "video-hash",
        cfg=cfg,
        processing_dir=processing_dir,
    ) == set()

    assert manifest_path.exists()
    assert run_ingestion._completed_checkpoint_window_indices(
        {"video_hash": "video-hash", "window_idx": 99, "main_db_committed": True},
        "video-hash",
        cfg=cfg,
        processing_dir=processing_dir,
    ) == set()


def test_checkpoint_cleanup_rejects_qdrant_complete_video_with_failed_target(tmp_path):
    state = {
        "checkpoint_version": 2,
        "video_hash": "video-hash",
        "windows": {
            "0": {
                "window_idx": 0,
                "window_status": "failed",
                "scene_ids": ["scene-0"],
                "persistence_targets": {
                    "memory_db": "failed",
                    "knowledge_graph": "not_applicable",
                    "vectors": "committed",
                    "scene_manifest": "committed",
                    "temporal_index": "committed",
                },
                "failed_targets": ["memory_db"],
            }
        },
    }

    assert not run_ingestion._progressive_checkpoint_cleanup_ready(
        state_data=state,
        video_hash="video-hash",
        cfg={"ingestion_isolation": False, "paths": {}},
        processing_dir=tmp_path,
        expected_window_indices=[0],
        phase6_complete=True,
    )


def test_nonisolated_resume_rejects_checkpoint_when_graph_evidence_disappears(
    tmp_path,
    monkeypatch,
):
    epoch_root = tmp_path / "epoch-materialized"
    processing_dir = epoch_root / "processing" / "video-a"
    epoch_root.mkdir()
    scene_ids = ["scene-1"]
    _write_scene_stores(epoch_root, scene_ids)
    manifest_path, temporal_path = _write_window_artifacts(processing_dir, scene_ids)
    cfg = {
        "ingestion_isolation": False,
        "phase6": {"enabled": True, "retrieval": {"enable": True}},
        "knowledge_graph": {"enabled": True},
        "paths": {
            "db_path": str(epoch_root / "memory.db"),
            "knowledge_graph_db": str(epoch_root / "knowledge_graph.db"),
        },
    }
    monkeypatch.setattr(run_ingestion, "KNOWLEDGE_GRAPH_AVAILABLE", True)
    record = run_ingestion._build_progressive_checkpoint_record(
        cfg=cfg,
        run_id="run-materialized",
        video_hash="video-hash",
        window_idx=0,
        window_start=0.0,
        window_end=300.0,
        scene_ids=scene_ids,
        graph_applicable=True,
        graph_failed=False,
        vectors_applicable=True,
        scene_manifest_path=manifest_path,
        temporal_index_applicable=True,
        temporal_index_committed=True,
        temporal_index_path=temporal_path,
    )
    state = {
        "checkpoint_version": 2,
        "video_hash": "video-hash",
        "windows": {"0": record},
    }

    assert run_ingestion._completed_checkpoint_window_indices(
        state,
        "video-hash",
        cfg=cfg,
        processing_dir=processing_dir,
    ) == {0}

    (epoch_root / "knowledge_graph.db").unlink()
    assert run_ingestion._completed_checkpoint_window_indices(
        state,
        "video-hash",
        cfg=cfg,
        processing_dir=processing_dir,
    ) == set()


def test_runtime_checkpoint_replaces_legacy_boolean_contract():
    source = Path(run_ingestion.__file__).read_text(encoding="utf-8")
    assert "_build_progressive_checkpoint_record(" in source
    assert "_completed_checkpoint_window_indices(" in source
    assert "checkpoint_cleanup_ready = _progressive_checkpoint_cleanup_ready(" in source
    assert "if checkpoint_cleanup_ready:" in source
    assert "'main_db_committed'" not in source
    assert "'kg_db_committed'" not in source
    assert "'vectors_committed':" not in source
    assert "'manifest_updated':" not in source
    assert "'temporal_index_updated':" not in source


def test_isolated_resume_uses_manifest_without_opening_memory_db(tmp_path):
    memory_db = tmp_path / "memory.db"
    cfg = {
        "ingestion_isolation": True,
        "paths": {"db_path": str(memory_db)},
    }
    manifest_by_id = {"scene-1": {"scene_id": "scene-1", "content_state": "signal"}}

    meta = run_ingestion._get_checkpoint_scene_meta(
        cfg,
        "scene-1",
        manifest_by_id,
    )

    assert meta == manifest_by_id["scene-1"]
    assert not memory_db.exists()


def test_resumed_scene_outputs_are_restored_to_timeline_order():
    outputs = [
        {"scene_id": "scene-later", "start": 300.0, "index": 2},
        {"scene_id": "scene-earlier", "start": 0.0, "index": 1},
    ]
    assert [
        item["scene_id"]
        for item in run_ingestion._sort_checkpoint_scene_outputs(outputs)
    ] == ["scene-earlier", "scene-later"]


def test_mirror_scene_vector_status_incremental():
    # Verify that visual embeddings status mirroring does not overwrite
    # other scenes' status flags if they were not in the current batch
    scenes = [
        {"id": "scene_1", "qdrant_ok": True, "faiss_ok": True},
        {"id": "scene_2", "qdrant_ok": False, "faiss_ok": False},
        {"id": "scene_3", "qdrant_ok": "not_attempted", "faiss_ok": "not_attempted"},
    ]
    
    pooled_clip = {"scene_2": True}
    pooled_dino = {"scene_2": True}
    
    _mirror_scene_vector_status(
        scenes,
        pooled_clip=pooled_clip,
        pooled_dino=pooled_dino,
        qdrant_ok=True,
        faiss_ok=True
    )
    
    # scene_1 should be completely untouched
    assert scenes[0]["qdrant_ok"] is True
    # scene_2 should be updated
    assert scenes[1]["qdrant_ok"] is True
    # scene_3 should be completely untouched
    assert scenes[2]["qdrant_ok"] == "not_attempted"
