from __future__ import annotations

import importlib.util
import subprocess
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


def test_wsl_status_probes_configured_audio_worker(tmp_path: Path, monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    db_path = tmp_path / "memory.db"

    runtime = _load_runtime_route_module(repo_root, monkeypatch, db_path)
    runtime._WSL_DISTRO = "Ubuntu-22.04"
    runtime._WSL_WORKSPACE = "/home/goodq/goodq_audio"

    monkeypatch.setattr("shutil.which", lambda name: "wsl.exe" if name == "wsl" else None)

    def _completed(args: list[str], stdout: str = "", returncode: int = 0):
        return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr="")

    def _fake_run(args, *, capture_output, text, timeout):
        if args == ["wsl", "--status"]:
            return _completed(args, "Default Distribution: Ubuntu-22.04\n")
        if args == ["wsl", "-l", "-v"]:
            return _completed(args, "Ubuntu-22.04 Running 2\n")
        if args == ["wsl", "-d", "Ubuntu-22.04", "--", "systemctl", "is-active", "vllm-llama1b.service"]:
            return _completed(args, "active\n")
        if args[:5] == ["wsl", "-d", "Ubuntu-22.04", "--", "bash"]:
            script = args[-1]
            if "faster_whisper" in script:
                assert "source /home/goodq/goodq_audio/setup_cuda_env.sh" in script
                return _completed(args, "ok:1.2.1\n")
            if "--query-gpu=name" in script:
                return _completed(args, "NVIDIA RTX Test, 16384, 1024, 999.00\n")
            if "CUDA Version" in script:
                return _completed(args, "13.2\n")
        raise AssertionError(f"unexpected subprocess call: {args!r}")

    monkeypatch.setattr(runtime.subprocess, "run", _fake_run)

    status = runtime._collect_wsl_status()

    assert status["audio_probe"] == "configured_worker"
    assert status["audio_processing"] == "available"
    assert status["faster_whisper"] == "ready"
    assert status["faster_whisper_version"] == "1.2.1"
    assert status["cuda_version"] == "13.2"
