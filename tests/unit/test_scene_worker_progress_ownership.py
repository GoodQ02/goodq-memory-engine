"""Real worker dispatch and status projection, with detector compute replayed."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import types

import pytest

from tests.unit.test_runtime_status import _load_runtime_route_module


WORKER = r'''
import json, sys, time, types
from pathlib import Path
root = Path(sys.argv[1])
case = sys.argv[2]
gpu = types.ModuleType("common.gpu_manager")
gpu.initialize_gpu_for_step = lambda **kw: None
sys.modules["common.gpu_manager"] = gpu
from steps.video_scene_detect import step
cached = json.loads((root / "cached.json").read_text(encoding="utf-8"))
def replay(*args):
    (root / "entered").write_text("detector compute replaced by cached result", encoding="utf-8")
    deadline = time.monotonic() + 60
    while not (root / "release").exists():
        if time.monotonic() > deadline:
            raise RuntimeError("parent did not release replay")
        time.sleep(0.02)
    if case == "error":
        raise RuntimeError("injected detector failure")
    return {"scenes": [] if case == "fallback" else cached["scenes"], "duration": cached["duration"]}
step._detect_with_scenedetect = replay
step._probe_video_duration = lambda path: cached["duration"]
from cli import step_runner
sys.argv = ["step_runner", "--step", "video_scene_detect", "--in", str(root / "item.json"),
            "--out", str(root / "output.json"), "--cfg", str(root / "config.json")]
step_runner.main()
'''


@pytest.mark.parametrize("case,owned", [("ok", True), ("error", True), ("fallback", True), ("ok", False)])
def test_scene_worker_preserves_pipeline_progress(tmp_path, monkeypatch, case, owned):
    repo = Path(__file__).resolve().parents[2]
    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("GOODQ_LOGS_ROOT", str(logs))
    monkeypatch.setenv("GOODQ_TEMP_ROOT", str(tmp_path / "temp"))
    monkeypatch.delenv("GOODQ_WITNESS_CONFIG", raising=False)
    # Avoid resolving workstation paths when importing the parent tracker.
    monkeypatch.setitem(sys.modules, "configs.paths", types.SimpleNamespace(LOGS_DIR=logs))
    from steps.common.progress_tracker import get_tracker

    tracker = get_tracker()
    monkeypatch.setattr(tracker, "progress_file", logs / "progress.json")
    monkeypatch.setattr(tracker, "current_state", copy.deepcopy(tracker.current_state))
    source = tmp_path / "video.mp4"
    source.write_bytes(b"No video decoding is permitted in this test.")
    scenes = [{"start": 0.0, "end": 32.532}, {"start": 32.532, "end": 108.041},
              {"start": 108.041, "end": 146.513}, {"start": 146.513, "end": 179.98}]
    # A local verification run can reuse a completed manifest without ingestion.
    retained = os.environ.get("GOODQ_PROGRESS_REPLAY_MANIFEST")
    if retained:
        manifest = json.loads(Path(retained).read_text(encoding="utf-8"))
        scenes = [{"start": s["start"], "end": s["end"]} for s in manifest["scenes"]]
    if owned:
        tracker.start_processing(source.name, total_steps=4, run_id="parent-progress-owner")
        tracker.update_step("Scene Detection", 1, {"scenes_to_detect": "analyzing video"})
    before = tracker.progress_file.read_bytes() if owned else None
    for name, value in {
        "cached.json": {"scenes": scenes, "duration": scenes[-1]["end"]},
        "item.json": {"source_path": str(source)},
        "config.json": {"paths": {"log_dir": str(logs), "db_dir": str(tmp_path / "db"),
                                    "db_path": str(tmp_path / "db/memory.db")}},
    }.items():
        (tmp_path / name).write_text(json.dumps(value), encoding="utf-8")

    runtime = _load_runtime_route_module(repo, monkeypatch, tmp_path / "db/memory.db", log_dir=logs)
    # Independent machine probes are outside this worker/progress test.
    monkeypatch.setattr(runtime, "requests", types.SimpleNamespace(get=lambda *a, **k: types.SimpleNamespace(status_code=503)))
    monkeypatch.setattr(runtime, "subprocess", types.SimpleNamespace(run=lambda *a, **k: types.SimpleNamespace(returncode=1)))
    monkeypatch.setattr(runtime, "_shared_wsl_status", lambda: {"available": False})
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.route_effects import ROUTE_EFFECTS, install_route_effect_authority

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.router.routes.extend(r for r in runtime.router.routes if r.path == "/api/status")
    install_route_effect_authority(app, registry={(m, "/api/status"): ROUTE_EFFECTS[(m, "/api/status")] for m in ("GET", "HEAD")})
    observed = {}
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        def status():
            response = client.get("/api/status")
            assert response.status_code == 200, response.text
            return response.json()["processing"]

        observed["before"] = status()
        with (tmp_path / "worker.log").open("w", encoding="utf-8") as log:
            child = subprocess.Popen([sys.executable, "-B", "-c", WORKER, str(tmp_path), case],
                                     cwd=repo, env=os.environ.copy(), stdout=log, stderr=log,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            try:
                deadline = time.monotonic() + 40
                while not (tmp_path / "entered").exists():
                    assert child.poll() is None, (tmp_path / "worker.log").read_text(encoding="utf-8")
                    assert time.monotonic() < deadline, "worker never reached replay boundary"
                    time.sleep(0.02)
                observed["during"] = status()
                (tmp_path / "release").touch()
                assert child.wait(timeout=30) == 0, (tmp_path / "worker.log").read_text(encoding="utf-8")
                observed["after_worker"] = status()
            finally:
                (tmp_path / "release").touch()
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=10)
        output = json.loads((tmp_path / "output.json").read_text(encoding="utf-8"))
        after = tracker.progress_file.read_bytes() if tracker.progress_file.exists() else None
        observed["receipt_unchanged"] = before == after
        observed["worker_result"] = output
        if owned:
            tracker.finish_processing("failed" if case == "error" else "completed")
            observed["after_owner_finish"] = status()
        (tmp_path / "observations.json").write_text(json.dumps(observed, indent=2), encoding="utf-8")

    assert before == after, "scene worker overwrote the pipeline owner's progress receipt"
    for point in ("during", "after_worker"):
        if not owned:
            assert observed[point]["status"] == "idle"
            assert "cli_progress" not in observed[point]
            continue
        progress = observed[point]["cli_progress"]
        assert progress["active"] is owned
        if owned:
            assert observed[point]["status"] == "processing"
            assert progress["run_id"] == "parent-progress-owner"
            assert progress["current_step"] == "Scene Detection"
            assert progress["progress_percent"] == 25
    if owned:
        terminal = observed["after_owner_finish"]["cli_progress"]
        assert not terminal["active"]
        assert terminal["status"] == ("failed" if case == "error" else "completed")
    if case == "error":
        assert output["scene_meta"]["status"] == "error"
        assert output["scene_meta"]["error"] == "injected detector failure"
        assert "[ERROR] Scene detection failed" in (tmp_path / "worker.log").read_text(encoding="utf-8")
    elif case == "fallback":
        assert output["scene_meta"]["status"] == "fallback_single_scene"
    else:
        assert output["scene_meta"]["status"] == "ok"
        assert output["scenes"] == scenes
    assert not list(tmp_path.rglob("*.db")), "worker replay must not materialize memory"
