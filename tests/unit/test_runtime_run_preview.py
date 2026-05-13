from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

from fastapi import APIRouter


def _load_api_main_module(repo_root: Path):
    module_path = repo_root / "api" / "main.py"
    spec = importlib.util.spec_from_file_location("tests.public_runtime_run_preview", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_latest_run_preview_uses_read_only_summary_projection(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    fake_config_loader = types.ModuleType("steps.common.config_loader")
    fake_config_loader.load_configs = lambda overrides=None: {
        "paths": {"data_root": "data", "db_path": "data/memory.db"},
        "host": {},
        "memory": {},
        "llm": {},
        "api": {},
    }
    monkeypatch.setitem(sys.modules, "steps.common.config_loader", fake_config_loader)

    fake_memory_manager = types.ModuleType("steps.common.memory_manager")
    fake_memory_manager.build_memory_router = lambda cfg: object()
    monkeypatch.setitem(sys.modules, "steps.common.memory_manager", fake_memory_manager)

    fake_llm_factory = types.ModuleType("steps.common.llm_model_factory")
    fake_llm_factory.build_llm_models = lambda *args, **kwargs: {}
    monkeypatch.setitem(sys.modules, "steps.common.llm_model_factory", fake_llm_factory)

    fake_llm_client = types.ModuleType("lib.llm_client")
    fake_llm_client.LLMClient = object
    monkeypatch.setitem(sys.modules, "lib.llm_client", fake_llm_client)

    fake_goodq_version = types.ModuleType("goodq_version")
    fake_goodq_version.GOODQ_VERSION = "test"
    monkeypatch.setitem(sys.modules, "goodq_version", fake_goodq_version)

    fake_routes_pkg = types.ModuleType("api.routes")
    for name in ("media", "scenes", "search", "system", "timeline"):
        route_mod = types.ModuleType(f"api.routes.{name}")
        route_mod.router = APIRouter()
        setattr(fake_routes_pkg, name, route_mod)
        monkeypatch.setitem(sys.modules, f"api.routes.{name}", route_mod)
    monkeypatch.setitem(sys.modules, "api.routes", fake_routes_pkg)

    api_main = _load_api_main_module(repo_root)

    monkeypatch.setattr(
        api_main.run_index,
        "list_runs",
        lambda reports_root=None, limit=None: [
            {
                "run_id": "20260424_182406_season2_fresh_witness",
                "status": "running",
                "epoch": "epoch_2026_04_24_season2_witness",
                "run_root": "reports/fresh_ingest_runs/20260424_182406_season2_fresh_witness",
            }
        ],
    )
    monkeypatch.setattr(
        api_main.run_summary,
        "load_run_summary",
        lambda run_root, reports_root=None: {
            "run_header": {
                "run_id": "20260424_182406_season2_fresh_witness",
                "status": "running",
                "epoch": "epoch_2026_04_24_season2_witness",
                "source_dir": "samples\\ingestion\\Sein_Experiment",
                "start_time": "2026-04-24T23:24:06+00:00",
                "end_time": "unknown",
                "total_duration_seconds": "unknown",
                "trigger_source": "watchdog",
            },
            "file_job_overview": {
                "episodes_total": 12,
                "episodes_completed": 5,
                "episodes_failed": 0,
                "episodes_running": 1,
                "episodes_pending": 6,
                "scenes_processed": 195,
            },
            "outcome_classification": {"status": "running"},
            "latest_episode": {
                "episode": "02x06 - The Statue.mp4",
                "status": "running",
            },
        },
    )

    preview = api_main._latest_run_preview()

    assert preview["available"] is True
    assert preview["run_id"] == "20260424_182406_season2_fresh_witness"
    assert preview["status"] == "running"
    assert preview["episodes_total"] == 12
    assert preview["episodes_completed"] == 5
    assert preview["latest_episode"]["episode"] == "02x06 - The Statue.mp4"
