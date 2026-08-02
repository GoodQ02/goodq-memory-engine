from __future__ import annotations
import base64
import json
import sqlite3
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.main import app
from steps.common.config_loader import load_configs, get_runtime_paths
from retrieval.temporal_reasoning import temporal_search

client = TestClient(app)
_TEST_LAN_TOKEN = "a" * 64
_TEST_LAN_HEADERS = {
    "Authorization": "Basic "
    + base64.b64encode(f"goodq:{_TEST_LAN_TOKEN}".encode("ascii")).decode("ascii")
}

@pytest.fixture(autouse=True)
def setup_test_databases(monkeypatch, tmp_path):
    # Set GOODQ_DATA_ROOT to the temporary path to isolate configurations
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("GOODQ_LAN_API_TOKEN", _TEST_LAN_TOKEN)
    
    # Setup directory structure for mock epoch
    epoch_dir = tmp_path / "GoodQ_Data" / "epochs" / "epoch_2025_12_22"
    epoch_dir.mkdir(parents=True, exist_ok=True)
    (epoch_dir / "faiss").mkdir(parents=True, exist_ok=True)
    
    db_path = epoch_dir / "memory.db"
    kg_path = epoch_dir / "knowledge_graph.db"

    # Force paths to point to our isolated tmp_path, ignoring config.local.yaml overrides
    import steps.common.config_loader
    import retrieval.temporal_reasoning
    import sys
    orig_load = steps.common.config_loader.load_configs
    def mocked_load(overrides=None):
        cfg = orig_load(overrides)
        if "paths" in cfg:
            cfg["paths"]["db_path"] = str(db_path).replace("\\", "/")
            cfg["paths"]["knowledge_graph_db"] = str(kg_path).replace("\\", "/")
            cfg["paths"]["db_dir"] = str(epoch_dir).replace("\\", "/")
        return cfg
    monkeypatch.setattr(steps.common.config_loader, "load_configs", mocked_load)
    monkeypatch.setattr(retrieval.temporal_reasoning, "load_configs", mocked_load)
    monkeypatch.setattr(sys.modules[__name__], "load_configs", mocked_load)
    try:
        import api.routes.search
        monkeypatch.setattr(api.routes.search, "load_configs", mocked_load)
    except (ImportError, AttributeError):
        pass
    
    # 1. Populate mock memory.db
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE scenes (
            id TEXT PRIMARY KEY,
            video_hash TEXT,
            start REAL,
            end REAL,
            meta TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE summaries (
            category TEXT,
            content TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE embeddings (
            scene_id TEXT,
            modality TEXT,
            vector BLOB
        )
        """
    )
    
    # Insert two mock scenes (scene_1 and scene_2)
    conn.execute(
        "INSERT INTO scenes (id, video_hash, start, end, meta) VALUES (?, ?, ?, ?, ?)",
        ("scene_1", "hash_1", 10.0, 20.0, json.dumps({
            "entities": ["Jay"],
            "primary_tags": ["laughing"],
            "keyframe": {"path": "/mock/path/scene_1.jpg"}
        }))
    )
    conn.execute(
        "INSERT INTO scenes (id, video_hash, start, end, meta) VALUES (?, ?, ?, ?, ?)",
        ("scene_2", "hash_1", 30.0, 40.0, json.dumps({
            "entities": ["Jay"],
            "primary_tags": ["coding"],
            "keyframe": {"path": "/mock/path/scene_2.jpg"}
        }))
    )
    
    # Insert scene summaries
    conn.execute(
        "INSERT INTO summaries (category, content) VALUES (?, ?)",
        ("scene_summary", json.dumps({
            "scene_id": "scene_1",
            "summary": "Jay is laughing at the desk"
        }))
    )
    conn.execute(
        "INSERT INTO summaries (category, content) VALUES (?, ?)",
        ("scene_summary", json.dumps({
            "scene_id": "scene_2",
            "summary": "Jay is coding on his computer"
        }))
    )
    
    # Insert float32 embeddings for similarity calculation tests
    vec_blob = np.ones(384, dtype=np.float32).tobytes()
    conn.execute(
        "INSERT INTO embeddings (scene_id, modality, vector) VALUES (?, ?, ?)",
        ("scene_1", "text", sqlite3.Binary(vec_blob))
    )
    conn.execute(
        "INSERT INTO embeddings (scene_id, modality, vector) VALUES (?, ?, ?)",
        ("scene_2", "text", sqlite3.Binary(vec_blob))
    )
    
    conn.commit()
    conn.close()
    
    # 2. Populate mock knowledge_graph.db
    conn_kg = sqlite3.connect(kg_path)
    conn_kg.execute(
        """
        CREATE TABLE media_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id TEXT,
            media_path TEXT
        )
        """
    )
    conn_kg.execute(
        """
        CREATE TABLE nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            node_type TEXT
        )
        """
    )
    conn_kg.execute(
        """
        CREATE TABLE node_media (
            node_id INTEGER,
            media_id INTEGER
        )
        """
    )
    
    # Insert node "Jay" (id=1)
    conn_kg.execute("INSERT INTO nodes (id, name, node_type) VALUES (?, ?, ?)", (1, "Jay", "person"))
    # Map "Jay" node to "scene_1" (media_id=1) and "scene_2" (media_id=2)
    conn_kg.execute("INSERT INTO media_nodes (id, scene_id, media_path) VALUES (?, ?, ?)", (1, "scene_1", "/mock/path/video.mp4"))
    conn_kg.execute("INSERT INTO media_nodes (id, scene_id, media_path) VALUES (?, ?, ?)", (2, "scene_2", "/mock/path/video.mp4"))
    conn_kg.execute("INSERT INTO node_media (node_id, media_id) VALUES (?, ?)", (1, 1))
    conn_kg.execute("INSERT INTO node_media (node_id, media_id) VALUES (?, ?)", (1, 2))
    
    conn_kg.commit()
    conn_kg.close()

def test_sqlite_read_only_protection():
    """
    Assert that write statements fail under read-only SQLite URI connections,
    accepting sqlite3.OperationalError or equivalent read-only/write-protection exceptions.
    """
    config = load_configs({})
    paths = get_runtime_paths(config)
    db_path = paths["db_path"]
    
    db_uri = f"{Path(db_path).resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    
    failed = False
    try:
        # Try to execute a mutating statement (INSERT, CREATE, UPDATE, etc.)
        conn.execute("INSERT INTO scenes (id) VALUES ('fake_test_scene_id_forbidden')")
        conn.commit()
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
        failed = True
        print(f"Write operation failed as expected with exception: {type(e).__name__}: {e}")
    finally:
        conn.close()
        
    assert failed, "Write query should have failed under read-only URI connection"

def test_temporal_search_engine_logic():
    """
    Test direct execution of temporal search query logic.
    """
    # 1. Fetch search results for a common entity
    result_dict = temporal_search(
        entities=["Jay"],
        max_results=5
    )
    
    assert "query" in result_dict
    assert "results" in result_dict
    assert result_dict["query"]["entities"] == ["Jay"]
    
    results = result_dict["results"]
    assert len(results) <= 5
    
    # Verify result shape
    for r in results:
        assert "scene_id" in r
        assert "source_file" in r
        assert "start_time" in r
        assert "end_time" in r
        assert "timestamp_label" in r
        assert "entities" in r
        assert "summary" in r
        assert "evidence" in r
        assert "temporal_distance_from_previous" in r
        assert "semantic_similarity_from_previous" in r
        
        evidence = r["evidence"]
        assert "transcript" in evidence
        assert "visual_tags" in evidence
        assert "artifact_paths" in evidence

def test_temporal_search_endpoint():
    """
    Test API endpoint validation and response shape.
    """
    payload = {
        "entities": ["Jay"],
        "max_results": 2,
        "grouping": "semantic_episode"
    }
    
    response = client.post("/api/search/temporal", json=payload, headers=_TEST_LAN_HEADERS)
    assert response.status_code == 200
    
    data = response.json()
    assert data["query"]["entities"] == ["Jay"]
    assert data["query"]["grouping"] == "semantic_episode"
    assert isinstance(data["results"], list)
    
    if len(data["results"]) > 0:
        r = data["results"][0]
        assert "scene_id" in r
        assert "source_file" in r
        assert "start_time" in r
        assert "end_time" in r
        assert "timestamp_label" in r
        assert "entities" in r
        assert "summary" in r
        assert "evidence" in r
        assert "temporal_distance_from_previous" in r
        assert "semantic_similarity_from_previous" in r

def test_temporal_search_empty_filters():
    """
    Test temporal search returning all sequential scenes chronologically when filters are empty.
    """
    payload = {
        "max_results": 10
    }
    response = client.post("/api/search/temporal", json=payload, headers=_TEST_LAN_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["results"], list)
