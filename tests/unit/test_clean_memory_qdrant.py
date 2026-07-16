from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
import urllib.request
import urllib.error
import sys

from cli.clean_memory import ResolvedPlanConfiguration, resolve_plan_configuration
from steps.common.clean_memory import QdrantCollectionEvidence

REPO_ROOT = Path(__file__).resolve().parents[2]
EPOCH_ID = "epoch_2026_07_observer"
CONFIG_SCOPE_SHA256 = "b" * 64


def _as_config_path(path: Path) -> str:
    return path.absolute().as_posix()


def _config(outer_root: Path, *, epoch_id: str = EPOCH_ID) -> dict[str, object]:
    data_root = outer_root / "GoodQ_Data"
    epoch_root = data_root / "epochs" / epoch_id

    def rendered(path: Path) -> str:
        return _as_config_path(path)

    collections = {
        role: f"goodq_{role}_{epoch_id}"
        for role in ("text", "clip", "dino", "audio")
    }
    paths: dict[str, object] = {
        "data_root": rendered(data_root),
        "db_dir": rendered(epoch_root),
        "db_path": rendered(epoch_root / "memory.db"),
        "knowledge_graph_db": rendered(epoch_root / "knowledge_graph.db"),
        "faiss_dir": rendered(epoch_root / "faiss"),
        "faiss_index_path": rendered(epoch_root / "faiss" / "text" / "faiss_text.index"),
        "faiss_clip_path": rendered(epoch_root / "faiss" / "clip" / "faiss_clip.index"),
        "faiss_dino_path": rendered(epoch_root / "faiss" / "dino" / "faiss_dino.index"),
        "faiss_audio_path": rendered(epoch_root / "faiss" / f"goodq_audio_{epoch_id}.index"),
        "clip_id_map_db": rendered(epoch_root / "faiss" / "clip" / "clip_id_map.sqlite"),
        "dino_id_map_db": rendered(epoch_root / "faiss" / "dino" / "dino_id_map.sqlite"),
        "clap_id_map_db": rendered(epoch_root / "faiss" / "audio" / "clap_id_map.sqlite"),
        "import_inbox": rendered(data_root / "import_inbox"),
        "processing": rendered(epoch_root / "processing"),
        "processed": rendered(data_root / "processed"),
        "failed": rendered(data_root / "failed"),
        "models_cache": rendered(outer_root / "models"),
        "qdrant_storage": rendered(outer_root / "qdrant_storage"),
        "watchdog_state_file": rendered(epoch_root / "logs" / "watchdog_state.json"),
        "watchdog_lock_file": rendered(epoch_root / "logs" / "watchdog.lock"),
        "nas_path": rendered(data_root / "archive"),
    }
    return {
        "host": {"data_root": rendered(outer_root), "profile": "BASELINE"},
        "paths": paths,
        "qdrant": {
            "enabled": True,
            "host": "http://127.0.0.1:6333",
            "collections": collections,
        },
        "phase6": {
            "clip_collection": collections["clip"],
            "dino_collection": collections["dino"],
        },
    }


def _projection(outer_root: Path) -> ResolvedPlanConfiguration:
    return resolve_plan_configuration(_config(outer_root), requested_epoch_id=EPOCH_ID)


def _clone_projection(
    source: ResolvedPlanConfiguration,
    mutate,
) -> ResolvedPlanConfiguration:
    payload = json.loads(source._projection_json)
    mutate(payload)
    projection_json = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    clone = object.__new__(ResolvedPlanConfiguration)
    object.__setattr__(clone, "_projection_json", projection_json)
    object.__setattr__(
        clone,
        "configuration_scope_sha256",
        hashlib.sha256(projection_json.encode("utf-8")).hexdigest(),
    )
    return clone


def test_public_api_schema_and_error_contract_are_exact() -> None:
    module = importlib.import_module("cli.clean_memory_qdrant")

    assert module.__all__ == (
        "QDRANT_OBSERVATION_SCHEMA",
        "QdrantObservationError",
        "QdrantObservation",
        "observe_qdrant",
    )
    assert (
        module.QDRANT_OBSERVATION_SCHEMA
        == "goodq.clean-memory-qdrant-observation.v1"
    )

    # Test error code constraints and immutability
    err = module.QdrantObservationError("invalid_configuration")
    assert err.code == "invalid_configuration"
    with pytest.raises(AttributeError):
        err.code = "something_else"

    with pytest.raises(ValueError):
        module.QdrantObservationError("unknown_error_code")


def test_invalid_configuration_rejection(tmp_path: Path) -> None:
    module = importlib.import_module("cli.clean_memory_qdrant")

    # Reject non-configuration objects
    with pytest.raises(module.QdrantObservationError) as exc_info:
        module.observe_qdrant("not a configuration object")
    assert exc_info.value.code == "invalid_configuration"

    config = _projection(tmp_path)

    # Reject tampered configurations (digest mismatch)
    bad_config = _clone_projection(config, lambda p: p.update({"path_flavor": "tampered"}))
    # Break the digest matching
    object.__setattr__(bad_config, "configuration_scope_sha256", "a" * 64)
    with pytest.raises(module.QdrantObservationError) as exc_info:
        module.observe_qdrant(bad_config)
    assert exc_info.value.code == "invalid_configuration"


def test_observe_qdrant_unreachable(tmp_path: Path) -> None:
    module = importlib.import_module("cli.clean_memory_qdrant")
    config = _projection(tmp_path)

    # Simulate connection timeout/refusal in urllib
    with patch("urllib.request.build_opener") as mock_build:
        mock_opener = MagicMock()
        mock_opener.open.side_effect = urllib.error.URLError("Connection refused")
        mock_build.return_value = mock_opener

        observation = module.observe_qdrant(config)
        assert observation.schema == "goodq.clean-memory-qdrant-observation.v1"
        assert observation.configuration_scope_sha256 == config.configuration_scope_sha256
        assert observation.qdrant_endpoint == "http://127.0.0.1:6333"
        assert len(observation.qdrant_collections) == 4

        for item in observation.qdrant_collections:
            assert isinstance(item, QdrantCollectionEvidence)
            assert item.exists is False
            assert item.configuration_json is None
            assert item.point_count is None
            assert item.fingerprint_kind is None
            assert item.fingerprint_value is None


def test_observe_qdrant_success(tmp_path: Path) -> None:
    module = importlib.import_module("cli.clean_memory_qdrant")
    config = _projection(tmp_path)

    mock_collection_data = {
        "result": {
            "status": "green",
            "points_count": 5,
            "config": {
                "params": {
                    "vectors": {"size": 768, "distance": "Cosine"}
                }
            }
        }
    }

    mock_scroll_data = {
        "result": {
            "points": [
                {"id": 1, "payload": {"epoch_id": EPOCH_ID, "data": "a"}},
                {"id": 2, "payload": {"epoch_id": EPOCH_ID, "data": "b"}},
            ],
            "next_page_offset": None
        }
    }

    def mock_open(request, timeout=None):
        url = request.full_url
        response = MagicMock()
        response.status = 200
        response.__enter__.return_value = response

        if url.endswith("/points/scroll"):
            payload = json.dumps(mock_scroll_data).encode("utf-8")
        else:
            payload = json.dumps(mock_collection_data).encode("utf-8")

        response.read.return_value = payload
        return response

    with patch("urllib.request.build_opener") as mock_build:
        mock_opener = MagicMock()
        mock_opener.open.side_effect = mock_open
        mock_build.return_value = mock_opener

        observation = module.observe_qdrant(config)
        assert observation.schema == "goodq.clean-memory-qdrant-observation.v1"
        assert len(observation.qdrant_collections) == 4

        for item in observation.qdrant_collections:
            assert item.exists is True
            assert item.point_count == 5
            assert item.fingerprint_kind == "point_state_sha256"
            assert isinstance(item.fingerprint_value, str)
            assert len(item.fingerprint_value) == 64
            # Config is parsed as config params dict
            cfg = json.loads(item.configuration_json)
            assert cfg["params"]["vectors"]["size"] == 768


def test_observe_qdrant_partial_existence(tmp_path: Path) -> None:
    module = importlib.import_module("cli.clean_memory_qdrant")
    config = _projection(tmp_path)

    mock_collection_data = {
        "result": {
            "status": "green",
            "points_count": 0,
            "config": {"params": {"vectors": {"size": 768, "distance": "Cosine"}}}
        }
    }
    mock_scroll_data = {"result": {"points": [], "next_page_offset": None}}

    def mock_open(request, timeout=None):
        url = request.full_url
        if "goodq_text_" in url:
            # text collection exists
            response = MagicMock()
            response.status = 200
            response.__enter__.return_value = response
            if url.endswith("/points/scroll"):
                payload = json.dumps(mock_scroll_data).encode("utf-8")
            else:
                payload = json.dumps(mock_collection_data).encode("utf-8")
            response.read.return_value = payload
            return response
        else:
            # other collections are missing (404)
            fp = MagicMock()
            fp.read.return_value = b'{"status":{"error":"Not Found"}}'
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, fp)

    with patch("urllib.request.build_opener") as mock_build:
        mock_opener = MagicMock()
        mock_opener.open.side_effect = mock_open
        mock_build.return_value = mock_opener

        observation = module.observe_qdrant(config)
        assert len(observation.qdrant_collections) == 4

        text_col = [c for c in observation.qdrant_collections if c.role == "text"][0]
        assert text_col.exists is True
        assert text_col.point_count == 0

        clip_col = [c for c in observation.qdrant_collections if c.role == "clip"][0]
        assert clip_col.exists is False
        assert clip_col.point_count is None


def test_observe_qdrant_import_purity() -> None:
    # Ensure importing doesn't import qdrant_client
    if "qdrant_client" in sys.modules:
        sys.modules.pop("qdrant_client")
    
    importlib.import_module("cli.clean_memory_qdrant")
    assert "qdrant_client" not in sys.modules


def test_observe_qdrant_scroll_pagination(tmp_path: Path) -> None:
    module = importlib.import_module("cli.clean_memory_qdrant")
    config = _projection(tmp_path)

    mock_collection_data = {
        "result": {
            "status": "green",
            "points_count": 3,
            "config": {"params": {"vectors": {"size": 768, "distance": "Cosine"}}}
        }
    }

    # First scroll returns point 1 and 2 with offset "token-1"
    mock_scroll_page_1 = {
        "result": {
            "points": [
                {"id": 1, "payload": {"data": "a"}},
                {"id": 2, "payload": {"data": "b"}},
            ],
            "next_page_offset": "token-1"
        }
    }

    # Second scroll returns point 3 and offset None
    mock_scroll_page_2 = {
        "result": {
            "points": [
                {"id": 3, "payload": {"data": "c"}},
            ],
            "next_page_offset": None
        }
    }

    scroll_calls = 0

    def mock_open(request, timeout=None):
        nonlocal scroll_calls
        url = request.full_url
        response = MagicMock()
        response.status = 200
        response.__enter__.return_value = response

        if url.endswith("/points/scroll"):
            if scroll_calls == 0:
                payload = json.dumps(mock_scroll_page_1).encode("utf-8")
                scroll_calls += 1
            else:
                payload = json.dumps(mock_scroll_page_2).encode("utf-8")
        else:
            payload = json.dumps(mock_collection_data).encode("utf-8")

        response.read.return_value = payload
        return response

    with patch("urllib.request.build_opener") as mock_build:
        mock_opener = MagicMock()
        mock_opener.open.side_effect = mock_open
        mock_build.return_value = mock_opener

        observation = module.observe_qdrant(config)
        assert len(observation.qdrant_collections) == 4

        # For text collection, we expect 3 points retrieved (from pagination)
        text_col = [c for c in observation.qdrant_collections if c.role == "text"][0]
        assert text_col.exists is True
        assert text_col.point_count == 3
        assert text_col.fingerprint_kind == "point_state_sha256"
        assert len(text_col.fingerprint_value) == 64

