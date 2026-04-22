from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

from fastapi import APIRouter


def _load_api_main():
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    fake_llm_client = types.ModuleType("lib.llm_client")
    fake_llm_client.LLMClient = object
    sys.modules["lib.llm_client"] = fake_llm_client

    fake_model_factory = types.ModuleType("steps.common.llm_model_factory")
    fake_model_factory.build_llm_models = lambda *args, **kwargs: {}
    sys.modules["steps.common.llm_model_factory"] = fake_model_factory

    fake_config_loader = types.ModuleType("steps.common.config_loader")
    fake_config_loader.load_configs = lambda overrides=None: {
        "qdrant": {"host": "http://127.0.0.1:6333"},
        "paths": {"data_root": "data", "db_path": "data/memory.db"},
        "host": {},
        "api": {},
    }
    sys.modules["steps.common.config_loader"] = fake_config_loader

    fake_memory_manager = types.ModuleType("steps.common.memory_manager")
    fake_memory_manager.build_memory_router = lambda cfg: object()
    sys.modules["steps.common.memory_manager"] = fake_memory_manager

    fake_goodq_version = types.ModuleType("goodq_version")
    fake_goodq_version.GOODQ_VERSION = "test"
    sys.modules["goodq_version"] = fake_goodq_version

    routes_pkg = types.ModuleType("api.routes")
    for name in ["search", "scenes", "timeline", "media", "system", "run_summary", "run_index", "ingest"]:
        mod = types.ModuleType(f"api.routes.{name}")
        mod.router = APIRouter()
        setattr(routes_pkg, name, mod)
        sys.modules[f"api.routes.{name}"] = mod
    sys.modules["api.routes"] = routes_pkg

    module_path = repo_root / "api" / "main.py"
    spec = importlib.util.spec_from_file_location("tests.api_main_truth", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Response:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_collect_engine_details_reports_qdrant_as_vector_db(monkeypatch) -> None:
    api_main = _load_api_main()

    def _fake_get(url: str, timeout: int = 2):
        if url == "http://localhost:6333/collections":
            return _Response(200, {"result": {"collections": [{"name": "goodq_text"}]}})
        raise RuntimeError(f"unexpected request: {url}")

    monkeypatch.setattr(api_main.requests, "get", _fake_get)

    engines = api_main._collect_engine_details()

    assert engines["vector_db"]["name"] == "Vector Database"
    assert engines["vector_db"]["status"] == "ready"
    assert "Qdrant" in engines["vector_db"]["description"]
    assert "ChromaDB" not in engines["vector_db"]["description"]


def test_queue_counts_supported_ingest_files_not_video_only(tmp_path: Path) -> None:
    api_main = _load_api_main()
    import_inbox = tmp_path / "import_inbox"
    processing = tmp_path / "processing"
    processed = tmp_path / "processed"
    failed = tmp_path / "failed"
    for path in (import_inbox, processing, processed, failed):
        path.mkdir(parents=True, exist_ok=True)

    (import_inbox / "sample.wav").write_bytes(b"audio")
    (import_inbox / "ignore.bin").write_bytes(b"ignored")

    api_main._IMPORT_INBOX = import_inbox
    api_main._PROCESSING_PATH = processing

    queue = api_main.get_queue()

    assert queue["inbox"]["count"] == 1
    assert queue["inbox"]["files"][0]["name"] == "sample.wav"


def test_root_search_endpoint_points_to_canonical_search_surfaces() -> None:
    api_main = _load_api_main()

    result = api_main.search("elaine", topk=5)

    assert result["status"] == "disabled"
    assert "deprecated" in result["message"].lower()
    assert "/api/search" in result["message"]
