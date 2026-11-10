"""Exercise checkpoint recovery through the canonical runner with fake compute."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli import run_ingestion
from scripts.ucf.ucf_ledger import UCFLedgerClient


class _InterruptedAfterCommit(BaseException):
    """Controlled test stop after the real checkpoint writer returns."""


def _runner_fixture(tmp_path, monkeypatch):
    for key in ("GOODQ_REQUIRE_WSL_AUDIO", "GOODQ_REQUIRE_GPU"):
        monkeypatch.setenv(key, "0")
    monkeypatch.setenv("GOODQ_HOST_PROFILE", "BASELINE")
    monkeypatch.delenv("GOODQ_WITNESS_CONFIG", raising=False)
    video = tmp_path / "home-movie.mp4"
    video.write_bytes(b"controlled scene recovery fixture; no media inference")
    epoch = tmp_path / "epoch"
    (epoch / "ucf").mkdir(parents=True)
    ledger = UCFLedgerClient(str(epoch / "ucf/ucf_ledger.db"))
    ledger.init_schema()
    ledger.register_media(run_ingestion._compute_sha256(video), str(video), 60, 30, 320, 240)
    ledger.close()
    processing = tmp_path / "processing"
    cfg = {
        "ingestion_isolation": True,
        "paths": {"data_root": str(tmp_path), "processing": str(processing),
                  "db_dir": str(tmp_path / "epoch"),
                  "db_path": str(tmp_path / "epoch/memory.db"),
                  "log_dir": str(tmp_path / "logs")},
        "phase6": {"enabled": False},
        "knowledge_graph": {"enabled": False},
        "control_agent": {"enabled": False},
    }
    scenes = [
        {"index": 0, "start": 0.0, "end": 20.0, "duration": 20.0},
        {"index": 1, "start": 40.0, "end": 60.0, "duration": 20.0},
    ]
    calls = []

    async def frame(_cfg, _ffmpeg, _video, scene, *_args, **_kwargs):
        calls.append((scene["start"], scene["end"]))
        return {"path": str(tmp_path / "frame.jpg"),
                "data": {"caption": f"Scene starting at {scene['start']}"}}

    async def audio(*_args, **_kwargs):
        return {"path": str(tmp_path / "audio.wav"), "data": {"transcript": "Hello."}}

    monkeypatch.setattr(run_ingestion, "CONTROL_AGENT_AVAILABLE", False)
    monkeypatch.setattr(run_ingestion, "PROGRESS_TRACKING_AVAILABLE", False)
    monkeypatch.setattr(run_ingestion, "resolve_ffmpeg", lambda *_: "fixture-ffmpeg")
    monkeypatch.setattr(run_ingestion, "list_scenes_for_video", lambda *_: {"scenes": []})
    monkeypatch.setattr(run_ingestion, "_detect_scenes", lambda *a, **k: {
        "scenes": list(scenes), "meta": {},
    })
    monkeypatch.setattr(run_ingestion, "_process_frame_async", frame)
    monkeypatch.setattr(run_ingestion, "_process_audio_async", audio)
    monkeypatch.setattr(run_ingestion, "register_scene_bundle", lambda *a, **k: {
        "vector_points_attempted": 0, "qdrant_ok": "not_attempted",
    })

    output = tmp_path / "results.json"

    def run(chunk_size=30.0):
        run_ingestion.run_with_config(
            cfg=cfg, input_file=video, output=output, workspace=tmp_path / "workspace",
            chunk_size=chunk_size, chunk_overlap=0.0, max_videos=1,
        )
        return json.loads(output.read_text(encoding="utf-8"))[0]

    checkpoint = processing / video.stem / "progressive_ingestion_state.json"
    return run, scenes, calls, checkpoint


@pytest.mark.parametrize("change", ["geometry", "bounds_only", "scene_membership", "missing_meta", "unchanged"])
def test_runner_resume_uses_current_windows_without_duplicate_scene_rows(tmp_path, monkeypatch, change):
    run, scenes, calls, checkpoint = _runner_fixture(tmp_path, monkeypatch)
    if change == "missing_meta":
        scenes.insert(1, {"index": 2, "start": 20.0, "end": 30.0, "duration": 10.0})
    real_write = run_ingestion.atomic_write_json

    def interrupt_after_commit(path, payload, *args, **kwargs):
        real_write(path, payload, *args, **kwargs)
        if Path(path) == checkpoint:
            raise _InterruptedAfterCommit

    with monkeypatch.context() as interrupted:
        interrupted.setattr(run_ingestion, "atomic_write_json", interrupt_after_commit)
        with pytest.raises(_InterruptedAfterCommit):
            run()
    state = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert set(state["windows"]) == {"0"}
    assert state["windows"]["0"]["window_status"] == "committed"
    assert sorted(calls) == ([(0.0, 20.0), (20.0, 30.0)] if change == "missing_meta" else [(0.0, 20.0)])
    calls.clear()

    if change == "scene_membership":
        scenes.insert(1, {"index": 2, "start": 20.0, "end": 30.0, "duration": 10.0})
    if change == "missing_meta":
        get_meta = run_ingestion._get_checkpoint_scene_meta

        def unavailable_meta(*args):
            meta = get_meta(*args)
            return {} if meta.get("start") == 20.0 else meta

        monkeypatch.setattr(run_ingestion, "_get_checkpoint_scene_meta", unavailable_meta)
    result = run(chunk_size={"geometry": 60.0, "bounds_only": 40.0}.get(change, 30.0))
    expected_bounds = [(scene["start"], scene["end"]) for scene in scenes]
    actual_bounds = [(scene["start"], scene["end"]) for scene in result["scenes"]]
    assert actual_bounds == expected_bounds
    assert len({scene["scene_id"] for scene in result["scenes"]}) == len(scenes)
    manifest = json.loads((checkpoint.parent / "video/scene_manifest.json").read_text(encoding="utf-8"))
    assert [(scene["start"], scene["end"]) for scene in manifest["scenes"]] == expected_bounds
    assert sorted(calls) == sorted(expected_bounds if change != "unchanged" else [(40.0, 60.0)])
