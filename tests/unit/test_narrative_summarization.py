from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from api.main import app
from retrieval.narrative_summarizer import synthesize_narrative

client = TestClient(app, client=("127.0.0.1", 50000))


@pytest.fixture
def mock_temporal_search():
    with patch("retrieval.narrative_summarizer.temporal_search") as mock:
        yield mock


@pytest.fixture
def mock_llm_client():
    with patch("retrieval.narrative_summarizer.LLMClient") as mock_class:
        mock_instance = MagicMock()
        mock_instance.available = True
        mock_instance.get_active_model.return_value = "Llama-1B-Speed"
        mock_instance.chat.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "This is a cohesive narrative summary of the video clips."
                    }
                }
            ]
        }
        mock_class.return_value = mock_instance
        yield mock_instance


def generate_mock_scenes(count: int):
    return [
        {
            "scene_id": f"scene_{i:04d}",
            "source_file": f"tape_{i}.mp4",
            "start_time": 0.0,
            "end_time": 10.0,
            "timestamp_label": "2026-05-30 08:00:00",
            "entities": ["Jay"],
            "summary": f"Scene summary {i}",
            "evidence": {
                "transcript": f"Dialogue transcript {i}",
                "visual_tags": ["person"],
                "artifact_paths": []
            },
            "temporal_distance_from_previous": 0.0,
            "semantic_similarity_from_previous": 0.0
        }
        for i in range(count)
    ]


def test_summarize_fewer_than_20_scenes(mock_temporal_search, mock_llm_client):
    """
    Assert that when fewer than 20 scenes are retrieved:
    - truncated is False
    - warnings is empty
    - source_count equals the actual count
    """
    mock_temporal_search.return_value = {
        "query": {"entities": ["Jay"], "grouping": "semantic_episode"},
        "results": generate_mock_scenes(7)
    }

    mock_llm_client.get_active_model.return_value = "Llama3.2-Ollama"
    result = synthesize_narrative(entities=["Jay"], summary_style="narrative")
    assert result["status"] == "success"
    assert result["source_count"] == 7
    assert result["truncated"] is False
    assert result["warnings"] == []
    assert "cohesive narrative summary" in result["summary"]
    assert result["model_used"] == "Llama3.2-Ollama"


def test_summarize_more_than_20_scenes(mock_temporal_search, mock_llm_client):
    """
    Assert that when more than 20 scenes are retrieved:
    - truncated is True
    - warnings contains a truncation notification
    - source_count is capped at 20
    """
    mock_temporal_search.return_value = {
        "query": {"entities": ["Jay"], "grouping": "semantic_episode"},
        "results": generate_mock_scenes(25)
    }

    result = synthesize_narrative(entities=["Jay"], summary_style="bullets")
    assert result["status"] == "success"
    assert result["source_count"] == 20
    assert result["truncated"] is True
    assert result["warnings"] == ["source_results_truncated"]


def test_summarize_empty_scenes(mock_temporal_search, mock_llm_client):
    """
    Assert correct handling of zero match results.
    """
    mock_temporal_search.return_value = {
        "query": {"entities": ["Nonexistent"], "grouping": "semantic_episode"},
        "results": []
    }

    result = synthesize_narrative(entities=["Nonexistent"])
    assert result["status"] == "success"
    assert result["source_count"] == 0
    assert result["truncated"] is False
    assert result["warnings"] == ["no_matching_scenes"]
    assert "No matching scenes" in result["summary"]


def test_summarize_llm_unavailable(mock_temporal_search, mock_llm_client):
    """
    Assert that when LLM service is offline or unavailable, a status of
    'llm_unavailable' is returned rather than crashing.
    """
    mock_temporal_search.return_value = {
        "query": {"entities": ["Jay"], "grouping": "semantic_episode"},
        "results": generate_mock_scenes(5)
    }
    mock_llm_client.available = False

    result = synthesize_narrative(entities=["Jay"])
    assert result["status"] == "llm_unavailable"
    assert "query" in result
    assert result["query"]["entities"] == ["Jay"]
    assert result["source_count"] == 5
    assert result["truncated"] is False
    assert result["warnings"] == ["model_unavailable"]


def test_summarize_llm_exception(mock_temporal_search, mock_llm_client):
    """
    Assert exception resilience during chat inference requests.
    """
    mock_temporal_search.return_value = {
        "query": {"entities": ["Jay"], "grouping": "semantic_episode"},
        "results": generate_mock_scenes(5)
    }
    mock_llm_client.chat.side_effect = Exception("Mock connection lost")

    result = synthesize_narrative(entities=["Jay"])
    assert result["status"] == "llm_unavailable"
    assert "query" in result
    assert result["source_count"] == 5
    assert result["truncated"] is False
    assert result["warnings"] == ["llm_inference_error"]
    assert "Mock connection lost" not in str(result)


def test_summarize_api_endpoint_rejects_legacy_synchronous_body(
    mock_temporal_search,
    mock_llm_client,
):
    response = client.post(
        "/api/search/temporal/summarize",
        json={
            "entities": ["Jay"],
            "summary_style": "executive",
            "max_results": 10,
        },
    )

    assert response.status_code == 422
    mock_temporal_search.assert_not_called()


def test_parse_narrative_segments():
    """
    Directly verify structured segment parsing, marker stripping, and auto-healing logic.
    """
    from retrieval.narrative_summarizer import parse_narrative_segments
    
    mock_scenes = [
        {"scene_id": "id1", "source_file": "file1.mp4", "start_time": 0.0, "end_time": 10.0},
        {"scene_id": "id2", "source_file": "file2.mp4", "start_time": 10.0, "end_time": 20.0}
    ]
    
    # Test case 1: Standard index < 10 start
    raw_text = "[Scene 1] Segment one text. [Scene 2] Segment two text."
    clean, segments = parse_narrative_segments(raw_text, mock_scenes)
    
    assert clean == "Segment one text. Segment two text."
    assert len(segments) == 2
    assert segments[0]["scene_id"] == "id1"
    assert segments[0]["text"] == "Segment one text."
    assert segments[0]["scene_index"] == 1
    assert "source_file" not in segments[0]
    assert segments[1]["scene_id"] == "id2"
    assert segments[1]["text"] == "Segment two text."
    assert segments[1]["scene_index"] == 2
    assert "source_file" not in segments[1]

    # Test case 2: Auto-healing for deep transition mode starting with [Scene 1] (shift + 1)
    mock_scenes_3 = [
        {"scene_id": "id1", "source_file": "file1.mp4", "start_time": 0.0, "end_time": 10.0},
        {"scene_id": "id2", "source_file": "file2.mp4", "start_time": 10.0, "end_time": 20.0},
        {"scene_id": "id3", "source_file": "file3.mp4", "start_time": 20.0, "end_time": 30.0}
    ]
    raw_text_deep_1 = "Some leading text of scene 1. [Scene 1] Segment two text. [Scene 2] Segment three text."
    clean_deep_1, segments_deep_1 = parse_narrative_segments(raw_text_deep_1, mock_scenes_3)
    assert clean_deep_1 == "Some leading text of scene 1. Segment two text. Segment three text."
    assert len(segments_deep_1) == 3
    assert segments_deep_1[0]["scene_id"] == "id1"
    assert segments_deep_1[0]["text"] == "Some leading text of scene 1."
    assert segments_deep_1[0]["scene_index"] == 1
    assert segments_deep_1[1]["scene_id"] == "id2"
    assert segments_deep_1[1]["text"] == "Segment two text."
    assert segments_deep_1[1]["scene_index"] == 2
    assert segments_deep_1[2]["scene_id"] == "id3"
    assert segments_deep_1[2]["text"] == "Segment three text."
    assert segments_deep_1[2]["scene_index"] == 3

    # Test case 3: Auto-healing for deep transition mode starting with [Scene 2] (no shift)
    raw_text_deep_2 = "Some leading text of scene 1. [Scene 2] Segment two text."
    clean_deep_2, segments_deep_2 = parse_narrative_segments(raw_text_deep_2, mock_scenes)
    assert clean_deep_2 == "Some leading text of scene 1. Segment two text."
    assert len(segments_deep_2) == 2
    assert segments_deep_2[0]["scene_id"] == "id1"
    assert segments_deep_2[0]["text"] == "Some leading text of scene 1."
    assert segments_deep_2[0]["scene_index"] == 1
    assert segments_deep_2[1]["scene_id"] == "id2"
    assert segments_deep_2[1]["text"] == "Segment two text."
    assert segments_deep_2[1]["scene_index"] == 2

    # Test case 4: Whitespace deep prefix (should not trigger auto-healing shift)
    raw_text_spaces = "            [Scene 1] Segment one text. [Scene 2] Segment two text."
    clean_spaces, segments_spaces = parse_narrative_segments(raw_text_spaces, mock_scenes)
    assert clean_spaces == "Segment one text. Segment two text."
    assert len(segments_spaces) == 2
    assert segments_spaces[0]["scene_id"] == "id1"
    assert segments_spaces[0]["text"] == "Segment one text."
    assert segments_spaces[0]["scene_index"] == 1


def test_summarize_uses_one_injected_config_for_retrieval_and_models(
    mock_temporal_search,
    mock_llm_client,
    monkeypatch,
):
    import retrieval.narrative_summarizer as module

    cfg = {
        "paths": {
            "db_path": "private-epoch/memory.db",
            "knowledge_graph_db": "private-epoch/knowledge_graph.db",
        },
        "llm": {"models": {}},
    }
    mock_temporal_search.return_value = {
        "query": {"entities": ["Jay"], "grouping": "semantic_episode"},
        "results": generate_mock_scenes(1),
    }
    mock_llm_client.get_active_model.return_value = "Llama3.2-Ollama"
    monkeypatch.setattr(
        module,
        "load_configs",
        MagicMock(side_effect=AssertionError("ambient config reload")),
    )
    build_models = MagicMock(return_value=[{"name": "verified-model"}])
    monkeypatch.setattr(module, "build_llm_models", build_models)

    result = synthesize_narrative(
        entities=["Jay"],
        config=cfg,
        expected_epoch_id="private-epoch",
    )

    assert result["status"] == "success"
    build_models.assert_called_once_with(cfg)
    assert mock_temporal_search.call_args.kwargs["config"] is cfg
    assert mock_temporal_search.call_args.kwargs["expected_epoch_id"] == "private-epoch"


def test_summarize_uses_verified_models_without_rebuilding_policy(
    mock_temporal_search,
    mock_llm_client,
    monkeypatch,
):
    import retrieval.narrative_summarizer as module

    cfg = {"paths": {}, "llm": {}}
    verified_models = [MagicMock(name="verified-model")]
    mock_temporal_search.return_value = {
        "query": {"entities": ["Jay"], "grouping": "semantic_episode"},
        "results": generate_mock_scenes(1),
    }
    mock_llm_client.get_active_model.return_value = "Llama3.2-Ollama"
    rebuild_policy = MagicMock(
        side_effect=AssertionError("model policy rebuilt after verification")
    )
    monkeypatch.setattr(module, "build_llm_models", rebuild_policy)

    result = synthesize_narrative(
        entities=["Jay"],
        config=cfg,
        expected_epoch_id="private-epoch",
        models=verified_models,
        allow_model_activation=False,
        allow_environment_proxies=False,
    )

    assert result["status"] == "success"
    rebuild_policy.assert_not_called()
    assert module.LLMClient.call_args.kwargs["models"] is verified_models
    assert module.LLMClient.call_args.kwargs["allow_auto_activation"] is False
    assert module.LLMClient.call_args.kwargs["allow_environment_proxies"] is False


def test_temporal_search_rejects_epoch_drift_before_database_open(
    tmp_path,
    monkeypatch,
):
    import retrieval.temporal_reasoning as module

    configured_epoch = tmp_path / "epoch_current"
    paths = {
        "db_path": configured_epoch / "memory.db",
        "knowledge_graph_db": configured_epoch / "knowledge_graph.db",
    }
    monkeypatch.setattr(module, "get_runtime_paths", lambda _cfg: paths)
    connect = MagicMock(side_effect=AssertionError("database opened before epoch check"))
    monkeypatch.setattr(module.sqlite3, "connect", connect)

    with pytest.raises(RuntimeError, match="epoch"):
        module.temporal_search(
            config={"paths": {}},
            expected_epoch_id="epoch_changed",
        )

    connect.assert_not_called()

