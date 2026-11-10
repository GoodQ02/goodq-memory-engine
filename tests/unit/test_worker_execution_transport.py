"""Real child processes exercise the production worker transport without models."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.unit.test_run_ingestion_step_observer_metadata import _RecorderObserver, _write_cfg


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("outcome", [
    "stdout", "file", "failure", "invalid_stdout", "invalid_stderr", "file_noisy", "failure_noisy", "invalid_file",
    "blank_stdout", "blank_file", "empty_object", "semantic_failure",
    pytest.param("native_retry", marks=pytest.mark.skipif(sys.platform != "win32", reason="Windows native exit status")),
])
def test_real_worker_transport_preserves_text_and_rejects_invalid_results(
    tmp_path, monkeypatch, mode, outcome
):
    from cli import run_ingestion as runner
    from configs import python_paths

    message = "caf\u00e9 \u5bb6 \U0001f642"
    root = tmp_path / message
    root.mkdir()
    cfg = _write_cfg(root, host={"profile": "BASELINE", "require_gpu": False})
    child_script = root / "worker.py"
    child_script.write_text('''
import json, sys
from pathlib import Path
sys.stdout.reconfigure(errors="replace")
sys.stderr.reconfigure(errors="replace")
args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
payload = json.loads(Path(args["--in"]).read_text(encoding="utf-8"))
config = json.loads(Path(args["--cfg"]).read_text(encoding="utf-8"))
assert Path(args["--cfg"]).parent.name == payload["text"]
outcome = payload["outcome"]
if outcome == "blank_stdout":
    print("  ")
elif outcome == "blank_file":
    Path(args["--out"]).write_text("  ", encoding="utf-8")
    print('{"text":"must not override the result file"}')
elif outcome == "empty_object":
    print('{}')
elif outcome == "semantic_failure":
    print(json.dumps({"clip_meta":{"status":"error","error":"fixture model failed"}}))
elif outcome == "invalid_stdout":
    sys.stdout.buffer.write(b'{"text":"\\xff"}')
elif outcome == "invalid_file":
    Path(args["--out"]).write_bytes(b'{"text":"\\xff"}')
    print(json.dumps({"text": payload["text"]}))
elif outcome == "invalid_stderr":
    sys.stderr.buffer.write(b'invalid diagnostic: \\xff')
    sys.exit(7)
elif outcome in {"failure", "failure_noisy"}:
    if outcome == "failure_noisy":
        sys.stdout.buffer.write(b'native diagnostic: \\xff')
    print(payload["text"], file=sys.stderr)
    sys.exit(7)
else:
    if outcome == "native_retry":
        marker = Path(args["--cfg"]).parent / "native-exit-seen"
        if not marker.exists():
            marker.touch()
            sys.stdout.buffer.write(b'native diagnostic: \\xff')
            sys.stdout.flush()
            import ctypes
            ctypes.windll.kernel32.ExitProcess(ctypes.c_uint32(0xC0000005))
    result = json.dumps({"text":payload["text"]}, ensure_ascii=False)
    if outcome in {"file", "file_noisy"}:
        Path(args["--out"]).write_text(result, encoding="utf-8")
        if outcome == "file_noisy":
            sys.stdout.buffer.write(b'native diagnostic: \\xff')
    else:
        print(result)
''', encoding="utf-8")

    monkeypatch.setenv("PYTHONIOENCODING", "cp1252")
    monkeypatch.setenv("PYTHONUTF8", "0")
    parent = dict(os.environ)
    observer = _RecorderObserver()
    monkeypatch.setattr(runner, "_PIPELINE_OBSERVER", observer)
    monkeypatch.setattr(runner, "_CURRENT_RUN_CONTEXT", None)
    monkeypatch.setattr(runner, "_control_agent_runtime_enabled", lambda: False)
    monkeypatch.setattr(runner, "resolve_conda", lambda: "fixture-conda-unavailable")
    monkeypatch.setattr(runner.shutil, "which", lambda _: None)
    monkeypatch.setattr(python_paths, "get_env_python", lambda _: Path(sys.executable))
    real_popen = subprocess.Popen
    real_async = asyncio.create_subprocess_exec
    launches = []

    def command(cmd, kwargs):
        assert Path(cmd[0]).samefile(sys.executable)
        assert Path(cmd[1]).name == "step_runner.py"
        launches.append(dict(kwargs["env"]))
        return [cmd[0], str(child_script), *cmd[2:]]

    def launch(cmd, **kwargs):
        return real_popen(command(cmd, kwargs), **kwargs)

    async def launch_async(*cmd, **kwargs):
        return await real_async(*command(cmd, kwargs), **kwargs)

    if mode == "sync":
        monkeypatch.setattr(runner.subprocess, "Popen", launch)
    else:
        monkeypatch.setattr(asyncio, "create_subprocess_exec", launch_async)
    step_name = "sentiment" if outcome == "native_retry" else "image_embed_clip" if outcome == "semantic_failure" else "fixture_transport"
    args = dict(env_name="goodq_core", step_name=step_name, cfg_json=cfg,
                payload={"text": message, "outcome": outcome}, _prefer_direct_env_python=True,
                _step_env_overrides={"PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"})
    if mode == "async":
        result = asyncio.run(runner._run_step_async(**args))
        if outcome in {"stdout", "file", "file_noisy", "native_retry", "empty_object"}:
            assert result["status"] == "ok", result
            assert result["outputs"] == ({} if outcome == "empty_object" else {"text": message})
        else:
            assert result["status"] == "error", result
            error = result["errors"]
    elif outcome in {"stdout", "file", "file_noisy", "native_retry", "empty_object"}:
        assert runner._run_step(**args) == ({} if outcome == "empty_object" else {"text": message})
    else:
        with pytest.raises(RuntimeError) as caught:
            runner._run_step(**args)
        error = str(caught.value)
    if outcome in {"failure", "failure_noisy"}:
        assert message in error
    elif outcome in {"invalid_stdout", "invalid_file"}:
        assert "UTF-8" in error
    elif outcome == "invalid_stderr":
        assert "\\xff" in error
    if outcome in {"blank_stdout", "blank_file"}:
        assert "empty" in error.lower()
    if outcome == "semantic_failure":
        assert "fixture model failed" in error
    if outcome in {"failure", "failure_noisy", "invalid_stdout", "invalid_file", "invalid_stderr", "blank_stdout", "blank_file", "semantic_failure"}:
        assert not any(row[0] == "step_end" for row in observer.events)
        assert any(row[0] == "step_error" for row in observer.events)
    if outcome == "failure_noisy":
        assert "\\xff" in error
    assert len(launches) == (2 if outcome == "native_retry" else 1)
    assert all(env["PYTHONIOENCODING"] == "utf-8" and env["PYTHONUTF8"] == "1" for env in launches)
    assert os.environ == parent


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("outcome", ["failure", "semantic_failure", "invalid_stdout"])
def test_error_observer_cannot_replace_worker_failure(tmp_path, monkeypatch, mode, outcome):
    class FailingObserver(_RecorderObserver):
        def step_error(self, *args, **kwargs):
            super().step_error(*args, **kwargs)
            raise RuntimeError("fixture notification failed")

    monkeypatch.setattr(sys.modules[__name__], "_RecorderObserver", FailingObserver)
    test_real_worker_transport_preserves_text_and_rejects_invalid_results(tmp_path, monkeypatch, mode, outcome)
