import pytest
import sqlite3
from unittest.mock import MagicMock, patch
from pathlib import Path
import requests
import copy
import json

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

# Helper for HITL confirmation
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
# set_payload tests (5)
# ---------------------------------------------------------------------------

@patch("requests.Session.put")
def test_set_payload_calls_qdrant_http_endpoint(mock_put):
    """R1: test_set_payload_calls_qdrant_http_endpoint — mock session PUT; assert correct URL + body"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_put.return_value = mock_response

    cfg = QdrantConfig(host="http://localhost:6333", collection="goodq_text", dim=384)
    client = QdrantClient(cfg)
    
    res = client.set_payload(["uuid-1", "uuid-2"], {"status": "promoted"})
    assert res is True
    mock_put.assert_called_once()
    args, kwargs = mock_put.call_args
    assert "http://localhost:6333/collections/goodq_text/points/payload?wait=true" in args[0]
    assert kwargs["json"]["payload"] == {"status": "promoted"}
    assert "points" in kwargs["json"]

@patch("requests.Session.put")
def test_set_payload_returns_false_on_http_failure(mock_put):
    """R1: test_set_payload_returns_false_on_http_failure — mock PUT returns 500; assert False, no raise"""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_put.return_value = mock_response

    cfg = QdrantConfig(host="http://localhost:6333", collection="goodq_text", dim=384)
    client = QdrantClient(cfg)

    res = client.set_payload(["uuid-1"], {"status": "promoted"})
    assert res is False

@patch("requests.Session.put")
def test_set_payload_returns_false_on_exception(mock_put):
    """R1: test_set_payload_returns_false_on_exception — mock PUT raises ConnectionError; assert False + WARNING logged"""
    mock_put.side_effect = requests.exceptions.ConnectionError("Connection refused")

    cfg = QdrantConfig(host="http://localhost:6333", collection="goodq_text", dim=384)
    client = QdrantClient(cfg)

    with patch("steps.common.qdrant_client.logger.warning") as mock_warn:
        res = client.set_payload(["uuid-1"], {"status": "promoted"})
        assert res is False
        mock_warn.assert_called()

@patch("requests.Session.put")
def test_set_payload_normalizes_point_ids_before_request(mock_put):
    """R1: test_set_payload_normalizes_point_ids_before_request — raw string UUID → normalized form in body"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_put.return_value = mock_response

    cfg = QdrantConfig(host="http://localhost:6333", collection="goodq_text", dim=384)
    client = QdrantClient(cfg)

    # Coerces arbitrary string to stable UUID5 form
    raw_points = ["my-arbitrary-string-key"]
    res = client.set_payload(raw_points, {"status": "promoted"})
    assert res is True
    
    mock_put.assert_called_once()
    args, kwargs = mock_put.call_args
    sent_points = kwargs["json"]["points"]
    assert len(sent_points) == 1
    assert sent_points[0] != "my-arbitrary-string-key"
    # Verify it looks like a valid UUID (36 chars with dashes)
    assert len(sent_points[0]) == 36

@patch("requests.Session.put")
def test_set_payload_empty_points_noop(mock_put):
    """R1: test_set_payload_empty_points_noop — set_payload([], ...) → no HTTP call, returns True"""
    cfg = QdrantConfig(host="http://localhost:6333", collection="goodq_text", dim=384)
    client = QdrantClient(cfg)

    res = client.set_payload([], {"status": "promoted"})
    assert res is True
    mock_put.assert_not_called()


# ---------------------------------------------------------------------------
# Lifecycle sync tests (4)
# ---------------------------------------------------------------------------

@patch("requests.post")
def test_promote_syncs_ucf_promotion_status_to_qdrant(mock_post, tmp_path, monkeypatch):
    """R2: test_promote_syncs_ucf_promotion_status_to_qdrant — UCF DB with 1 validated frame; assert requests.post called; qdrant_sync.status == 'ok'"""
    db_path = _create_mock_db_for_test(tmp_path, "validated", vector_key="vec-key-1", vector_collection="goodq_clip")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))

    mock_post.return_value = MagicMock(status_code=200, text="{}")

    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)

    res, rc = _confirm_tool_directly(client, "promote_ucf_to_memory", {"video_hash": "vh_test_001", "epoch_id": "epoch_test"})
    assert rc == 0
    assert res["status"] == "success"
    
    output = res["output"]
    assert output["status"] == "promoted_complete"
    assert output["promoted_count"] == 1
    
    q_sync = output["qdrant_sync"]
    assert q_sync["attempted"] is True
    assert q_sync["status"] == "ok"
    assert "goodq_clip" in q_sync["collections_attempted"]
    assert q_sync["points_attempted"] == 1
    assert not q_sync["failed_collections"]
    
    assert mock_post.call_count >= 1
    payload_calls = [
        call for call in mock_post.call_args_list
        if "collections/goodq_clip/points/payload" in call[0][0]
    ]
    assert len(payload_calls) == 1
    args, kwargs = payload_calls[0]
    assert kwargs["json"]["payload"] == {"ucf_promotion_status": "promoted"}

@patch("requests.post")
def test_promote_qdrant_sync_nonfatal_and_envelope_carries_warning(mock_post, tmp_path, monkeypatch):
    """R2: test_promote_qdrant_sync_nonfatal_and_envelope_carries_warning — requests.post returns 500; assert warning in envelope"""
    db_path = _create_mock_db_for_test(tmp_path, "validated", vector_key="vec-key-1", vector_collection="goodq_clip")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))

    mock_post.return_value = MagicMock(status_code=500, text="Internal Server Error")

    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)

    res, rc = _confirm_tool_directly(client, "promote_ucf_to_memory", {"video_hash": "vh_test_001", "epoch_id": "epoch_test"})
    assert rc == 0
    assert res["status"] == "success"
    
    output = res["output"]
    assert output["status"] == "promoted_complete"
    
    q_sync = output["qdrant_sync"]
    assert q_sync["attempted"] is True
    assert q_sync["status"] == "warning"
    assert "goodq_clip" in q_sync["failed_collections"]
    
    assert "warnings" in res
    assert "qdrant_payload_sync_failed" in res["warnings"]

@patch("requests.post")
def test_reject_and_supersede_sync_their_status_to_qdrant(mock_post, tmp_path, monkeypatch):
    """R2: test_reject_and_supersede_sync_their_status_to_qdrant — reject -> 'rejected', supersede -> 'superseded'"""
    # 1. Reject
    db_path = _create_mock_db_for_test(tmp_path, "validated", vector_key="vec-key-reject", vector_collection="goodq_clip")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    mock_post.return_value = MagicMock(status_code=200, text="{}")

    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)

    res, rc = _confirm_tool_directly(client, "reject_ucf_frames", {"video_hash": "vh_test_001", "epoch_id": "epoch_test", "reason": "bad resolution"})
    assert rc == 0
    assert res["output"]["status"] == "rejected_complete"
    
    assert mock_post.call_count == 1
    args, kwargs = mock_post.call_args
    assert "collections/goodq_clip/points/payload" in args[0]
    assert kwargs["json"]["payload"] == {"ucf_promotion_status": "rejected"}

    # 2. Supersede
    db_path_2 = _create_mock_db_for_test(tmp_path / "second", "promoted", vector_key="vec-key-supersede", vector_collection="goodq_clip")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path_2)

    res2, rc2 = _confirm_tool_directly(client, "supersede_ucf_frames", {"video_hash": "vh_test_001", "epoch_id": "epoch_test"})
    assert rc2 == 0
    assert res2["output"]["status"] == "superseded_complete"
    
    assert mock_post.call_count == 2
    args, kwargs = mock_post.call_args_list[1]
    assert "collections/goodq_clip/points/payload" in args[0]
    assert kwargs["json"]["payload"] == {"ucf_promotion_status": "superseded"}

@patch("requests.post")
def test_null_vector_key_frames_skipped_and_qdrant_sync_is_skipped(mock_post, tmp_path, monkeypatch):
    """R2: test_null_vector_key_frames_skipped_and_qdrant_sync_is_skipped — NULL vector_keys; assert requests.post NOT called; qdrant_sync status='skipped'"""
    db_path = _create_mock_db_for_test(tmp_path, "validated", vector_key=None, vector_collection="goodq_clip")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))

    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)

    res, rc = _confirm_tool_directly(client, "promote_ucf_to_memory", {"video_hash": "vh_test_001", "epoch_id": "epoch_test"})
    assert rc == 0
    
    q_sync = res["output"]["qdrant_sync"]
    assert q_sync["attempted"] is False
    assert q_sync["status"] == "skipped"
    mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# Default filter tests (3)
# ---------------------------------------------------------------------------

@patch("steps.common.qdrant_client.build_qdrant_client")
def test_qdrant_query_default_excludes_rejected_and_superseded(mock_build, monkeypatch):
    """R3: test_qdrant_query_default_excludes_rejected_and_superseded — no ucf args; assert must_not contains rejected + superseded"""
    mock_client = MagicMock()
    mock_client.query.return_value = []
    mock_build.return_value = mock_client
    
    client = MiniAgentClient(profile="safe")
    args = {
        "collection": "goodq_text",
        "query_vector": [0.1] * 384,
        "top_k": 5
    }
    res, rc = client.execute_tool(tool_name="qdrant_query", tool_args=args)
    assert rc == 0
    
    mock_client.query.assert_called_once()
    _, kwargs = mock_client.query.call_args
    p_filter = kwargs["payload_filter"]
    assert "must_not" in p_filter
    must_not_keys = [item["key"] for item in p_filter["must_not"]]
    must_not_vals = [item["match"]["value"] for item in p_filter["must_not"]]
    assert "ucf_promotion_status" in must_not_keys
    assert "rejected" in must_not_vals
    assert "superseded" in must_not_vals

@patch("steps.common.qdrant_client.build_qdrant_client")
def test_qdrant_query_ucf_status_filter_promoted_overrides_default(mock_build, monkeypatch):
    """R3: test_qdrant_query_ucf_status_filter_promoted_overrides_default — ucf_status_filter='promoted'; assert must has promoted clause; no default must_not"""
    mock_client = MagicMock()
    mock_client.query.return_value = []
    mock_build.return_value = mock_client

    client = MiniAgentClient(profile="safe")
    args = {
        "collection": "goodq_text",
        "query_vector": [0.1] * 384,
        "top_k": 5,
        "ucf_status_filter": "promoted"
    }
    res, rc = client.execute_tool(tool_name="qdrant_query", tool_args=args)
    assert rc == 0

    mock_client.query.assert_called_once()
    _, kwargs = mock_client.query.call_args
    p_filter = kwargs["payload_filter"]
    
    # Assert ucf_promotion_status == promoted is in must
    assert "must" in p_filter
    must_entries = p_filter["must"]
    promoted_match = [item for item in must_entries if item["key"] == "ucf_promotion_status" and item["match"]["value"] == "promoted"]
    assert len(promoted_match) == 1
    
    # Default exclusions should be suppressed
    if "must_not" in p_filter:
        must_not_keys = [item["key"] for item in p_filter["must_not"]]
        assert "ucf_promotion_status" not in must_not_keys

@patch("steps.common.qdrant_client.build_qdrant_client")
def test_qdrant_query_include_terminal_disables_default_exclusion(mock_build, monkeypatch):
    """R3: test_qdrant_query_include_terminal_disables_default_exclusion — ucf_include_terminal=True; assert NO ucf_promotion_status clause injected"""
    mock_client = MagicMock()
    mock_client.query.return_value = []
    mock_build.return_value = mock_client

    client = MiniAgentClient(profile="safe")
    args = {
        "collection": "goodq_text",
        "query_vector": [0.1] * 384,
        "top_k": 5,
        "ucf_include_terminal": True
    }
    res, rc = client.execute_tool(tool_name="qdrant_query", tool_args=args)
    assert rc == 0

    mock_client.query.assert_called_once()
    _, kwargs = mock_client.query.call_args
    p_filter = kwargs["payload_filter"]
    
    # Should be no ucf_promotion_status anywhere
    if "must" in p_filter:
        must_keys = [item["key"] for item in p_filter["must"]]
        assert "ucf_promotion_status" not in must_keys
    if "must_not" in p_filter:
        must_not_keys = [item["key"] for item in p_filter["must_not"]]
        assert "ucf_promotion_status" not in must_not_keys


# ---------------------------------------------------------------------------
# Filter composition and validation tests (5)
# ---------------------------------------------------------------------------

@patch("steps.common.qdrant_client.build_qdrant_client")
def test_qdrant_query_existing_must_is_preserved(mock_build, monkeypatch):
    """R3: test_qdrant_query_existing_must_is_preserved — pass existing must clause; assert it survives alongside UCF clause"""
    mock_client = MagicMock()
    mock_client.query.return_value = []
    mock_build.return_value = mock_client

    client = MiniAgentClient(profile="safe")
    existing_filter = {
        "must": [{"key": "scene_id", "match": {"value": "scene_0042"}}]
    }
    args = {
        "collection": "goodq_text",
        "query_vector": [0.1] * 384,
        "top_k": 5,
        "ucf_status_filter": "promoted",
        "payload_filter": existing_filter
    }
    res, rc = client.execute_tool(tool_name="qdrant_query", tool_args=args)
    assert rc == 0

    mock_client.query.assert_called_once()
    _, kwargs = mock_client.query.call_args
    p_filter = kwargs["payload_filter"]
    
    must_entries = p_filter["must"]
    assert len(must_entries) == 2
    
    scene_match = [item for item in must_entries if item["key"] == "scene_id"]
    promoted_match = [item for item in must_entries if item["key"] == "ucf_promotion_status"]
    assert len(scene_match) == 1
    assert len(promoted_match) == 1

@patch("steps.common.qdrant_client.build_qdrant_client")
def test_qdrant_query_existing_must_not_is_preserved(mock_build, monkeypatch):
    """R3: test_qdrant_query_existing_must_not_is_preserved — pass existing must_not; assert it survives alongside default exclusions"""
    mock_client = MagicMock()
    mock_client.query.return_value = []
    mock_build.return_value = mock_client

    client = MiniAgentClient(profile="safe")
    existing_filter = {
        "must_not": [{"key": "is_bad", "match": {"value": True}}]
    }
    args = {
        "collection": "goodq_text",
        "query_vector": [0.1] * 384,
        "top_k": 5,
        "payload_filter": existing_filter
    }
    res, rc = client.execute_tool(tool_name="qdrant_query", tool_args=args)
    assert rc == 0

    mock_client.query.assert_called_once()
    _, kwargs = mock_client.query.call_args
    p_filter = kwargs["payload_filter"]

    must_not_entries = p_filter["must_not"]
    assert len(must_not_entries) == 3  # 1 existing + 2 default exclusions
    
    bad_match = [item for item in must_not_entries if item["key"] == "is_bad"]
    ucf_match = [item for item in must_not_entries if item["key"] == "ucf_promotion_status"]
    assert len(bad_match) == 1
    assert len(ucf_match) == 2

def test_qdrant_query_invalid_ucf_status_filter_returns_error():
    """R3: test_qdrant_query_invalid_ucf_status_filter_returns_error — ucf_status_filter='staged'; assert status == 'error'"""
    client = MiniAgentClient(profile="safe")
    args = {
        "collection": "goodq_text",
        "query_vector": [0.1] * 384,
        "top_k": 5,
        "ucf_status_filter": "staged"
    }
    output = client._execute_qdrant_query(args)
    assert output["status"] == "error"
    assert output["reason"] == "invalid_ucf_status_filter"

def test_qdrant_query_invalid_ucf_status_filter_validated_also_rejected():
    """R3: test_qdrant_query_invalid_ucf_status_filter_validated_also_rejected — same for 'validated'"""
    client = MiniAgentClient(profile="safe")
    args = {
        "collection": "goodq_text",
        "query_vector": [0.1] * 384,
        "top_k": 5,
        "ucf_status_filter": "validated"
    }
    output = client._execute_qdrant_query(args)
    assert output["status"] == "error"
    assert output["reason"] == "invalid_ucf_status_filter"

@patch("steps.common.qdrant_client.build_qdrant_client")
def test_qdrant_query_no_double_must_not_on_repeated_calls(mock_build):
    """R3: test_qdrant_query_no_double_must_not_on_repeated_calls — deepcopy ensures no accumulation on args re-use"""
    mock_client = MagicMock()
    mock_client.query.return_value = []
    mock_build.return_value = mock_client

    client = MiniAgentClient(profile="safe")
    args = {
        "collection": "goodq_text",
        "query_vector": [0.1] * 384,
        "top_k": 5,
        "payload_filter": {}
    }
    
    # First call
    client._execute_qdrant_query(args)
    _, kwargs1 = mock_client.query.call_args
    p_filter1 = kwargs1["payload_filter"]
    assert len(p_filter1["must_not"]) == 2

    # Second call using the same args dict
    client._execute_qdrant_query(args)
    _, kwargs2 = mock_client.query.call_args
    p_filter2 = kwargs2["payload_filter"]
    assert len(p_filter2["must_not"]) == 2


@patch("requests.post")
@patch("scripts.ucf.validate_ucf_epoch.run_validation")
def test_materialization_bridge_lifecycle(mock_run_validation, mock_post, tmp_path, monkeypatch):
    """Verify materialization bridge lifecycle: ingest (0) -> validate -> promote (N) -> reject/supersede (0)."""
    # 1. Setup mock UCF ledger db with one staged frame
    db_path = _create_mock_db_for_test(tmp_path, "staged", vector_key="vec-key-1", vector_collection="goodq_clip")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    mock_run_validation.return_value = 0
    mock_post.return_value = MagicMock(status_code=200, text="{}")

    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)

    # Setup paths under tmp_path
    db_dir = tmp_path / "GoodQ_Data" / "epochs" / "epoch_test"
    db_dir.mkdir(parents=True, exist_ok=True)
    client.config["paths"]["db_dir"] = str(db_dir)
    client.config["paths"]["db_path"] = str(db_dir / "memory.db")
    client.config["paths"]["knowledge_graph_db"] = str(db_dir / "knowledge_graph.db")
    client.config["paths"]["processing"] = str(db_dir / "processing")

    # Recreate target directories
    video_processing_dir = db_dir / "processing" / "test"
    video_processing_dir.mkdir(parents=True, exist_ok=True)
    (video_processing_dir / "video").mkdir(parents=True, exist_ok=True)

    # 2. Write mock scene_manifest.json and temporal_index.json
    scene_manifest = {
        "scenes": [
            {
                "id": "scene_001",
                "start": 0.0,
                "end": 1.0,
                "confidence": 1.0,
                "keyframe": {
                    "hash": "kframe-hash-1",
                    "path": "frames/frame_0.png",
                    "ocr_text": "Sample OCR text"
                },
                "audio": {
                    "hash": "audio-hash-1",
                    "path": "audio/chunk_0.wav",
                    "transcript": "Sample speaker transcript",
                    "speaker_transcript": [
                        {
                            "start": 0.0,
                            "end": 1.0,
                            "speaker": "speaker_0",
                            "text": "Sample speaker transcript"
                        }
                    ]
                }
            }
        ]
    }
    with open(video_processing_dir / "video" / "scene_manifest.json", "w", encoding="utf-8") as f:
        json.dump(scene_manifest, f)

    temporal_index = {
        "segments": [
            {
                "scene_id": "scene_001",
                "start": 0.0,
                "end": 1.0,
                "speaker": "speaker_0",
                "text": "Sample speaker transcript"
            }
        ]
    }
    with open(video_processing_dir / "temporal_index.json", "w", encoding="utf-8") as f:
        json.dump(temporal_index, f)

    # Mock _fetch_vector_from_qdrant to return a dummy vector
    monkeypatch.setattr(client, "_fetch_vector_from_qdrant", lambda col, key: [0.1] * 384)

    # Check active database is empty/0 records initially
    assert not Path(client.config["paths"]["db_path"]).exists()
    assert not Path(client.config["paths"]["knowledge_graph_db"]).exists()

    # 3. Validate
    res, rc = _confirm_tool_directly(client, "validate_ucf_frames", {"video_hash": "vh_test_001", "epoch_id": "epoch_test"})
    assert rc == 0
    assert res["output"]["validated_count"] == 1

    # 4. Promote (trigger materialization)
    res, rc = _confirm_tool_directly(client, "promote_ucf_to_memory", {"video_hash": "vh_test_001", "epoch_id": "epoch_test"})
    assert rc == 0
    assert res["output"]["promoted_count"] == 1
    
    # Assert active database tables have records materialized
    conn_mem = sqlite3.connect(client.config["paths"]["db_path"])
    scenes = conn_mem.execute("SELECT id, video_hash, start, end FROM scenes").fetchall()
    assert len(scenes) == 1
    assert scenes[0][0] == "scene_001"
    
    segments = conn_mem.execute("SELECT id, speaker FROM segments").fetchall()
    assert len(segments) == 1
    assert segments[0][1] == "speaker_0"

    embeddings = conn_mem.execute("SELECT hash, modality, scene_id FROM embeddings").fetchall()
    assert len(embeddings) == 1
    assert embeddings[0][0] == "vec-key-1"

    fts = conn_mem.execute("SELECT scene_id, text FROM scene_text_fts").fetchall()
    assert len(fts) == 2  # OCR + transcript
    
    links = conn_mem.execute("SELECT parent_hash, child_hash, relation FROM links").fetchall()
    assert len(links) > 0

    conn_mem.close()

    # Assert Knowledge Graph nodes and edges materialized
    from lib.knowledge_graph import KnowledgeGraph
    with KnowledgeGraph(client.config["paths"]["knowledge_graph_db"]) as kg:
        stats = kg.get_statistics()
        assert stats["total_nodes"] > 0
        assert stats["total_edges"] > 0
        # Check specific node types exist
        node_types = [r[0] for r in kg.conn.execute("SELECT DISTINCT node_type FROM nodes").fetchall()]
        assert "video" in node_types
        assert "scene" in node_types
        assert "segment" in node_types
        assert "speaker" in node_types

    # 5. Reject (trigger dematerialization)
    # We must reset frame state to validated first to allow reject
    conn_ucf = sqlite3.connect(str(db_path))
    conn_ucf.execute("UPDATE context_frames SET promotion_status = 'validated'")
    conn_ucf.commit()
    conn_ucf.close()

    res, rc = _confirm_tool_directly(client, "reject_ucf_frames", {"video_hash": "vh_test_001", "epoch_id": "epoch_test", "reason": "test reject"})
    assert rc == 0
    assert res["output"]["rejected_count"] == 1

    # Verify that memory.db active records are dematerialized/deleted
    conn_mem = sqlite3.connect(client.config["paths"]["db_path"])
    assert len(conn_mem.execute("SELECT * FROM scenes").fetchall()) == 0
    assert len(conn_mem.execute("SELECT * FROM segments").fetchall()) == 0
    assert len(conn_mem.execute("SELECT * FROM embeddings").fetchall()) == 0
    assert len(conn_mem.execute("SELECT * FROM scene_text_fts").fetchall()) == 0
    assert len(conn_mem.execute("SELECT * FROM links").fetchall()) == 0
    conn_mem.close()

    # Verify Knowledge Graph is pruned (0 nodes/edges left, or support-aware clean)
    with KnowledgeGraph(client.config["paths"]["knowledge_graph_db"]) as kg:
        stats = kg.get_statistics()
        assert stats["total_nodes"] == 0
        assert stats["total_edges"] == 0

