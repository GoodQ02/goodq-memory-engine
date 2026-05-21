from __future__ import annotations

import importlib.util
import sqlite3
import sys
import types
from pathlib import Path


def _load_runtime_route_module(repo_root: Path, monkeypatch, db_path: Path):
    fake_config_loader = types.ModuleType("steps.common.config_loader")
    fake_config_loader.load_configs = lambda overrides=None: {
        "paths": {"data_root": str(db_path.parent), "db_path": str(db_path)},
        "host": {},
        "memory": {},
        "llm": {},
    }
    monkeypatch.setitem(sys.modules, "steps.common.config_loader", fake_config_loader)

    fake_memory_store = types.ModuleType("steps.common.memory_store")
    fake_memory_store.normalize_memory_tier_list = lambda values: values
    monkeypatch.setitem(sys.modules, "steps.common.memory_store", fake_memory_store)

    fake_ingest_requests = types.ModuleType("api.utils.ingest_requests")
    fake_ingest_requests.is_supported_ingest_path = lambda path: True
    monkeypatch.setitem(sys.modules, "api.utils.ingest_requests", fake_ingest_requests)

    fake_goodq_version = types.ModuleType("goodq_version")
    fake_goodq_version.GOODQ_VERSION = "test"
    monkeypatch.setitem(sys.modules, "goodq_version", fake_goodq_version)

    module_path = repo_root / "api" / "routes" / "runtime.py"
    spec = importlib.util.spec_from_file_location("tests.runtime_status", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_database_status_counts_sqlite_scenes(tmp_path: Path, monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    db_path = tmp_path / "memory.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE scenes (scene_id TEXT)")
        conn.executemany("INSERT INTO scenes (scene_id) VALUES (?)", [("a",), ("b",), ("c",)])

    runtime = _load_runtime_route_module(repo_root, monkeypatch, db_path)

    assert runtime._database_status(db_path) == {"exists": True, "scenes": 3}


def test_database_status_reports_zero_for_missing_database(tmp_path: Path, monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    db_path = tmp_path / "missing.db"

    runtime = _load_runtime_route_module(repo_root, monkeypatch, db_path)

    assert runtime._database_status(db_path) == {"exists": False, "scenes": 0}
