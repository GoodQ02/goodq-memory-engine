"""Reservation durability and worker ownership at the production launch boundary."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from common import vram_allocator as vram
from steps.common import atomic_io
from tests.unit.test_run_ingestion_step_observer_metadata import (
    _RecorderObserver,
    _write_cfg,
)


@pytest.fixture
def allocator(monkeypatch, tmp_path):
    monkeypatch.setattr(vram, "REGISTRY_DIR", tmp_path)
    monkeypatch.setattr(vram, "REGISTRY_PATH", tmp_path / "claims.json")
    monkeypatch.setattr(vram, "LOCK_PATH", tmp_path / "claims.lock")
    monkeypatch.setattr(vram.VRAMAllocator, "query_gpu_memory", lambda self: (10000, 0))
    monkeypatch.setattr(vram.VRAMAllocator, "start_heartbeat_daemon", lambda *a: None)
    monkeypatch.delenv("GOODQ_BYPASS_VRAM_LIMITS", raising=False)
    instance = vram.VRAMAllocator(env={"GOODQ_HOST_PROFILE": "GPU_ENHANCED"})
    instance._write_registry({})
    return instance


def _operation(allocator, operation):
    if operation == "reserve":
        return allocator.reserve("audio_embed_clap", os.getpid(), reservation_id="launch")
    if operation == "update":
        return allocator.update_pid("launch", 424242)
    if operation == "heartbeat":
        return allocator.refresh_heartbeat("launch")
    return allocator.release("launch")


@pytest.mark.skipif(os.name != "nt", reason="native Windows sharing semantics")
@pytest.mark.parametrize("operation", ["reserve", "update", "heartbeat", "release"])
def test_transient_standard_reader_preserves_each_registry_mutation(allocator, operation):
    if operation != "reserve":
        _operation(allocator, "reserve")
    before = allocator._read_registry()
    reader = vram.REGISTRY_PATH.open("r", encoding="utf-8")
    timer = threading.Timer(0.2, reader.close)
    timer.start()
    try:
        result = _operation(allocator, operation)
    finally:
        timer.join()
        reader.close()
    after = allocator._read_registry()
    if operation == "reserve":
        assert result is True and after["launch"]["pid"] == os.getpid()
    elif operation == "update":
        assert after["launch"]["pid"] == 424242
    elif operation == "heartbeat":
        assert after["launch"]["updated_at"] > before["launch"]["updated_at"]
    else:
        assert after == {}
    assert not vram.LOCK_PATH.exists()


@pytest.mark.parametrize("operation", ["reserve", "update", "heartbeat", "release"])
def test_write_failure_is_not_reported_as_success(allocator, monkeypatch, operation):
    if operation != "reserve":
        _operation(allocator, "reserve")
    before = vram.REGISTRY_PATH.read_bytes()

    def denied(*args, **kwargs):
        raise PermissionError("persistent registry denial")

    monkeypatch.setattr(atomic_io, "atomic_write_json", denied)
    monkeypatch.setattr(atomic_io, "atomic_write_json_for_concurrent_readers", denied)
    with pytest.raises(RuntimeError, match="write VRAM registry"):
        _operation(allocator, operation)
    assert vram.REGISTRY_PATH.read_bytes() == before
    assert not vram.LOCK_PATH.exists()


@pytest.mark.skipif(os.name != "nt", reason="native Windows sharing semantics")
def test_persistent_standard_reader_blocks_admission_without_losing_claims(allocator):
    allocator.reserve("audio_embed_clap", os.getpid(), reservation_id="sibling")
    before = vram.REGISTRY_PATH.read_bytes()
    with vram.REGISTRY_PATH.open("r", encoding="utf-8"):
        with pytest.raises(RuntimeError, match="write VRAM registry") as failure:
            _operation(allocator, "reserve")
    assert failure.value.__cause__.winerror in (32, 33)
    assert vram.REGISTRY_PATH.read_bytes() == before
    assert not vram.LOCK_PATH.exists()
    assert _operation(allocator, "reserve") is True
    assert set(allocator._read_registry()) == {"launch", "sibling"}


def test_read_permission_error_does_not_grant_admission(allocator, monkeypatch):
    before = vram.REGISTRY_PATH.read_bytes()

    def denied(*args, **kwargs):
        raise PermissionError("unreadable registry")

    monkeypatch.setattr(atomic_io, "read_text_during_atomic_replace", denied)
    with pytest.raises(RuntimeError, match="read VRAM registry"):
        _operation(allocator, "reserve")
    assert vram.REGISTRY_PATH.read_bytes() == before


@pytest.mark.parametrize("contents", ["{broken", "[]", "null"])
def test_unreadable_registry_cannot_become_empty_admission(allocator, contents):
    vram.REGISTRY_PATH.write_text(contents, encoding="utf-8")
    with pytest.raises(RuntimeError, match="read VRAM registry"):
        _operation(allocator, "reserve")
    assert vram.REGISTRY_PATH.read_text(encoding="utf-8") == contents


def test_concurrent_passive_reads_keep_complete_sibling_claims(allocator):
    _operation(allocator, "reserve")
    allocator.reserve("audio_embed_clap", os.getpid(), reservation_id="sibling")

    def write():
        for _ in range(50):
            allocator.refresh_heartbeat("launch")

    def read():
        for _ in range(150):
            assert set(allocator._read_registry()) == {"launch", "sibling"}

    with ThreadPoolExecutor(max_workers=2) as pool:
        writer = pool.submit(write)
        reader = pool.submit(read)
        writer.result()
        reader.result()
    allocator.release("launch")
    assert set(allocator._read_registry()) == {"sibling"}


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("failure_point", ["reserve", "update", "release", "release_after_worker_error", "release_in_retry"])
def test_production_caller_fails_honestly_and_reaps_worker(
    allocator, monkeypatch, tmp_path, asynchronous, failure_point
):
    from cli import run_ingestion as runner
    import configs.python_paths as python_paths

    cfg = _write_cfg(tmp_path, host={"profile": "GPU_ENHANCED", "require_gpu": True})
    monkeypatch.setenv("GOODQ_TEST_VRAM_ALLOCATOR", "1")
    monkeypatch.setattr(runner, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(runner, "resolve_conda", lambda: "conda")
    monkeypatch.setattr(runner.shutil, "which", lambda _: "conda")
    monkeypatch.setattr(python_paths, "get_env_python", lambda _: sys.executable)
    observer = _RecorderObserver()
    monkeypatch.setattr(runner, "_PIPELINE_OBSERVER", observer)
    before = {}
    workers = []
    write = vram.VRAMAllocator._write_registry

    def fail_at_boundary(self, registry):
        is_failure = (
            (failure_point == "reserve" and registry and not workers)
            or (failure_point == "update" and any(c["pid"] != os.getpid() for c in registry.values()))
            or (failure_point.startswith("release") and workers and not registry)
        )
        if is_failure:
            before.update(self._read_registry())
            # Use the actual writer error handling, not a replacement allocator.
            with monkeypatch.context() as patcher:
                def denied(*a, **kw):
                    raise PermissionError("persistent registry denial")
                patcher.setattr(atomic_io, "atomic_write_json", denied)
                patcher.setattr(atomic_io, "atomic_write_json_for_concurrent_readers", denied)
                return write(self, registry)
        return write(self, registry)

    monkeypatch.setattr(vram.VRAMAllocator, "_write_registry", fail_at_boundary)
    # Real OS children establish that PID-update failure cannot orphan a worker.
    child_code = (
        "import time; time.sleep(30)" if failure_point == "update"
        else 'print(\'{"clap_meta":{"status":"ok"}}\')'
    )
    if failure_point == "release_after_worker_error":
        child_code = "raise SystemExit(7)"
    expected_error = "returncode=7" if failure_point == "release_after_worker_error" else "write VRAM registry"
    popen = runner.subprocess.Popen
    spawn_async = asyncio.create_subprocess_exec

    def spawn(*args, **kwargs):
        child = popen([sys.executable, "-c", child_code], **kwargs)
        workers.append(child)
        return child

    async def spawn_a(*args, **kwargs):
        child = await spawn_async(sys.executable, "-c", child_code, **kwargs)
        workers.append(child)
        return child

    async def run_a():
        try:
            if failure_point == "release_in_retry":
                try:
                    raise ValueError("a previous attempt failed")
                except ValueError:
                    result = await runner._run_step_async("goodq_audio_embed", "audio_embed_clap", {}, cfg)
            else:
                result = await runner._run_step_async("goodq_audio_embed", "audio_embed_clap", {}, cfg)
            assert result["status"] == "error"
            assert expected_error in result["errors"]
            assert all(worker.returncode is not None for worker in workers)
        finally:
            for worker in workers:
                if worker.returncode is None:
                    worker.kill()
                    await worker.communicate()

    if asynchronous:
        monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", spawn_a)
        asyncio.run(run_a())
    else:
        monkeypatch.setattr(runner.subprocess, "Popen", spawn)
        try:
            with pytest.raises(RuntimeError, match=expected_error):
                if failure_point == "release_in_retry":
                    try:
                        raise ValueError("a previous attempt failed")
                    except ValueError:
                        runner._run_step("goodq_audio_embed", "audio_embed_clap", {}, cfg)
                else:
                    runner._run_step("goodq_audio_embed", "audio_embed_clap", {}, cfg)
            assert all(worker.poll() is not None for worker in workers)
        finally:
            for worker in workers:
                if worker.poll() is None:
                    worker.kill()
                    worker.communicate()
    assert len(workers) == (failure_point != "reserve")
    remaining = allocator._read_registry()
    assert remaining == (before if failure_point.startswith("release") else {})
    if failure_point.startswith("release"):
        assert any(event[0] == "step_error" and "vram_release_failed" in event[2] for event in observer.events)
