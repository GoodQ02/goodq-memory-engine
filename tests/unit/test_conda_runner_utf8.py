"""UTF-8 transport through the real JSON dispatcher without model compute."""
import contextlib
import io
import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest


@pytest.mark.parametrize("fails", [False, True])
def test_conda_transport_binds_utf8_and_preserves_dispatcher_result_or_failure(monkeypatch, tmp_path, fails):
    from cli import step_runner
    from steps.common import conda_runner, step_logger, tool_paths

    message = "GoodQ \ufffd caf\u00e9 \u5bb6"
    monkeypatch.setenv("PYTHONIOENCODING", "cp1252")
    monkeypatch.setenv("PYTHONUTF8", "0")
    monkeypatch.setattr(conda_runner, "_resolve_models_root", lambda: str(tmp_path / "models"))
    monkeypatch.setattr(tool_paths, "resolve_conda", lambda: "fixture-conda")
    monkeypatch.setattr(step_runner, "load_step_config", lambda path, *_: json.loads(Path(path).read_text(encoding="utf-8")))
    monkeypatch.setattr(step_logger, "MISSION_LOGGER_AVAILABLE", False)
    gpu = types.ModuleType("common.gpu_manager")
    gpu.initialize_gpu_for_step = lambda **_: None
    monkeypatch.setitem(sys.modules, "common.gpu_manager", gpu)
    def compute(name, item, cfg):
        assert item["text"] == message and cfg["label"] == message
        print(message)
        if fails:
            raise RuntimeError(message)
        return {"text": message}
    monkeypatch.setattr(step_runner, "run_step", compute)

    def conda_transport(cmd, **kwargs):
        assert cmd[:7] == ["fixture-conda", "run", "-n", "goodq_core", "python", "-m", "cli.step_runner"]
        assert kwargs["encoding"] == "utf-8"
        assert kwargs["env"]["PYTHONIOENCODING"] == "utf-8"
        assert kwargs["env"]["PYTHONUTF8"] == "1"
        output = io.StringIO()
        with monkeypatch.context() as child, contextlib.redirect_stdout(output):
            child.setattr(sys, "argv", ["step_runner", *cmd[7:]])
            try:
                step_runner.main()
            except RuntimeError as error:
                raise subprocess.CalledProcessError(7, cmd, output=output.getvalue(), stderr=str(error)) from error
        # Model the intermediate Conda writer as well as the outer UTF-8 reader.
        stdout = output.getvalue().encode(kwargs["env"]["PYTHONIOENCODING"]).decode(kwargs["encoding"])
        assert message in stdout
        return subprocess.CompletedProcess(cmd, 0, stdout, "")
    monkeypatch.setattr(conda_runner.subprocess, "run", conda_transport)
    cfg = {"label": message, "paths": {"log_dir": str(tmp_path / "logs")}, "gpu": {"clear_cache_before_step": False}}
    if fails:
        with pytest.raises(conda_runner.StepExecutionError, match="exit code 7") as caught:
            conda_runner.run_conda_step("goodq_core", "fixture_utf8", {"text": message}, cfg)
        assert f"STDERR: {message}" in str(caught.value)
        assert f"STDOUT: {message}" in str(caught.value)
    else:
        assert conda_runner.run_conda_step("goodq_core", "fixture_utf8", {"text": message}, cfg) == {"text": message}
    assert os.environ["PYTHONIOENCODING"] == "cp1252" and os.environ["PYTHONUTF8"] == "0"
    row = json.loads((tmp_path / "logs/step_runs.jsonl").read_text(encoding="utf-8"))
    assert row["status"] == ("error" if fails else "ok")


@pytest.mark.parametrize("raw,step,error", [
    (b'null', 'image_embed_clip', 'object'),
    (b'[]', 'image_embed_clip', 'object'),
    (b'{"text":"\xff"}', 'image_embed_clip', 'UTF-8'),
    (b'{"clip_meta":{"status":"error","error":"fixture model failed"}}', 'image_embed_clip', 'fixture model failed'),
    (b'{}', 'fixture', None),
    (b'{"clap_meta":{"status":"skipped","reason":"audio_silent"}}', 'audio_embed_clap', None),
    (b'{"tagger_meta":{"status":"skipped","reason":"disabled"}}', 'tagger', None),
])
def test_conda_adapter_validates_structured_outcome(monkeypatch, tmp_path, raw, step, error):
    from steps.common import conda_runner, tool_paths
    monkeypatch.setattr(conda_runner, "_resolve_models_root", lambda: str(tmp_path/'models'))
    monkeypatch.setattr(tool_paths, "resolve_conda", lambda: "fixture-conda")

    def transport(cmd, **kwargs):
        Path(cmd[cmd.index('--out') + 1]).write_bytes(raw)
        return subprocess.CompletedProcess(cmd, 0, '', '')

    monkeypatch.setattr(conda_runner.subprocess, "run", transport)
    if error:
        with pytest.raises(conda_runner.StepExecutionError, match=error):
            conda_runner.run_conda_step('goodq_core', step, {}, {})
    else:
        assert conda_runner.run_conda_step('goodq_core', step, {}, {}) == json.loads(raw)
