from __future__ import annotations
import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from api.main import app
from steps.common.config_loader import load_configs, get_runtime_paths
from retrieval.temporal_reasoning import temporal_search

client = TestClient(app)

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
    
    response = client.post("/api/search/temporal", json=payload)
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
    response = client.post("/api/search/temporal", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["results"], list)
