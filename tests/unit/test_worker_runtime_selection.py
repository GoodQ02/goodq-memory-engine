"""The production launch boundary must honor isolated runtime selection."""
from pathlib import Path
import sys

import pytest

from steps.common.worker_launch import WorkerRequest, prepare_worker_launch


@pytest.mark.parametrize("env_name,step,expected", [
    ("goodq_ocr", "image_ocr", "direct_env_python"),
    ("goodq_object_detect", "object_detect", "direct_env_python"),
    ("goodq_caption_vlm", "image_caption", "direct_env_python"),
    ("goodq_core", "sentiment", "conda_run"),
])
def test_locked_runtime_overrides_platform_launcher_preference(tmp_path, monkeypatch, env_name, step, expected):
    from configs import python_paths
    from steps.common import worker_launch
    monkeypatch.setattr(python_paths, "get_env_python", lambda _: Path(sys.executable))
    monkeypatch.setattr(worker_launch.shutil, "which", lambda _: "conda")
    request = WorkerRequest(env_name, step, tmp_path/'in', tmp_path/'out', tmp_path/'cfg')
    launch = prepare_worker_launch(request, {}, repo_root=tmp_path, conda_exe="conda",
                                   prefer_direct=False, prefer_available_python=False)
    assert launch.kind == expected
    if expected == "direct_env_python":
        assert Path(launch.command[0]).samefile(sys.executable)


@pytest.mark.parametrize("sandboxed", [False, True])
def test_missing_environment_never_substitutes_parent_outside_packaged_mode(tmp_path, monkeypatch, sandboxed):
    from configs import python_paths
    from steps.common import worker_launch
    resolver = python_paths.PythonPathConfig()
    monkeypatch.setattr(resolver, "_initialized", True)
    monkeypatch.setattr(resolver, "_conda_base", None)
    monkeypatch.setattr(resolver, "_env_pythons", {})
    monkeypatch.setattr(resolver, "is_sandboxed", sandboxed)
    monkeypatch.setattr(python_paths, "get_env_python", resolver.get_env_python)
    monkeypatch.setattr(worker_launch.shutil, "which", lambda _: None)
    request = WorkerRequest("missing_fixture_environment", "fixture", tmp_path/'in', tmp_path/'out', tmp_path/'cfg')
    args = dict(repo_root=tmp_path, conda_exe="missing-conda", prefer_direct=False, prefer_available_python=True)
    if sandboxed:
        assert Path(prepare_worker_launch(request, {}, **args).command[0]).samefile(sys.executable)
    else:
        with pytest.raises(RuntimeError, match="Conda unavailable"):
            prepare_worker_launch(request, {}, **args)
