from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient


_STUBBED_MODULES = [
    "api.routes",
    "api.routes.control_recurrence",
    "api.routes.ingest",
    "api.routes.media",
    "api.routes.meta",
    "api.routes.runtime",
    "api.routes.scenes",
    "api.routes.search",
    "api.routes.summary",
    "api.routes.system",
    "api.routes.timeline",
    "lib.llm_client",
    "steps.common.config_loader",
    "steps.common.llm_model_factory",
    "steps.common.memory_manager",
    "goodq_version",
]


@pytest.fixture(autouse=True)
def _restore_stubbed_modules():
    previous = {name: sys.modules.get(name) for name in _STUBBED_MODULES}
    missing = {name for name, module in previous.items() if module is None}
    yield
    for name in _STUBBED_MODULES:
        if name in missing:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous[name]


def _load_runtime_route_module(repo_root: Path):
    module_path = repo_root / "api" / "routes" / "runtime.py"
    spec = importlib.util.spec_from_file_location("tests.runtime_route_prune_truth", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_meta_route_module(repo_root: Path):
    module_path = repo_root / "api" / "routes" / "meta.py"
    spec = importlib.util.spec_from_file_location("tests.meta_route_prune_truth", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    def _fake_get_runtime_paths(cfg=None, *keys, **kwargs):
        paths = (cfg or {}).get("paths", {}) if isinstance(cfg, dict) else {}
        values = {
            "data_root": "data",
            "db_path": "data/memory.db",
            "knowledge_graph_db": "data/knowledge_graph.db",
            "processing": "data/processing",
            "log_dir": "data/logs",
            "import_inbox": "data/import_inbox",
        }
        values.update(paths)
        for key in keys:
            values.setdefault(key, key)
        return values

    fake_config_loader.get_runtime_paths = _fake_get_runtime_paths
    sys.modules["steps.common.config_loader"] = fake_config_loader

    fake_memory_manager = types.ModuleType("steps.common.memory_manager")
    fake_memory_manager.build_memory_router = lambda cfg: object()
    sys.modules["steps.common.memory_manager"] = fake_memory_manager

    fake_goodq_version = types.ModuleType("goodq_version")
    fake_goodq_version.GOODQ_VERSION = "test"
    sys.modules["goodq_version"] = fake_goodq_version

    runtime_module = _load_runtime_route_module(repo_root)
    meta_module = _load_meta_route_module(repo_root)

    routes_pkg = types.ModuleType("api.routes")
    for name in ["search", "scenes", "timeline", "media", "system", "ingest", "control_recurrence", "summary"]:
        mod = types.ModuleType(f"api.routes.{name}")
        mod.router = APIRouter()
        if name == "search":
            mod.configure_search_from_cfg = lambda cfg: None
        setattr(routes_pkg, name, mod)
        sys.modules[f"api.routes.{name}"] = mod
    setattr(routes_pkg, "meta", meta_module)
    setattr(routes_pkg, "runtime", runtime_module)
    sys.modules["api.routes.meta"] = meta_module
    sys.modules["api.routes.runtime"] = runtime_module
    sys.modules["api.routes"] = routes_pkg

    module_path = repo_root / "api" / "main.py"
    spec = importlib.util.spec_from_file_location("tests.api_main_legacy_prune_truth", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _collect_paths(routes):
    """Recursively collect all endpoint paths from routes.

    Handles both flat (FastAPI <0.137) and tree-structured (FastAPI >=0.137)
    route lists where _IncludedRouter objects wrap sub-routes.
    """
    from fastapi.routing import APIRoute
    from starlette.routing import Mount, Route

    paths = set()
    for route in routes:
        if isinstance(route, (APIRoute, Route)):
            paths.add(route.path)
        elif isinstance(route, Mount):
            paths.add(route.path)
            if hasattr(route, "routes"):
                paths.update(_collect_paths(route.routes))
        elif hasattr(route, "routes"):
            # _IncludedRouter or similar container without .path
            paths.update(_collect_paths(route.routes))
        elif hasattr(route, "path"):
            paths.add(route.path)
    return paths


def test_main_api_prunes_legacy_compatibility_endpoints() -> None:
    api_main = _load_api_main()

    # Collect from both app.routes and app.router.routes for compat
    paths = _collect_paths(api_main.app.routes)
    if hasattr(api_main.app, "router"):
        paths.update(_collect_paths(api_main.app.router.routes))

    # Diagnostic: dump route structure for CI debugging
    def _dump_routes(routes, indent=0):
        for route in routes:
            t = type(route).__name__
            p = getattr(route, "path", "NO_PATH")
            has_sub = hasattr(route, "routes")
            sub_count = len(route.routes) if has_sub else 0
            print(f"{'  ' * indent}{t}: path={p!r} has_routes={has_sub} sub={sub_count}")
            if has_sub:
                _dump_routes(route.routes, indent + 1)
    print(f"\n=== app.routes ({len(list(api_main.app.routes))}) ===")
    _dump_routes(api_main.app.routes)
    if hasattr(api_main.app, "router"):
        print(f"\n=== app.router.routes ({len(list(api_main.app.router.routes))}) ===")
        _dump_routes(api_main.app.router.routes)
    print(f"\nCollected paths ({len(paths)}): {sorted(paths)}")

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
        "/runs",
        "/runs/{run_id}",
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
    client = TestClient(api_main.app)

    result = client.get("/api").json()

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


def test_api_root_is_curated_human_index_not_full_inventory() -> None:
    api_main = _load_api_main()
    client = TestClient(api_main.app)

    result = client.get("/api").json()

    assert "/docs" in result["endpoints"]
    assert "/openapi.json" in result["endpoints"]
    assert "/api/health/summary" not in result["endpoints"]
    assert "/api/read/envelope" not in result["endpoints"]
    assert "/api/gpu/stats" not in result["endpoints"]


def test_main_delegates_runtime_summary_endpoints_to_router_module() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / "api" / "main.py").read_text(encoding="utf-8")

    assert "runtime" in source
    assert "app.include_router(runtime.router)" in source

    direct_runtime_paths = [
        '@app.get("/api/status")',
        '@app.head("/api/status")',
        '@app.get("/api/health/summary")',
        '@app.get("/api/engines")',
        '@app.get("/api/queue")',
        '@app.get("/api/gpu/stats")',
        '@app.get("/api/wsl2-status")',
        '@app.get("/api/models")',
        '@app.get("/api/runs/latest/preview")',
        '@app.get("/api/memory/stats")',
        '@app.get("/api/read/envelope")',
    ]

    for route_marker in direct_runtime_paths:
        assert route_marker not in source


def test_main_mounts_control_recurrence_router_without_inline_execution_paths() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / "api" / "main.py").read_text(encoding="utf-8")
    route_source = (repo_root / "api" / "routes" / "control_recurrence.py").read_text(encoding="utf-8")

    assert "control_recurrence" in source
    assert "app.include_router(control_recurrence.router)" in source
    assert "build_control_recurrence_report" not in route_source
    assert "build_control_recurrence_comparison" not in route_source
    assert "run_ingestion" not in route_source


def test_main_delegates_root_discovery_endpoints_to_meta_router_module() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / "api" / "main.py").read_text(encoding="utf-8")

    assert "meta" in source
    assert "app.include_router(meta.router)" in source
    assert '@app.get("/")' not in source
    assert '@app.get("/api")' not in source


def test_runtime_router_stays_read_only_aggregation_surface() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / "api" / "routes" / "runtime.py").read_text(encoding="utf-8")

    for marker in ('@router.post("', '@router.put("', '@router.delete("', '@router.patch("'):
        assert marker not in source


def test_memory_stats_labels_faiss_audio_count_as_storage_not_current_run_proof() -> None:
    api_main = _load_api_main()
    client = TestClient(api_main.app)

    result = client.get("/api/memory/stats").json()

    semantics = result["audio_vector_semantics"]
    assert semantics["faiss.audio_vectors"] == "faiss_index_count_only_not_current_run_qdrant_proof"
    assert semantics["current_run_success_contract"] == "docs/architecture/AUDIO_VECTOR_PROVENANCE_CONTRACT.md"
    assert "clap_meta.status == ok" in semantics["current_run_success_requires"]


def test_runtime_and_meta_roles_are_stated_explicitly_in_source_and_docs() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    runtime_source = (repo_root / "api" / "routes" / "runtime.py").read_text(encoding="utf-8")
    meta_source = (repo_root / "api" / "routes" / "meta.py").read_text(encoding="utf-8")
    api_reference = (repo_root / "docs" / "reference" / "API.md").read_text(encoding="utf-8")

    assert "read-only aggregation surface" in runtime_source
    assert "curated human index" in meta_source
    assert "read-only aggregation surface" in api_reference
    assert "curated human index" in api_reference
