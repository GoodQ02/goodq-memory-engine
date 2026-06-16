import pytest
import sqlite3
import requests
import uuid
import copy
from unittest.mock import MagicMock, patch
from pathlib import Path

from steps.common.qdrant_client import QdrantClient, QdrantConfig
from agents.mini_agent_client import MiniAgentClient

# Helper: Create a mock database with frame records
def _create_mock_db_for_test(tmp_path, promotion_status="validated", vector_key="vector-key-1", vector_collection="goodq_clip", vector_backend="qdrant"):
    db_path = tmp_path / "ucf_ledger.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
    CREATE TABLE IF NOT EXISTS media_sources (
        video_hash TEXT PRIMARY KEY,
        file_path TEXT NOT NULL,
        duration REAL NOT NULL,
        fps REAL NOT NULL,
        width INTEGER NOT NULL,
        height INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS context_frames (
        frame_id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_hash TEXT NOT NULL,
        ucf_schema_version TEXT NOT NULL,
        epoch_id TEXT NOT NULL,
        run_id TEXT NOT NULL,
        t_start REAL NOT NULL,
        t_end REAL NOT NULL,
        modality TEXT NOT NULL,
        worker_name TEXT NOT NULL,
        model_tag TEXT NOT NULL,
        confidence REAL NOT NULL DEFAULT 1.0,
        spatial_region TEXT,
        spatial_space TEXT NOT NULL DEFAULT 'normalized_yxyx_top_left',
        vector_key TEXT,
        vector_backend TEXT,
        vector_collection TEXT,
        vector_dim INTEGER,
        vector_model_tag TEXT,
        source_artifact_id TEXT,
        raw_ref TEXT,
        payload TEXT NOT NULL,
        payload_hash TEXT NOT NULL,
        promotion_status TEXT NOT NULL DEFAULT 'staged',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (video_hash) REFERENCES media_sources(video_hash)
    );
    """)
    conn.execute("INSERT OR REPLACE INTO media_sources VALUES ('vh_test_001', 'test.mp4', 10.0, 30.0, 1920, 1080, '2026-06-15')")
    
    # Log a frame
    conn.execute("""
    INSERT INTO context_frames (
        video_hash, ucf_schema_version, epoch_id, run_id, t_start, t_end,
        modality, worker_name, model_tag, confidence, spatial_region, spatial_space,
        vector_key, vector_backend, vector_collection, vector_dim, vector_model_tag,
        source_artifact_id, raw_ref, payload, payload_hash, promotion_status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        'vh_test_001', 'ucf.v0.1', 'epoch_test', 'run_test', 0.0, 1.0,
        'video', 'image_embed_clip', 'openai/clip-vit-large-patch14', 1.0,
        None, 'normalized_yxyx_top_left', vector_key, vector_backend, vector_collection,
        384, 'openai/clip-vit-large-patch14', 'scene_001', None, '{}', 'hash', promotion_status
    ))
    conn.commit()
    conn.close()
    return db_path

def _confirm_tool_directly(client, tool_name, tool_args):
    envelope, rc = client.execute_tool(tool_name=tool_name, tool_args=tool_args)
    assert rc == 3, f"Expected needs_confirmation (3), got {rc}"
    token = envelope["result"]["confirmation_token"]
    return client.execute_tool(
        tool_name=tool_name,
        tool_args=tool_args,
        confirm=True,
        confirmation_token=token,
    )

# ---------------------------------------------------------------------------
# Section 1: Point ID normalization in set_payload / _normalize_point_id
# ---------------------------------------------------------------------------

def test_normalize_point_id_edge_cases():
    """Stress test _normalize_point_id under empty, special, and malformed inputs."""
    cfg = QdrantConfig(host="http://localhost:6333", collection="goodq_text", dim=384)
    client = QdrantClient(cfg)

    # 1. Empty and None inputs
    assert client._normalize_point_id(None) is None
    assert client._normalize_point_id("") is None
    assert client._normalize_point_id("    ") is None
    assert client._normalize_point_id("\n\t") is None

    # 2. Integers: standard, zero, negative
    assert client._normalize_point_id(0) == 0
    assert client._normalize_point_id(999999) == 999999
    assert client._normalize_point_id(-123) == -123

    # 3. Numeric strings: standard, negative, decimal
    assert client._normalize_point_id("1234") == 1234
    assert client._normalize_point_id("  5678  ") == 5678
    
    # Negative numeric string does NOT match isdigit(), should map deterministically via UUID5
    neg_candidate = "-1234"
    res_neg = client._normalize_point_id(neg_candidate)
    assert len(res_neg) == 36
    assert isinstance(res_neg, str)

    # Decimal string does NOT match isdigit(), should map deterministically via UUID5
    decimal_candidate = "12.34"
    res_dec = client._normalize_point_id(decimal_candidate)
    assert len(res_dec) == 36
    assert isinstance(res_dec, str)

    # 4. Booleans (Python bool is a subclass of int!)
    # Verify behavior: it returns True / False because isinstance(True, int) is True!
    # Note: Qdrant rejects JSON boolean values for Point IDs, so this is a vulnerability/bug in normalization.
    assert client._normalize_point_id(True) is True
    assert client._normalize_point_id(False) is False

    # 5. UUIDs: standard, uppercase, hex-only
    uuid_raw = "9c23b2b0-95b8-4d5b-a63e-436f56c71c3a"
    assert client._normalize_point_id(uuid_raw) == uuid_raw
    assert client._normalize_point_id(uuid_raw.upper()) == uuid_raw
    assert client._normalize_point_id(uuid_raw.replace("-", "")) == uuid_raw

    # 6. Special Characters and Emojis
    spec_chars = "!@#$%^&*()_+{}|:<>?`-=[]\\;',./"
    res_spec = client._normalize_point_id(spec_chars)
    assert len(res_spec) == 36
    assert res_spec == client._normalize_point_id(spec_chars)  # Deterministic

    unicode_str = "你好🌟世界🚀"
    res_uni = client._normalize_point_id(unicode_str)
    assert len(res_uni) == 36
    assert res_uni == client._normalize_point_id(unicode_str)  # Deterministic

    # 7. Complex or malformed objects
    assert len(client._normalize_point_id({"key": "value"})) == 36
    assert len(client._normalize_point_id([1, 2, 3])) == 36

    class BadStringRepr:
        def __str__(self):
            raise ValueError("Intentional crash in str()")
    
    # Should catch exception and return None
    assert client._normalize_point_id(BadStringRepr()) is None


# ---------------------------------------------------------------------------
# Section 2: Query exclusions and validation in _execute_qdrant_query
# ---------------------------------------------------------------------------

def test_qdrant_query_invalid_args_raise_exceptions():
    """Verify that _execute_qdrant_query crashes with unhandled exceptions for missing or malformed keys."""
    client = MiniAgentClient(profile="safe")
    
    # 1. Missing query_vector key (raises KeyError)
    with pytest.raises(KeyError):
        client._execute_qdrant_query({"collection": "goodq_text"})

    # 2. None query_vector (raises TypeError: len())
    with pytest.raises(TypeError):
        client._execute_qdrant_query({"collection": "goodq_text", "query_vector": None})

    # 3. None collection (raises AttributeError on .lower())
    with pytest.raises(AttributeError):
        client._execute_qdrant_query({"collection": None, "query_vector": [0.1]*384})

    # 4. Non-dict payload_filter (raises AttributeError or TypeError)
    with pytest.raises(AttributeError):
        client._execute_qdrant_query({
            "collection": "goodq_text",
            "query_vector": [0.1]*384,
            "payload_filter": [1, 2] # non-empty list instead of dict to bypass the 'or {}' falsy check
        })


@patch("steps.common.qdrant_client.build_qdrant_client")
def test_qdrant_query_filter_malformation_handling(mock_build):
    """Verify how _execute_qdrant_query behaves when existing payload_filter fields are not lists."""
    client = MiniAgentClient(profile="safe")
    
    # payload_filter has "must" as a string instead of a list
    args = {
        "collection": "goodq_text",
        "query_vector": [0.1]*384,
        "payload_filter": {"must": "not-a-list"},
        "ucf_status_filter": "promoted"
    }
    with pytest.raises(AttributeError):
        client._execute_qdrant_query(args)

    # payload_filter has "must_not" as a string instead of a list
    args_must_not = {
        "collection": "goodq_text",
        "query_vector": [0.1]*384,
        "payload_filter": {"must_not": "not-a-list"},
        # No ucf_status_filter so it defaults to must_not exclusions
    }
    with pytest.raises(AttributeError):
        client._execute_qdrant_query(args_must_not)


@patch("steps.common.qdrant_client.build_qdrant_client")
def test_qdrant_query_filter_override_composition(mock_build):
    """Verify ucf_status_filter and default exclusions composition in _execute_qdrant_query."""
    mock_q = MagicMock()
    mock_q.query.return_value = []
    mock_build.return_value = mock_q

    client = MiniAgentClient(profile="safe")

    # Scenario A: ucf_status_filter present ("promoted")
    args = {
        "collection": "goodq_text",
        "query_vector": [0.1]*384,
        "ucf_status_filter": "promoted",
        "payload_filter": {
            "must": [{"key": "tag", "match": {"value": "important"}}]
        }
    }
    client._execute_qdrant_query(args)
    mock_q.query.assert_called_once()
    _, kwargs = mock_q.query.call_args
    p_filter = kwargs["payload_filter"]
    
    # ucf_promotion_status: promoted must be appended
    must = p_filter.get("must", [])
    assert len(must) == 2
    assert must[0] == {"key": "tag", "match": {"value": "important"}}
    assert must[1] == {"key": "ucf_promotion_status", "match": {"value": "promoted"}}
    # Default exclusions should be absent
    assert "must_not" not in p_filter

    mock_q.reset_mock()

    # Scenario B: ucf_status_filter absent, ucf_include_terminal is False (default)
    args = {
        "collection": "goodq_text",
        "query_vector": [0.1]*384,
        "payload_filter": {
            "must_not": [{"key": "is_draft", "match": {"value": True}}]
        }
    }
    client._execute_qdrant_query(args)
    mock_q.query.assert_called_once()
    _, kwargs = mock_q.query.call_args
    p_filter = kwargs["payload_filter"]
    
    # Must_not should contain the original clause AND the two defaults
    must_not = p_filter.get("must_not", [])
    assert len(must_not) == 3
    assert must_not[0] == {"key": "is_draft", "match": {"value": True}}
    assert must_not[1] == {"key": "ucf_promotion_status", "match": {"value": "rejected"}}
    assert must_not[2] == {"key": "ucf_promotion_status", "match": {"value": "superseded"}}
    assert "must" not in p_filter


# ---------------------------------------------------------------------------
# Section 3: Robustness of ucf sync in lifecycle operations (simulate outage)
# ---------------------------------------------------------------------------

@patch("steps.common.qdrant_client.QdrantClient.set_payload")
def test_lifecycle_promote_qdrant_outage_resilience(mock_set_payload, tmp_path, monkeypatch):
    """Simulate Qdrant network outage (raises ConnectionError) during promote_ucf_to_memory.
    Verify SQLite succeeds and warning payload is returned.
    """
    db_path = _create_mock_db_for_test(tmp_path, "validated", vector_key="vec-key-outage", vector_collection="goodq_clip")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))

    # set_payload raises exception representing network outage
    mock_set_payload.side_effect = requests.exceptions.ConnectionError("Connection refused")

    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)

    # Invoke promote_ucf_to_memory
    res, rc = _confirm_tool_directly(client, "promote_ucf_to_memory", {"video_hash": "vh_test_001", "epoch_id": "epoch_test"})
    assert rc == 0
    assert res["status"] == "success"

    output = res["output"]
    assert output["status"] == "promoted_complete"
    assert output["promoted_count"] == 1

    # Verify qdrant sync details are logged as warning
    q_sync = output["qdrant_sync"]
    assert q_sync["attempted"] is True
    assert q_sync["status"] == "warning"
    assert "goodq_clip" in q_sync["failed_collections"]
    assert q_sync["points_attempted"] == 1

    # Verify warning in envelope
    assert "warnings" in res
    assert "qdrant_payload_sync_failed" in res["warnings"]

    # Verify SQLite row was promoted anyway (database integrity preserved)
    conn = sqlite3.connect(str(db_path))
    status = conn.execute("SELECT promotion_status FROM context_frames WHERE video_hash = 'vh_test_001'").fetchone()[0]
    conn.close()
    assert status == "promoted"


@patch("steps.common.qdrant_client.QdrantClient.set_payload")
def test_lifecycle_reject_qdrant_outage_resilience(mock_set_payload, tmp_path, monkeypatch):
    """Simulate Qdrant network outage (returns False) during reject_ucf_frames.
    Verify SQLite succeeds and warning is returned.
    """
    db_path = _create_mock_db_for_test(tmp_path, "validated", vector_key="vec-key-outage", vector_collection="goodq_clip")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))

    # set_payload returns False representing HTTP error / outage
    mock_set_payload.return_value = False

    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)

    # Invoke reject_ucf_frames
    res, rc = _confirm_tool_directly(client, "reject_ucf_frames", {"video_hash": "vh_test_001", "epoch_id": "epoch_test", "reason": "outage test"})
    assert rc == 0
    assert res["status"] == "success"

    output = res["output"]
    assert output["status"] == "rejected_complete"

    # Verify qdrant sync details are logged as warning
    q_sync = output["qdrant_sync"]
    assert q_sync["attempted"] is True
    assert q_sync["status"] == "warning"

    # Verify warning in envelope
    assert "warnings" in res
    assert "qdrant_payload_sync_failed" in res["warnings"]

    # Verify SQLite row was rejected anyway
    conn = sqlite3.connect(str(db_path))
    status = conn.execute("SELECT promotion_status FROM context_frames WHERE video_hash = 'vh_test_001'").fetchone()[0]
    conn.close()
    assert status == "rejected"


@patch("steps.common.qdrant_client.QdrantClient.set_payload")
def test_lifecycle_supersede_qdrant_outage_resilience(mock_set_payload, tmp_path, monkeypatch):
    """Simulate Qdrant network outage (raises Timeout) during supersede_ucf_frames.
    Verify SQLite succeeds and warning is returned.
    """
    db_path = _create_mock_db_for_test(tmp_path, "promoted", vector_key="vec-key-outage", vector_collection="goodq_clip")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))

    # set_payload raises Timeout exception
    mock_set_payload.side_effect = requests.exceptions.Timeout("Request timed out")

    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)

    # Invoke supersede_ucf_frames
    res, rc = _confirm_tool_directly(client, "supersede_ucf_frames", {"video_hash": "vh_test_001", "epoch_id": "epoch_test"})
    assert rc == 0
    assert res["status"] == "success"

    output = res["output"]
    assert output["status"] == "superseded_complete"

    # Verify qdrant sync details are logged as warning
    q_sync = output["qdrant_sync"]
    assert q_sync["attempted"] is True
    assert q_sync["status"] == "warning"

    # Verify warning in envelope
    assert "warnings" in res
    assert "qdrant_payload_sync_failed" in res["warnings"]

    # Verify SQLite row was superseded anyway
    conn = sqlite3.connect(str(db_path))
    status = conn.execute("SELECT promotion_status FROM context_frames WHERE video_hash = 'vh_test_001'").fetchone()[0]
    conn.close()
    assert status == "superseded"
