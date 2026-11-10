"""The Watchdog adapter preserves resolved configuration and current-run evidence."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from cli import run_ingestion
from pipelines.direct_ingestion import run_direct_ingestion


def _fixture(tmp_path, monkeypatch):
    import configs.paths

    monkeypatch.setattr(configs.paths, "LOGS_DIR", tmp_path / "ambient-logs")
    video = tmp_path / "selected.mp4"
    video.write_bytes(b"one controlled input; media execution is intercepted")
    cfg = {
        "ingestion_isolation": True,
        "paths": {"processing": str(tmp_path / "requested-processing"),
                  "log_dir": str(tmp_path / "requested-logs")},
        "qdrant": {"host": "http://127.0.0.1:9"},
        "phase6": {"enabled": True},
        "knowledge_graph": {"enabled": False},
    }
    return video, cfg


def test_direct_call_preserves_config_without_reloading_or_mutating_it(tmp_path, monkeypatch):
    video, cfg = _fixture(tmp_path, monkeypatch)
    before = copy.deepcopy(cfg)
    observed = {}

    class ReachedRunnerBoundary(Exception):
        pass

    def unwanted_reload(*args, **kwargs):
        raise AssertionError("resolved caller configuration must not be reloaded")

    def inspect_config(received):
        observed.update(copy.deepcopy(received))
        received["paths"]["processing"] = "changed-only-in-run-copy"
        raise ReachedRunnerBoundary

    monkeypatch.setattr(run_ingestion, "load_configs", unwanted_reload)
    monkeypatch.setattr(run_ingestion, "_initial_knowledge_graph_status", inspect_config)
    with pytest.raises(ReachedRunnerBoundary):
        run_direct_ingestion(video, cfg)
    assert observed["ingestion_isolation"] is True
    assert {key: observed["paths"][key] for key in before["paths"]} == before["paths"]
    assert observed["qdrant"] == before["qdrant"]
    assert cfg == before


def _intercept_runner(monkeypatch, callback):
    monkeypatch.setattr(run_ingestion, "run", callback)
    monkeypatch.setattr(run_ingestion, "run_with_config", callback, raising=False)


def test_direct_call_keeps_watchdog_run_identity_for_receipts(tmp_path, monkeypatch):
    video, cfg = _fixture(tmp_path, monkeypatch)
    cfg["run"] = {"id": "watchdog-requested-run", "pipeline": "watchdog_video_ingest"}
    observed = {}
    monkeypatch.setenv("GOODQ_RUN_ID", "previous-run")

    class ReachedRunnerContext(Exception):
        pass

    def inspect_context(received):
        observed.update(received["run"])
        raise ReachedRunnerContext

    monkeypatch.setattr(run_ingestion, "_resolve_audio_runtime_contract", inspect_context)
    with pytest.raises(ReachedRunnerContext):
        run_direct_ingestion(video, cfg)
    assert observed["id"] == cfg["run"]["id"]


def test_direct_call_rejects_witness_cfg_before_creating_runtime_paths(tmp_path, monkeypatch):
    video, cfg = _fixture(tmp_path, monkeypatch)
    cfg["witness"] = {"ingestion_isolation": True, "artifact_root": str(tmp_path / "witness")}
    before = copy.deepcopy(cfg)

    # Exercise the real adapter and canonical guard; no runner/guard override.
    with pytest.raises(run_ingestion.typer.BadParameter, match="fresh process"):
        run_direct_ingestion(video, cfg)

    assert not Path(cfg["paths"]["processing"]).exists()
    assert not Path(cfg["paths"]["log_dir"]).exists()
    assert cfg == before


@pytest.mark.parametrize("caller", ["cli", "watchdog"])
def test_canonical_governed_intake_reaches_runner_without_witness_admission(tmp_path, monkeypatch, caller):
    from typer.testing import CliRunner
    from cli import watchdog
    from cli import golden_witness
    from steps.common.memory import embedding_persistence_allowed

    video, cfg = _fixture(tmp_path, monkeypatch)
    monkeypatch.delenv("GOODQ_WITNESS_CONFIG", raising=False)
    observed = {}

    class ReachedRunnerBoundary(Exception):
        pass

    def inspect_config(received):
        observed.update(copy.deepcopy(received))
        raise ReachedRunnerBoundary

    def unexpected_admission(*_args, **_kwargs):
        pytest.fail("canonical governed intake must not acquire single-use witness stores")

    monkeypatch.setattr(run_ingestion, "_initial_knowledge_graph_status", inspect_config)
    monkeypatch.setattr(golden_witness, "admit_witness_run", unexpected_admission)
    if caller == "cli":
        monkeypatch.setattr(run_ingestion, "load_configs", lambda _: cfg)
        result = CliRunner().invoke(run_ingestion.APP, [
            "--input-file", str(video), "--output", str(tmp_path / "result.json"),
            "--workspace", cfg["paths"]["processing"],
        ])
        assert isinstance(result.exception, ReachedRunnerBoundary), result.output
    else:
        # Keep the production Watchdog -> adapter -> canonical runner call chain;
        # bypass only background-service construction and error-log persistence.
        from steps.common import progress_tracker
        monkeypatch.setattr(progress_tracker, "add_error", lambda *_: None)
        processor = watchdog.WatchdogProcessor.__new__(watchdog.WatchdogProcessor)
        processor._cfg_base = cfg
        processor.processing_dir = Path(cfg["paths"]["processing"])
        processor.control_agent_status = "disabled"
        processor.control_agent_reason = "test caller boundary"
        with pytest.raises(ReachedRunnerBoundary):
            processor.ingest_video(video, "governed-watchdog-run")
        assert observed["run"]["id"] == "governed-watchdog-run"
    assert observed["ingestion_isolation"] is True
    assert "witness" not in observed
    assert embedding_persistence_allowed(observed) is False


def test_direct_call_uses_explicit_input_and_returned_artifact_paths(tmp_path, monkeypatch):
    video, cfg = _fixture(tmp_path, monkeypatch)
    identity = hashlib.sha256(video.read_bytes()).hexdigest()
    index = Path(cfg["paths"]["processing"]) / video.stem / "temporal_index.json"
    index.parent.mkdir(parents=True)
    index.write_text(json.dumps({"video_hash": identity, "phase6_complete": True}), encoding="utf-8")
    observed = {}

    def no_symlink(*args, **kwargs):
        raise AssertionError("explicit-file ingestion must not depend on symlink permission")

    def runner(**kwargs):
        observed.update(kwargs)
        kwargs["output"].parent.mkdir(parents=True, exist_ok=True)
        kwargs["output"].write_text(json.dumps([{
            "video_path": str(video), "video_id": identity, "video_hash": identity,
            "scenes": [{"scene_id": "scene-0"}], "phase6_complete": True,
            "temporal_index_path": str(index),
        }]), encoding="utf-8")

    monkeypatch.setattr(Path, "symlink_to", no_symlink)
    _intercept_runner(monkeypatch, runner)
    result = run_direct_ingestion(video, cfg)
    assert observed["input_file"] == video.resolve()
    assert observed.get("input_dir") is None
    assert observed["cfg"]["ingestion_isolation"] is True
    assert observed["cfg"]["qdrant"] == cfg["qdrant"]
    assert {key: observed["cfg"]["paths"][key] for key in cfg["paths"]} == cfg["paths"]
    assert observed["output"].is_relative_to(Path(cfg["paths"]["log_dir"]))
    assert result["status"] == "success"
    assert result["video_hash"] == identity
    assert Path(result["processing_dir"]) == index.parent
    assert Path(result["temporal_index_path"]) == index


def test_direct_call_exposes_runner_exit_code_to_watchdog(tmp_path, monkeypatch):
    video, cfg = _fixture(tmp_path, monkeypatch)

    def runner(**kwargs):
        raise run_ingestion.typer.Exit(code=1)

    _intercept_runner(monkeypatch, runner)
    with pytest.raises(RuntimeError, match="direct_ingestion_runner_failed exit_code=1"):
        run_direct_ingestion(video, cfg)


@pytest.mark.parametrize("result_kind", ["missing", "empty", "wrong_content"])
def test_direct_call_rejects_missing_or_unbound_current_result(tmp_path, monkeypatch, result_kind):
    video, cfg = _fixture(tmp_path, monkeypatch)
    # A previous successful output must not make a no-output call successful.
    old_logs = tmp_path / "ambient-logs"
    old_logs.mkdir()
    (old_logs / f"direct_ingest_{video.stem}.json").write_text(
        json.dumps([{"video_id": "stale", "scenes": []}]), encoding="utf-8")

    def runner(**kwargs):
        if result_kind != "missing":
            payload = [] if result_kind == "empty" else [{"video_id": "wrong", "video_hash": "wrong"}]
            kwargs["output"].parent.mkdir(parents=True, exist_ok=True)
            kwargs["output"].write_text(json.dumps(payload), encoding="utf-8")

    _intercept_runner(monkeypatch, runner)
    with pytest.raises(RuntimeError, match="direct_ingestion_result"):
        run_direct_ingestion(video, cfg)
