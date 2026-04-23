from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

from fastapi import APIRouter
from fastapi.testclient import TestClient


def _install_test_stubs(repo_root: Path) -> None:
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

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


def _load_api_main():
    repo_root = Path(__file__).resolve().parents[2]
    _install_test_stubs(repo_root)

    fake_llm_client = types.ModuleType("lib.llm_client")
    fake_llm_client.LLMClient = object
    sys.modules["lib.llm_client"] = fake_llm_client

    fake_model_factory = types.ModuleType("steps.common.llm_model_factory")
    fake_model_factory.build_llm_models = lambda *args, **kwargs: {}
    sys.modules["steps.common.llm_model_factory"] = fake_model_factory

    meta_module = _load_meta_route()

    routes_pkg = types.ModuleType("api.routes")
    for name in ["search", "scenes", "timeline", "media", "system", "run_summary", "run_index", "ingest", "runtime"]:
        mod = types.ModuleType(f"api.routes.{name}")
        mod.router = APIRouter()
        setattr(routes_pkg, name, mod)
        sys.modules[f"api.routes.{name}"] = mod
    setattr(routes_pkg, "meta", meta_module)
    sys.modules["api.routes.meta"] = meta_module
    sys.modules["api.routes"] = routes_pkg

    module_path = repo_root / "api" / "main.py"
    spec = importlib.util.spec_from_file_location("tests.api_main_truth", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_runtime_route():
    repo_root = Path(__file__).resolve().parents[2]
    _install_test_stubs(repo_root)

    module_path = repo_root / "api" / "routes" / "runtime.py"
    spec = importlib.util.spec_from_file_location("tests.runtime_route_truth", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_meta_route():
    repo_root = Path(__file__).resolve().parents[2]
    _install_test_stubs(repo_root)

    module_path = repo_root / "api" / "routes" / "meta.py"
    spec = importlib.util.spec_from_file_location("tests.meta_route_truth", module_path)
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
    runtime_route = _load_runtime_route()

    def _fake_get(url: str, timeout: int = 2):
        if url == "http://localhost:6333/collections":
            return _Response(200, {"result": {"collections": [{"name": "goodq_text"}]}})
        raise RuntimeError(f"unexpected request: {url}")

    monkeypatch.setattr(runtime_route.requests, "get", _fake_get)

    engines = runtime_route._collect_engine_details()

    assert engines["vector_db"]["name"] == "Vector Database"
    assert engines["vector_db"]["status"] == "ready"
    assert "Qdrant" in engines["vector_db"]["description"]
    assert "ChromaDB" not in engines["vector_db"]["description"]


def test_queue_counts_supported_ingest_files_not_video_only(tmp_path: Path) -> None:
    runtime_route = _load_runtime_route()
    import_inbox = tmp_path / "import_inbox"
    processing = tmp_path / "processing"
    processed = tmp_path / "processed"
    failed = tmp_path / "failed"
    for path in (import_inbox, processing, processed, failed):
        path.mkdir(parents=True, exist_ok=True)

    (import_inbox / "sample.wav").write_bytes(b"audio")
    (import_inbox / "ignore.bin").write_bytes(b"ignored")

    runtime_route._IMPORT_INBOX = import_inbox
    runtime_route._PROCESSING_PATH = processing

    queue = runtime_route.get_queue()

    assert queue["inbox"]["count"] == 1
    assert queue["inbox"]["files"][0]["name"] == "sample.wav"


def test_api_root_points_to_canonical_search_surfaces() -> None:
    api_main = _load_api_main()
    client = TestClient(api_main.app)

    result = client.get("/api").json()

    assert result["status"] == "ok"
    assert "/api/search/multimodal" in result["endpoints"]
    assert "/search?q=..." not in result["endpoints"]
