import pytest
from unittest.mock import MagicMock
from api.routes.runtime import _evaluate_qdrant_audio_payloads

def test_qdrant_payload_invariant():
    """
    Regression test to ensure Qdrant payload invariant is maintained.
    Specifically checks that payloads contain 'video_id', 'scene_id', and 'ucf_promotion_status'.
    """
    
    # Valid payload
    valid_payload = {
        "video_id": "test_video",
        "scene_id": "scene_001",
        "ucf_promotion_status": "promoted",
        "run_id": "run_123",
        "embedding_id": "emb_123",
        "component": "audio_embed_clap",
        "step": "audio_embed_clap",
        "model": "test",
        "created_at": "2026-01-01",
        "commit_ts_utc": "2026-01-01T00:00:00Z"
    }
    
    # Missing ucf_promotion_status
    invalid_payload_1 = {
        "video_id": "test_video",
        "scene_id": "scene_001",
        "run_id": "run_123"
    }
    
    # Missing video_id and scene_id
    invalid_payload_2 = {
        "ucf_promotion_status": "promoted",
        "run_id": "run_123"
    }

    # Evaluate using the runtime evaluator
    result_valid = _evaluate_qdrant_audio_payloads([valid_payload], scene_ids={"scene_001"}, video_ids={"test_video"})

    assert result_valid == {
        "current_run_qdrant_proven": 1,
        "provenance_unverified": 0,
        "missing_required_fields": {},
        "scene_mismatch_count": 0,
        "video_mismatch_count": 0,
    }
    
    assert "video_id" in valid_payload
    assert "scene_id" in valid_payload
    assert "ucf_promotion_status" in valid_payload
    
    assert "ucf_promotion_status" not in invalid_payload_1
    assert "video_id" not in invalid_payload_2


def test_qdrant_search_payload_invariants(monkeypatch):
    """
    Verify that Qdrant query results return points containing 'video_id', 'scene_id',
    and 'ucf_promotion_status' in their payloads using a deterministic transport.
    """
    import requests
    from steps.common.qdrant_client import QdrantClient, QdrantConfig

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

    original_session_post = requests.Session.post
    post_called = []

    def mock_session_post(self, url, json=None, **kwargs):
        if "points/search" in url:
            post_called.append(url)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_search_result
            return mock_resp
        return original_session_post(self, url, json=json, **kwargs)

    monkeypatch.setattr(requests.Session, "post", mock_session_post)
    monkeypatch.setattr(QdrantClient, "collection_exists", lambda self: True)

    cfg = QdrantConfig(host="http://mock_qdrant:6333", collection="test_collection", dim=384, enabled=True)
    client = QdrantClient(cfg)
    results = client.query(
        [0.1] * 384,
        top_k=2,
        retrieval_context="system.healthcheck",
    )

    assert len(results) == 2
    assert len(post_called) == 1

    for res in results:
        payload = res.get("payload", {})
        assert "video_id" in payload, f"Missing video_id in payload: {payload}"
        assert "scene_id" in payload, f"Missing scene_id in payload: {payload}"
        assert "ucf_promotion_status" in payload, f"Missing ucf_promotion_status in payload: {payload}"
