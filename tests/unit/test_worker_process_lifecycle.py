"""Process ownership regressions through both production worker callers."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.unit.test_run_ingestion_step_observer_metadata import _RecorderObserver, _write_cfg


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    from cli import run_ingestion as runner
    from common import vram_allocator as vram
    from configs import python_paths

    cfg = _write_cfg(tmp_path, host={"profile": "GPU_ENHANCED", "require_gpu": False})
    monkeypatch.setenv("GOODQ_TEST_VRAM_ALLOCATOR", "1")
    monkeypatch.setattr(vram, "REGISTRY_DIR", tmp_path / "owner")
    monkeypatch.setattr(vram, "REGISTRY_PATH", tmp_path / "owner/claims.json")
    monkeypatch.setattr(vram, "LOCK_PATH", tmp_path / "owner/claims.lock")
    monkeypatch.setattr(vram.VRAMAllocator, "query_gpu_memory", lambda self: (16384, 0))
    monkeypatch.setattr(vram.VRAMAllocator, "start_heartbeat_daemon", lambda *a: None)
    monkeypatch.setattr(vram, "step_uses_gpu_backend", lambda *a, **kw: True)
    monkeypatch.setattr(runner, "_CURRENT_RUN_CONTEXT", None)
    monkeypatch.setattr(runner, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(runner, "resolve_conda", lambda: "fixture-conda-unavailable")
    monkeypatch.setattr(runner.shutil, "which", lambda _: None)
    monkeypatch.setattr(python_paths, "get_env_python", lambda _: Path(sys.executable))
    return runner, cfg, vram


@pytest.mark.parametrize("release_fails", [False, True])
def test_sync_admission_interrupt_preserves_interrupt_and_releases_late_claim(runtime, monkeypatch, release_fails):
    runner, cfg, vram = runtime
    reserve = vram.VRAMAllocator.wait_and_reserve

    def interrupted(self, **kwargs):
        assert reserve(self, **kwargs)
        assert self._read_registry()
        raise KeyboardInterrupt("fixture admission interrupted")

    monkeypatch.setattr(vram.VRAMAllocator, "wait_and_reserve", interrupted)
    if release_fails:
        def fail_release(*args):
            raise OSError("fixture release failed")
        monkeypatch.setattr(vram.VRAMAllocator, "release", fail_release)
    with pytest.raises(KeyboardInterrupt, match="fixture admission interrupted"):
        runner._run_step("goodq_audio_embed", "audio_embed_clap", {}, cfg)
    assert bool(vram.VRAMAllocator()._read_registry()) is release_fails


def test_async_admission_cancel_survives_release_failure(runtime, monkeypatch):
    import threading
    runner, cfg, vram = runtime
    admitted, proceed = threading.Event(), threading.Event()
    reserve = vram.VRAMAllocator.wait_and_reserve

    def wait(self, **kwargs):
        assert reserve(self, **kwargs)
        admitted.set()
        assert proceed.wait(5)
        return True

    def fail_release(*args):
        raise OSError("fixture release failed")

    monkeypatch.setattr(vram.VRAMAllocator, "wait_and_reserve", wait)
    monkeypatch.setattr(vram.VRAMAllocator, "release", fail_release)

    async def scenario():
        task = asyncio.create_task(runner._run_step_async("goodq_audio_embed", "audio_embed_clap", {}, cfg))
        try:
            assert await asyncio.to_thread(admitted.wait, 5)
            task.cancel()
            await asyncio.sleep(0)
            proceed.set()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            proceed.set()

    asyncio.run(scenario())
    assert len(vram.VRAMAllocator()._read_registry()) == 1


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("hook", ["step_start", "begin_heartbeat"])
def test_observer_failure_reaps_real_worker_before_releasing_claim(runtime, monkeypatch, mode, hook):
    runner, cfg, vram = runtime
    children, inputs, released_while_alive = [], [], []
    real_release = vram.VRAMAllocator.release
    real_popen = subprocess.Popen
    real_async = asyncio.create_subprocess_exec

    class Observer(_RecorderObserver):
        def step_start(self, *a, **kw):
            if hook == "step_start":
                raise RuntimeError("fixture observer failed")

        def begin_heartbeat(self, *a, **kw):
            raise RuntimeError("fixture observer failed")

    def release(self, claim):
        child = children[-1]
        alive = child.poll() is None if mode == "sync" else child.returncode is None
        released_while_alive.append(alive)
        return real_release(self, claim)

    def args(cmd):
        inputs.append(Path(cmd[cmd.index("--in") + 1]))
        assert vram.VRAMAllocator()._read_registry()
        return [sys.executable, "-c", "import time; time.sleep(60)"]

    def launch(cmd, **kw):
        child = real_popen(args(cmd), **kw)
        children.append(child)
        return child

    async def launch_async(*cmd, **kw):
        child = await real_async(*args(list(cmd)), **kw)
        children.append(child)
        return child

    monkeypatch.setattr(runner, "_observer", lambda: Observer())
    monkeypatch.setattr(vram.VRAMAllocator, "release", release)
    if mode == "sync":
        monkeypatch.setattr(subprocess, "Popen", launch)
        try:
            with pytest.raises(RuntimeError, match="fixture observer failed"):
                runner._run_step("goodq_audio_embed", "audio_embed_clap", {}, cfg)
            assert children[0].poll() is not None, "failed caller left its worker alive"
            assert released_while_alive == [False]
        finally:
            if children and children[0].poll() is None:
                children[0].kill()
            if children:
                children[0].communicate(timeout=5)
    else:
        monkeypatch.setattr(asyncio, "create_subprocess_exec", launch_async)

        async def scenario():
            try:
                result = await runner._run_step_async("goodq_audio_embed", "audio_embed_clap", {}, cfg)
                assert result["status"] == "error" and "fixture observer failed" in result["errors"]
                assert children[0].returncode is not None, "failed caller left its worker alive"
                assert released_while_alive == [False]
            finally:
                if children and children[0].returncode is None:
                    children[0].kill()
                if children:
                    await asyncio.wait_for(children[0].communicate(), 5)

        asyncio.run(scenario())
    assert vram.VRAMAllocator()._read_registry() == {}
    assert not inputs[0].exists()


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_unstoppable_worker_keeps_claim_and_input(runtime, monkeypatch, mode):
    runner, cfg, vram = runtime
    inputs = []

    class Observer(_RecorderObserver):
        def step_start(self, *a, **kw):
            raise RuntimeError("fixture observer failed")

    class Process:
        pid = os.getpid()
        returncode = None

        def kill(self):
            raise PermissionError("fixture child cannot be stopped")

    def launch(cmd, **kw):
        inputs.append(Path(cmd[cmd.index("--in") + 1]))
        return Process()

    async def launch_async(*cmd, **kw):
        return launch(list(cmd), **kw)

    monkeypatch.setattr(runner, "_observer", lambda: Observer())
    if mode == "sync":
        monkeypatch.setattr(subprocess, "Popen", launch)
        with pytest.raises(RuntimeError, match="fixture observer failed"):
            runner._run_step("goodq_audio_embed", "audio_embed_clap", {}, cfg)
    else:
        monkeypatch.setattr(asyncio, "create_subprocess_exec", launch_async)
        result = asyncio.run(runner._run_step_async("goodq_audio_embed", "audio_embed_clap", {}, cfg))
        assert result["status"] == "error" and "fixture observer failed" in result["errors"]
    assert len(vram.VRAMAllocator()._read_registry()) == 1
    assert inputs[0].exists(), "unreaped worker still owns its input"
    inputs[0].unlink()
    inputs[0].parent.rmdir()


@pytest.mark.parametrize("hook", ["heartbeat_stop", "step_error", "release_error"])
def test_async_cancellation_survives_observer_cleanup_failure(runtime, monkeypatch, hook):
    runner, cfg, vram = runtime
    children = []
    ready = asyncio.Event()
    real_async = asyncio.create_subprocess_exec

    class Observer(_RecorderObserver):
        def begin_heartbeat(self, *a, **kw):
            ready.set()

            def stop():
                if hook == "heartbeat_stop":
                    raise RuntimeError("fixture heartbeat stop failed")

            return stop

        def step_error(self, step, *, error, metadata=None):
            if hook == "step_error" or (hook == "release_error" and error.startswith("vram_release_failed")):
                raise RuntimeError("fixture error observer failed")

    async def launch(*cmd, **kw):
        child = await real_async(sys.executable, "-c", "import time; time.sleep(60)", **kw)
        children.append(child)
        return child

    if hook == "release_error":
        def fail_release(*a):
            raise OSError("fixture release failed")
        monkeypatch.setattr(vram.VRAMAllocator, "release", fail_release)
    monkeypatch.setattr(runner, "_observer", lambda: Observer())
    monkeypatch.setattr(asyncio, "create_subprocess_exec", launch)

    async def scenario():
        task = asyncio.create_task(runner._run_step_async("goodq_audio_embed", "audio_embed_clap", {}, cfg))
        try:
            await asyncio.wait_for(ready.wait(), 5)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert children[0].returncode is not None
        finally:
            if children and children[0].returncode is None:
                children[0].kill()
            if children:
                await asyncio.wait_for(children[0].communicate(), 5)

    asyncio.run(scenario())
    assert bool(vram.VRAMAllocator()._read_registry()) is (hook == "release_error")


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_timeout_is_bounded_and_keeps_unreaped_worker_ownership(runtime, monkeypatch, mode):
    runner, cfg, vram = runtime
    inputs = []
    communicating = asyncio.Event()
    monkeypatch.setattr(runner, "_observer", lambda: _RecorderObserver())
    monkeypatch.setattr(runner, "STEP_TIMEOUT", 0.01)

    class Process:
        pid = os.getpid()
        returncode = None

        def kill(self):
            raise PermissionError("fixture child cannot be stopped")

        terminate = kill

        def communicate(self, timeout=None):
            raise subprocess.TimeoutExpired("fixture", timeout)

    class AsyncProcess(Process):
        async def communicate(self):
            communicating.set()
            await asyncio.Event().wait()

        async def wait(self):
            await asyncio.Event().wait()

    def launch(cmd, **kw):
        inputs.append(Path(cmd[cmd.index("--in") + 1]))
        return Process()

    async def launch_async(*cmd, **kw):
        inputs.append(Path(cmd[cmd.index("--in") + 1]))
        return AsyncProcess()

    if mode == "sync":
        monkeypatch.setattr(subprocess, "Popen", launch)
        with pytest.raises(RuntimeError, match="timed out"):
            runner._run_step("goodq_audio_embed", "audio_embed_clap", {}, cfg)
    else:
        real_wait_for = asyncio.wait_for

        async def bounded_wait(awaitable, timeout):
            return await real_wait_for(awaitable, min(timeout, 0.02))

        monkeypatch.setattr(asyncio, "create_subprocess_exec", launch_async)
        monkeypatch.setattr(asyncio, "wait_for", bounded_wait)

        async def scenario():
            task = asyncio.create_task(runner._run_step_async("goodq_audio_embed", "audio_embed_clap", {}, cfg))
            await real_wait_for(communicating.wait(), 5)
            result = await real_wait_for(task, 0.5)
            assert result["status"] == "error" and "timed out" in result["errors"]

        asyncio.run(scenario())
    assert len(vram.VRAMAllocator()._read_registry()) == 1
    assert inputs[0].exists()
    inputs[0].unlink()
    inputs[0].parent.rmdir()
