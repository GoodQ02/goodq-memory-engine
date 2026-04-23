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
    spec = importlib.util.spec_from_file_location("tests.api_main_legacy_prune_truth", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_api_prunes_legacy_compatibility_endpoints() -> None:
    api_main = _load_api_main()

    paths = {route.path for route in api_main.app.routes}

    retired_paths = {
        "/search",
        "/vector_search",
        "/api/scenes",
        "/api/knowledge_graph",
        "/api/recent-activity",
        "/api/entities",
        "/api/entities/{entity_id}/relationships",
        "/api/analytics/knowledge-graph",
        "/api/analytics/timeline",
        "/api/analytics/emotions",
        "/api/analytics/embeddings",
        "/api/analytics/{tab_name}",
        "/api/pipeline-engines",
        "/api/command-center",
        "/api/processes",
        "/api/processes/{name}/{action}",
        "/api/test-audio",
        "/api/logs/watchdog",
        "/api/processing/stats",
        "/api/progress",
        "/api/scene/{scene_id}",
        "/api/chat/control-agent",
    }

    assert retired_paths.isdisjoint(paths)

    surviving_paths = {
        "/",
        "/api",
        "/api/status",
        "/api/health/summary",
        "/api/engines",
        "/api/queue",
        "/api/gpu/stats",
        "/api/wsl2-status",
        "/api/models",
        "/api/runs/latest/preview",
        "/api/memory/stats",
        "/api/read/envelope",
    }

    assert surviving_paths.issubset(paths)


def test_api_root_only_advertises_truthful_supported_surfaces() -> None:
    api_main = _load_api_main()

    result = api_main.api_root()

    assert result["status"] == "ok"
    assert result["endpoints"] == [
        "/docs",
        "/openapi.json",
        "/api/status",
        "/api/engines",
        "/api/queue",
        "/api/search/multimodal",
        "/api/ingest/submit",
        "/api/videos/{video_id}/scenes",
        "/api/system/status",
    ]
