from __future__ import annotations

import json
from pathlib import Path
import re
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routes import summary as summary_route

@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_db_paths(tmp_path):
    """Create temporary DB files and patch paths config to prevent using real databases."""
    kg_db = tmp_path / "knowledge_graph.db"
    kg_db.write_text("")  # ensure kg_db.exists() is True
    
    mem_db = tmp_path / "memory.db"
    mem_db.write_text("")  # ensure mem_db.exists() is True
    
    # Setup patch for _get_kg_db_path and config loader
    with patch("api.routes.summary._get_kg_db_path", return_value=kg_db), \
         patch("steps.common.config_loader.load_configs") as mock_load:
        
        mock_load.return_value = {
            "paths": {
                "db_path": str(mem_db),
                "knowledge_graph_db": str(kg_db)
            },
            "llm": {
                "features": {
                    "video_summarization": True
                },
                "api_url": "http://localhost:1234/v1/chat/completions",
                "model": "test-model"
            }
        }
        yield kg_db, mem_db


def test_capabilities_endpoint(client) -> None:
    """Verify the summary capabilities endpoint returns correct LLM feature flags."""
    resp = client.get("/api/summary/capabilities")
    assert resp.status_code == 200
    assert resp.json() == {"video_summarization_enabled": True}


def test_invalid_hash_validation(client) -> None:
    """Verify endpoints validate hash patterns and return 400 Bad Request on malformed inputs."""
    # GET endpoint
    resp_get = client.get("/api/summary/video/not-a-hash")
    assert resp_get.status_code == 400
    assert "Invalid video hash format" in resp_get.json()["detail"]

    # Status endpoint
    resp_status = client.get("/api/summary/video/not-a-hash/status")
    assert resp_status.status_code == 400
    assert "Invalid video hash format" in resp_status.json()["detail"]

    # POST generate endpoint
    resp_post = client.post("/api/summary/video/not-a-hash/generate")
    assert resp_post.status_code == 400
    assert "Invalid video hash format" in resp_post.json()["detail"]


@patch("sqlite3.connect")
def test_missing_video_checks(mock_connect, client) -> None:
    """Verify endpoints return 404 Not Found if video hash does not exist in the database."""
    # Mock database to return no matching video row
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # Mock scenes check: returns None (video not in KG DB)
    mock_cursor.execute.return_value.fetchone.return_value = None
    mock_conn.execute.return_value.fetchone.return_value = None

    valid_missing_hash = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"

    # POST Generate missing video
    resp_post = client.post(f"/api/summary/video/{valid_missing_hash}/generate")
    assert resp_post.status_code == 404
    assert "not found in database" in resp_post.json()["detail"]

    # GET missing video summary
    resp_get = client.get(f"/api/summary/video/{valid_missing_hash}")
    assert resp_get.status_code == 404
    assert "Video summary not found" in resp_get.json()["detail"]


@patch("steps.video_summarizer.step.run_step")
@patch("sqlite3.connect")
@patch("requests.get")
def test_successful_generate_flow(mock_get, mock_connect, mock_run, client) -> None:
    """Verify that a valid video queues a background job, acquires lock during run, and releases it."""
    valid_hash = "1234567890abcdef1234567890abcdef"
    
    # Mock connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # Mock scenes table search returns a row (video exists)
    mock_conn.execute.return_value.fetchone.return_value = (1,)
    
    # Mock LLM API pre-flight check returning 200 OK
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_get.return_value = mock_resp
    
    # Trace the lock status during the background task execution
    status_during_run = []
    
    def mock_run_step_side_effect(cfg, v_hash):
        # Check if hash is in active summarizations list during execution
        status_during_run.append(v_hash in summary_route._running_summarizations)
        
    mock_run.side_effect = mock_run_step_side_effect
    
    # Ensure current locks list is empty initially
    summary_route._running_summarizations.clear()

    # Trigger generation
    resp = client.post(f"/api/summary/video/{valid_hash}/generate")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert "successfully started" in resp.json()["message"]
    
    # Verify that the lock was active during background task execution
    assert status_during_run == [True]
    
    # Verify lock status is now idle (released)
    status_resp = client.get(f"/api/summary/video/{valid_hash}/status")
    assert status_resp.status_code == 200
    assert status_resp.json() == {"status": "idle"}

    # Manually add the lock to test duplicate protection (409 Conflict)
    summary_route._running_summarizations.add(valid_hash)
    try:
        resp_dup = client.post(f"/api/summary/video/{valid_hash}/generate")
        assert resp_dup.status_code == 409
        assert "already running" in resp_dup.json()["detail"]
    finally:
        # Clean up lock manually
        summary_route._running_summarizations.discard(valid_hash)


@patch("sqlite3.connect")
def test_get_video_summary_success(mock_connect, client) -> None:
    """Verify that GET /video/{video_hash} parses and returns the persisted summary & provenance."""
    valid_hash = "abcdefabcdefabcdefabcdefabcdef12"
    
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # Mock master table check: summaries table exists
    mock_cursor.fetchone.side_effect = [("summaries",)]
    
    # Mock summaries row payload
    payload = json.dumps({
        "video_hash": valid_hash,
        "summary": "This is a great test summary.",
        "method": "llm",
        "provenance": {
            "model_backend": "test-model (http://localhost:1234/v1/chat/completions)",
            "prompt_version": "v1.0.0",
            "timestamp": "2026-06-13T00:00:00Z"
        }
    })
    
    mock_cursor.fetchall.return_value = [(payload, "2026-06-13 00:00:00")]
    
    resp = client.get(f"/api/summary/video/{valid_hash}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["video_hash"] == valid_hash
    assert data["summary"] == "This is a great test summary."
    assert data["method"] == "llm"
    assert data["provenance"]["model_backend"] == "test-model (http://localhost:1234/v1/chat/completions)"
