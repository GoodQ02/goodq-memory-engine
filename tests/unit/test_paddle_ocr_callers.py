"""OCR selection and device ownership at the retained production callers."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from common import vram_allocator as vram


@pytest.fixture
def runtime(monkeypatch, tmp_path):
    from cli import run_ingestion as runner
    from configs import python_paths

    monkeypatch.setenv("GOODQ_TEST_VRAM_ALLOCATOR", "1")
    monkeypatch.setattr(vram, "REGISTRY_DIR", tmp_path / "owner")
    monkeypatch.setattr(vram, "REGISTRY_PATH", tmp_path / "owner/claims.json")
    monkeypatch.setattr(vram, "LOCK_PATH", tmp_path / "owner/claims.lock")
    monkeypatch.setattr(vram.VRAMAllocator, "query_gpu_memory", lambda self: (16384, 0))
    monkeypatch.setattr(vram.VRAMAllocator, "start_heartbeat_daemon", lambda *a: None)
    monkeypatch.setattr(vram, "pid_exists", lambda pid: True)
    monkeypatch.setattr(runner, "_base_env", lambda *a: {"GOODQ_HOST_PROFILE": "GPU_ENHANCED"})
    monkeypatch.setattr(runner, "_observer", lambda: None)
    monkeypatch.setattr(runner, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(runner, "resolve_conda", lambda: "missing-conda")
    monkeypatch.setattr(runner.shutil, "which", lambda _: None)
    monkeypatch.setattr(python_paths, "get_env_python", lambda name: Path(sys.executable) if name == "goodq_ocr" else None)
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"image_ocr": {"device": "cuda:0"}}), encoding="utf-8")
    return runner, cfg


def _result():
    return {"ocr_text": "JUL 04 1988", "ocr_meta": {
        "status": "ok", "engine": "paddleocr-3.7-onnxruntime-cuda",
        "model_revision": "recognizer", "detector_revision": "detector",
        "accepted_regions": [{"text": "JUL 04 1988", "bbox": [1, 2, 60, 20],
                              "confidence": 0.83, "confidence_kind": "recognizer_sequence_score"}],
    }}


@pytest.mark.parametrize("caller", ["sync", "async", "standalone"])
@pytest.mark.parametrize("device", ["cpu", "cuda:0"])
def test_selected_runtime_and_metadata_cross_each_caller(runtime, monkeypatch, caller, device):
    runner, cfg = runtime
    config = {"image_ocr": {"device": device}}
    cfg.write_text(json.dumps(config), encoding="utf-8")
    observed = []

    class Process:
        pid = os.getpid()
        returncode = 0

        def __init__(self, cmd):
            assert cmd[0] == sys.executable
            assert "conda" not in cmd
            assert cmd[cmd.index("--step") + 1] == "image_ocr"
            child_cfg = json.loads(Path(cmd[cmd.index("--cfg") + 1]).read_text(encoding="utf-8"))
            assert child_cfg["image_ocr"]["device"] == device
            self.out = Path(cmd[cmd.index("--out") + 1])

        def communicate(self, timeout=None):
            claims = vram.VRAMAllocator()._read_registry()
            assert bool(claims) is (device == "cuda:0")
            if claims:
                assert list(claims.values())[0]["pid"] == self.pid
                assert list(claims.values())[0]["step_name"] == "image_ocr"
            observed.append(claims)
            self.out.write_text(json.dumps(_result()), encoding="utf-8")
            return "", ""

    class AsyncProcess(Process):
        async def communicate(self):
            stdout, stderr = super().communicate()
            return stdout.encode(), stderr.encode()

    monkeypatch.setattr(runner.subprocess, "Popen", lambda cmd, **kwargs: Process(cmd))

    async def launch(*cmd, **kwargs):
        return AsyncProcess(cmd)

    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", launch)
    if caller == "sync":
        result = runner._run_step("obsolete-caption-env", "image_ocr", {}, cfg)
    elif caller == "async":
        envelope = asyncio.run(runner._run_step_async("obsolete-caption-env", "image_ocr", {}, cfg))
        assert envelope["status"] == "ok"
        result = envelope["outputs"]
    else:
        from steps.common.conda_runner import run_conda_step
        result = run_conda_step("obsolete-caption-env", "image_ocr", {}, config)
    assert result == _result()
    assert observed and vram.VRAMAllocator()._read_registry() == {}


@pytest.mark.parametrize("caller", ["sync", "async", "standalone"])
def test_gpu_admission_denial_never_switches_ocr_provider(runtime, monkeypatch, caller):
    runner, cfg = runtime
    monkeypatch.setattr(vram.VRAMAllocator, "wait_and_reserve", lambda *a, **k: False)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: pytest.fail("unadmitted worker launched"))
    if caller == "async":
        result = asyncio.run(runner._run_step_async("goodq_ocr", "image_ocr", {}, cfg))
        assert result["status"] == "error" and "VRAM allocation failed" in result["errors"]
    elif caller == "standalone":
        from steps.common.conda_runner import StepExecutionError, run_conda_step
        with pytest.raises(StepExecutionError, match="VRAM allocation failed"):
            run_conda_step("goodq_ocr", "image_ocr", {}, {"image_ocr": {"device": "cuda:0"}})
    else:
        with pytest.raises(RuntimeError, match="VRAM allocation failed"):
            runner._run_step("goodq_ocr", "image_ocr", {}, cfg)
    assert vram.VRAMAllocator()._read_registry() == {}


def test_missing_environment_releases_reservation(runtime, monkeypatch):
    from configs import python_paths
    runner, cfg = runtime
    monkeypatch.setattr(python_paths, "get_env_python", lambda _: None)
    with pytest.raises(RuntimeError, match="goodq_ocr is unavailable"):
        runner._run_step("goodq_ocr", "image_ocr", {}, cfg)
    assert vram.VRAMAllocator()._read_registry() == {}


def test_selected_cuda_requires_measurable_gpu_even_with_legacy_bypass(runtime, monkeypatch):
    runner, cfg = runtime
    monkeypatch.setattr(runner, "_base_env", lambda *a: {"GOODQ_BYPASS_VRAM_LIMITS": "1"})
    monkeypatch.setattr(vram.VRAMAllocator, "query_gpu_memory", lambda _: (0, 0))
    with pytest.raises(RuntimeError, match="GPU memory is unavailable"):
        runner._run_step("goodq_ocr", "image_ocr", {}, cfg)
    assert vram.VRAMAllocator()._read_registry() == {}


def test_async_cancellation_reaps_worker_before_releasing_device(runtime, monkeypatch):
    runner, cfg = runtime
    events = []

    async def witness():
        started = asyncio.Event()
        stopped = asyncio.Event()

        class Process:
            pid = os.getpid()
            returncode = None

            async def communicate(self):
                started.set()
                await stopped.wait()
                events.append("reaped")
                assert vram.VRAMAllocator()._read_registry()
                return b"", b""

            def kill(self):
                assert vram.VRAMAllocator()._read_registry()
                events.append("killed")
                self.returncode = -9
                stopped.set()

            terminate = kill

            async def wait(self):
                await stopped.wait()
                return self.returncode

        async def launch(*args, **kwargs):
            return Process()

        monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", launch)
        pending = asyncio.create_task(runner._run_step_async("goodq_ocr", "image_ocr", {}, cfg))
        await asyncio.wait_for(started.wait(), timeout=10)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending

    asyncio.run(witness())
    assert events == ["killed", "reaped"]
    assert vram.VRAMAllocator()._read_registry() == {}


def test_sync_interruption_reaps_worker_before_releasing_device(runtime, monkeypatch):
    runner, cfg = runtime
    events = []

    class Process:
        pid = os.getpid()
        returncode = None

        def communicate(self, timeout=None):
            assert vram.VRAMAllocator()._read_registry()
            if self.returncode is None:
                raise KeyboardInterrupt()
            events.append("reaped")
            return "", ""

        def kill(self):
            assert vram.VRAMAllocator()._read_registry()
            events.append("killed")
            self.returncode = -9

    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: Process())
    with pytest.raises(KeyboardInterrupt):
        runner._run_step("goodq_ocr", "image_ocr", {}, cfg)
    assert events == ["killed", "reaped"]
    assert vram.VRAMAllocator()._read_registry() == {}


def test_aggregation_keeps_native_scores_and_dates_from_each_frame():
    from cli.run_ingestion import _aggregate_ocr_sample_results
    samples = []
    for timestamp, date in [(1.0, "1988-07-04"), (2.0, "1988-07-05")]:
        outputs = _result()
        outputs["time_hints"] = {"explicit_dates": [date], "months": ["july"]}
        samples.append({"timestamp": timestamp, "status": "ok", "outputs": outputs})
    result = _aggregate_ocr_sample_results(samples, 1.0)
    assert result["time_hints"] == {"explicit_dates": ["1988-07-04", "1988-07-05"], "months": ["july"]}
    assert result["ocr_meta"]["observations"][1]["accepted_regions"] == _result()["ocr_meta"]["accepted_regions"]
    assert result["ocr_meta"]["observations"][1]["timestamp"] == 2.0


def test_historical_engine_remains_historical_and_absence_is_not_relabelled():
    from cli.run_ingestion import _aggregate_ocr_sample_results
    old = {"ocr_text": "ARCHIVE", "ocr_meta": {"status": "ok", "engine": "tesseract", "confidence": 95}}
    result = _aggregate_ocr_sample_results([{"status": "ok", "outputs": old}], 0.0)
    assert result["ocr_meta"]["engine"] == "tesseract" and result["ocr_meta"]["confidence"] == 95
    assert "engine" not in _aggregate_ocr_sample_results([], 0.0)["ocr_meta"]


@pytest.mark.parametrize("changed_key", ["engine", "model_revision", "detector_revision", "config_sha256"])
def test_aggregation_rejects_mixed_model_or_config_identities(changed_key):
    from cli.run_ingestion import _aggregate_ocr_sample_results
    one, two = _result(), _result()
    two["ocr_meta"][changed_key] = "changed"
    with pytest.raises(ValueError, match="different model/configuration"):
        _aggregate_ocr_sample_results([
            {"timestamp": 1.0, "status": "ok", "outputs": one},
            {"timestamp": 2.0, "status": "ok", "outputs": two},
        ], 1.0)


@pytest.mark.parametrize("status", ["dependency_missing", "no_source_path", "unavailable"])
def test_selected_ocr_runtime_absence_is_an_error_not_empty_content(status):
    from cli.step_runner import _derive_step_log_outcome
    outcome, error, _ = _derive_step_log_outcome("image_ocr", {
        "ocr_text": None, "ocr_meta": {"status": status, "reason": "required_runtime_missing"},
    }, verbose=False)
    assert outcome == "error" and error == "required_runtime_missing"


def test_cuda_selection_conflicting_with_cpu_profile_fails_before_launch(runtime, monkeypatch):
    runner, cfg = runtime
    monkeypatch.setattr(runner, "_base_env", lambda *a: {"GOODQ_HOST_PROFILE": "BASELINE"})
    with pytest.raises(RuntimeError, match="conflicts with host CPU policy"):
        runner._run_step("goodq_ocr", "image_ocr", {}, cfg)
    assert vram.VRAMAllocator()._read_registry() == {}


def test_sync_cancellation_during_admission_releases_late_claim(runtime, monkeypatch):
    runner, cfg = runtime

    def grant_then_interrupt(self, **kwargs):
        kwargs.pop("timeout_seconds")
        assert self.reserve(**kwargs)
        raise KeyboardInterrupt()

    monkeypatch.setattr(vram.VRAMAllocator, "wait_and_reserve", grant_then_interrupt)
    with pytest.raises(KeyboardInterrupt):
        runner._run_step("goodq_ocr", "image_ocr", {}, cfg)
    assert vram.VRAMAllocator()._read_registry() == {}


def test_aggregation_keeps_earliest_finite_date_support_offset():
    from cli.run_ingestion import _aggregate_ocr_sample_results
    samples = []
    for timestamp, dates in [(5.0, {"1988-07-04": 5.0}),
                             (2.0, {"1988-07-04": 2.0, "1988-07-05": 2.0}),
                             (8.0, {"1988-07-04": 8.0, "invalid": float("nan")})]:
        outputs = _result()
        outputs["time_hints"] = {"explicit_dates": ["1988-07-04"], "first_seen_ts": dates}
        samples.append({"timestamp": timestamp, "status": "ok", "outputs": outputs})
    result = _aggregate_ocr_sample_results(samples, 5.0)
    assert result["time_hints"]["first_seen_ts"] == {"1988-07-04": 2.0, "1988-07-05": 2.0}


def test_aggregation_rejects_different_model_even_when_that_sample_has_no_text():
    from cli.run_ingestion import _aggregate_ocr_sample_results
    empty = _result()
    empty["ocr_text"] = None
    empty["ocr_meta"].update(status="no_text", model_revision="different-model")
    with pytest.raises(ValueError, match="different model/configuration"):
        _aggregate_ocr_sample_results([
            {"timestamp": 1.0, "status": "ok", "outputs": empty},
            {"timestamp": 2.0, "status": "ok", "outputs": _result()},
        ], 1.0)


def test_paddle_ucf_uses_declared_native_score_mean_without_changing_region_scores(tmp_path):
    import sqlite3
    from cli.run_ingestion import _aggregate_ocr_sample_results, _log_visual_to_ucf_ledger
    from scripts.ucf.ucf_ledger import UCFLedgerClient

    db_dir = tmp_path / "db"
    (db_dir / "ucf").mkdir(parents=True)
    ledger = UCFLedgerClient(str(db_dir / "ucf/ucf_ledger.db"))
    ledger.init_schema()
    ledger.register_media("source", "source.mp4", 4.0, 25.0, 100, 100)
    ledger.close()
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"paths": {"db_dir": str(db_dir), "data_root": str(tmp_path)},
                               "run": {"id": "ocr-score-proof"}}), encoding="utf-8")
    frames = tmp_path / "frames"
    frames.mkdir()
    samples = []
    for timestamp, score in [(1.0, 0.8), (2.0, 0.6)]:
        result = _result()
        result["ocr_meta"]["accepted_regions"][0]["confidence"] = score
        samples.append({"status": "ok", "timestamp": timestamp, "outputs": result})
    item = _aggregate_ocr_sample_results(samples, 2.0)
    _log_visual_to_ucf_ledger(cfg, "source", "scene", {"start": 0.0, "duration": 4.0}, frames, item, strict=True)
    with sqlite3.connect(db_dir / "ucf/ucf_ledger.db") as db:
        confidence, payload, raw = db.execute("SELECT confidence,payload,raw_ref FROM context_frames WHERE worker_name='image_ocr'").fetchone()
    assert confidence == pytest.approx(0.7)
    assert json.loads(payload)["confidence_kind"] == "mean_recognizer_sequence_score"
    assert json.loads(payload)["confidence_observation_count"] == 2
    saved = json.loads(Path(raw).read_text(encoding="utf-8"))
    assert [obs["accepted_regions"][0]["confidence"] for obs in saved["observations"]] == [0.8, 0.6]
    item["ocr_observations"][0]["ocr_meta"]["accepted_regions"][0]["confidence"] = None
    with pytest.raises(ValueError, match="requires native region scores"):
        _log_visual_to_ucf_ledger(cfg, "source", "scene", {"start": 0.0, "duration": 4.0}, frames, item, strict=True)


@pytest.mark.parametrize("hook", ["step_start", "begin_heartbeat"])
@pytest.mark.parametrize("reapable", [True, False])
def test_async_ocr_observer_failure_keeps_claim_until_worker_exit(runtime, monkeypatch, hook, reapable):
    runner, cfg = runtime
    events = []

    class Observer:
        def step_start(self, *args, **kwargs):
            if hook == "step_start":
                raise RuntimeError("observer start failed")

        def begin_heartbeat(self, *args, **kwargs):
            raise RuntimeError("observer heartbeat failed")

    class Process:
        pid = os.getpid()
        returncode = None

        def kill(self):
            assert vram.VRAMAllocator()._read_registry()
            events.append("kill_requested")
            if not reapable:
                raise PermissionError("worker could not be stopped")

        async def communicate(self):
            assert vram.VRAMAllocator()._read_registry()
            self.returncode = -9
            events.append("reaped")
            return b"", b""

    async def launch(*args, **kwargs):
        return Process()

    monkeypatch.setattr(runner, "_observer", lambda: Observer())
    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", launch)
    result = asyncio.run(runner._run_step_async("goodq_ocr", "image_ocr", {}, cfg))
    assert result["status"] == "error" and "observer" in result["errors"]
    claims = vram.VRAMAllocator()._read_registry()
    if reapable:
        assert events == ["kill_requested", "reaped"]
        assert claims == {}
    else:
        assert events == ["kill_requested"]
        assert len(claims) == 1
        assert next(iter(claims.values()))["pid"] == Process.pid
