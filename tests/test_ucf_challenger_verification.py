import pytest
import sqlite3
import os
import requests
from unittest.mock import MagicMock
from scripts.ucf.ucf_ledger import UCFLedgerClient, UCFRecord
from tests.test_qdrant_payload_invariant import test_qdrant_search_payload_invariants

def test_ucf_rounding_duplicate_prevention(tmp_path):
    """
    R2 duplicate prevention test:
    Verify that if t_start is slightly different (e.g. 12.3456 vs 12.346)
    they both round to 12.346 and trigger UNIQUE constraint violation / ON CONFLICT ignore/replace,
    and all metadata fields ('model_tag', 'raw_ref', 'source_artifact_id') are successfully updated.
    """
    db_file = str(tmp_path / "ucf_ledger.db")
    client = UCFLedgerClient(db_file)
    client.init_schema()

    # Register media source first to satisfy foreign key constraint
    client.register_media(
        video_hash="hash123",
        file_path="dummy/path.mp4",
        duration=100.0,
        fps=30.0,
        width=1920,
        height=1080
    )

    # 1. Insert first frame with t_start = 12.3456 (rounds to 12.346)
    client.log_frame(
        video_hash="hash123",
        epoch_id="epoch1",
        run_id="run1",
        t_start=12.3456,
        t_end=15.0,
        modality="video",
        worker_name="object_detect",
        model_tag="model_v1",
        confidence=0.9,
        source_artifact_id="art1",
        raw_ref="ref1",
        payload={"label": "person"}
    )

    # Verify database state after first insertion
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT t_start, model_tag, raw_ref, source_artifact_id, run_id FROM context_frames")
    rows = cursor.fetchall()
    assert len(rows) == 1
    # 12.3456 must be rounded to 12.346
    assert rows[0][0] == 12.346
    assert rows[0][1] == "model_v1"
    assert rows[0][2] == "ref1"
    assert rows[0][3] == "art1"
    assert rows[0][4] == "run1"

    # 2. Insert second frame with same unique keys but slightly different t_start = 12.346 (which also rounds/is 12.346)
    # and different metadata fields
    client.log_frame(
        video_hash="hash123",
        epoch_id="epoch1",
        run_id="run2",
        t_start=12.346,
        t_end=15.0,
        modality="video",
        worker_name="object_detect",
        model_tag="model_v2",
        confidence=0.95,
        source_artifact_id="art2",
        raw_ref="ref2",
        payload={"label": "person", "new_field": "val"}
    )

    # Verify that conflict is handled and metadata fields are updated correctly
    cursor.execute("SELECT t_start, model_tag, raw_ref, source_artifact_id, run_id, confidence, payload FROM context_frames")
    rows = cursor.fetchall()
    assert len(rows) == 1  # No duplicate rows inserted!
    assert rows[0][0] == 12.346
    assert rows[0][1] == "model_v2"
    assert rows[0][2] == "ref2"
    assert rows[0][3] == "art2"
    assert rows[0][4] == "run2"
    assert rows[0][5] == 0.95
    assert "new_field" in rows[0][6]

    conn.close()


def test_r4_regression_assertion_failure_on_bad_live_payload(monkeypatch):
    """
    R4 regression test robustness:
    Verify that AssertionError is raised if we query live Qdrant and payloads are incorrect.
    We mock requests to simulate a live Qdrant instance that returns collections,
    but scrolls them returning incorrect payloads (missing video_id, scene_id, or ucf_promotion_status).
    Calling the test function should raise AssertionError.
    """
    # Force environmental variable for live host so test checks it
    monkeypatch.setenv("GOODQ_QDRANT_HOST", "http://fake_live_qdrant:6333")

    original_get = requests.get
    original_post = requests.post

    def mock_get(url, **kwargs):
        if "fake_live_qdrant:6333/collections" in url:
            # Simulate Qdrant running and having a collection
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "result": {
                    "collections": [{"name": "fake_collection"}]
                }
            }
            return resp
        return original_get(url, **kwargs)

    def mock_post(url, json=None, **kwargs):
        if "fake_live_qdrant:6333/collections/fake_collection/points/scroll" in url:
            # Simulate scroll returning point with invalid payload (missing ucf_promotion_status)
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "result": {
                    "points": [
                        {
                            "id": "point-bad",
                            "payload": {
                                "video_id": "test_video",
                                "scene_id": "scene_001",
                                # "ucf_promotion_status" is missing!
                            }
                        }
                    ]
                }
            }
            return resp
        # For the mock query part (Part 1 of the test)
        if "mock_qdrant:6333" in url:
            # Return valid mocked search results as expected by Part 1 of the test
            mock_payloads = [
                {
                    "video_id": "test_video",
                    "scene_id": "scene_001",
                    "ucf_promotion_status": "promoted",
                },
                {
                    "video_id": "test_video",
                    "scene_id": "scene_002",
                    "ucf_promotion_status": "staged",
                }
            ]
            mock_search_result = {
                "result": [
                    {
                        "id": "point-1",
                        "score": 0.99,
                        "payload": mock_payloads[0]
                    },
                    {
                        "id": "point-2",
                        "score": 0.95,
                        "payload": mock_payloads[1]
                    }
                ]
            }
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = mock_search_result
            return resp
        return original_post(url, json=json, **kwargs)

    monkeypatch.setattr(requests, "get", mock_get)
    monkeypatch.setattr(requests, "post", mock_post)

    # When calling test_qdrant_search_payload_invariants, it should execute both mocked part and live part,
    # and fail on the live part with AssertionError because our mock returns an invalid payload.
    with pytest.raises(AssertionError) as exc_info:
        test_qdrant_search_payload_invariants(monkeypatch)
    
    assert "missing ucf_promotion_status" in str(exc_info.value).lower()
