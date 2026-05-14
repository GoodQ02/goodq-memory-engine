from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts import bootstrap_install


def _completed(cmd: list[str], returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)


def _step_spec() -> bootstrap_install.StepEnvSpec:
    return bootstrap_install.StepEnvSpec(
        "goodq_video_scene_detect",
        "envs/video_scene_detect/requirements.txt",
        "envs/locks/video_scene_detect.lock.txt",
        "scene detection",
        ("scenedetect", "cv2", "numpy"),
    )


def _write_lock(repo_root: Path) -> Path:
    lock_path = repo_root / "envs" / "locks" / "video_scene_detect.lock.txt"
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text("numpy==2.2.6\nscenedetect==0.6.2\n", encoding="utf-8")
    return lock_path


def test_step_env_lock_install_retries_transient_pip_transport_failure(monkeypatch, tmp_path):
    _write_lock(tmp_path)
    messages: list[str] = []
    lock_attempts = 0
    transient_error = (
        "urllib3.exceptions.ProtocolError: "
        "Connection broken: IncompleteRead while downloading numpy"
    )

    def fake_run(cmd: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        nonlocal lock_attempts
        if "--upgrade" in cmd:
            return _completed(cmd)
        if "-r" in cmd:
            lock_attempts += 1
            if lock_attempts == 1:
                return _completed(cmd, returncode=1, stderr=transient_error)
            return _completed(cmd)
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(bootstrap_install, "_run", fake_run)
    monkeypatch.setattr(bootstrap_install, "_print", lambda message: messages.append(message))
    monkeypatch.setattr(bootstrap_install.time, "sleep", lambda _seconds: None)

    bootstrap_install._install_step_env_from_lock(Path("conda"), tmp_path, _step_spec())

    assert lock_attempts == 2
    assert any("Transient pip download failure for goodq_video_scene_detect" in message for message in messages)


def test_pip_transient_detection_includes_ssl_and_temporary_http_5xx():
    assert bootstrap_install._is_transient_pip_network_error(
        "pip._vendor.requests.exceptions.SSLError: TLS handshake timed out"
    )
    assert bootstrap_install._is_transient_pip_network_error(
        "HTTPSConnectionPool(host='download.pytorch.org'): HTTP 503 Service Unavailable"
    )


def test_step_env_lock_install_raises_after_transient_pip_retry_ceiling(monkeypatch, tmp_path):
    _write_lock(tmp_path)
    lock_attempts = 0
    transient_error = "ChunkedEncodingError: Connection broken while downloading numpy"

    def fake_run(cmd: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        nonlocal lock_attempts
        if "--upgrade" in cmd:
            return _completed(cmd)
        if "-r" in cmd:
            lock_attempts += 1
            return _completed(cmd, returncode=1, stderr=transient_error)
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(bootstrap_install, "_run", fake_run)
    monkeypatch.setattr(bootstrap_install.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="ChunkedEncodingError"):
        bootstrap_install._install_step_env_from_lock(Path("conda"), tmp_path, _step_spec())

    assert lock_attempts == 3


def test_step_env_lock_install_does_not_retry_non_transient_pip_error(monkeypatch, tmp_path):
    _write_lock(tmp_path)
    lock_attempts = 0
    resolver_error = "ERROR: No matching distribution found for definitely-not-a-goodq-package"

    def fake_run(cmd: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        nonlocal lock_attempts
        if "--upgrade" in cmd:
            return _completed(cmd)
        if "-r" in cmd:
            lock_attempts += 1
            return _completed(cmd, returncode=1, stderr=resolver_error)
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(bootstrap_install, "_run", fake_run)

    with pytest.raises(RuntimeError, match="No matching distribution"):
        bootstrap_install._install_step_env_from_lock(Path("conda"), tmp_path, _step_spec())

    assert lock_attempts == 1


def test_step_env_lock_install_keeps_no_deps(monkeypatch, tmp_path):
    _write_lock(tmp_path)
    install_cmd: list[str] | None = None

    def fake_run(cmd: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        nonlocal install_cmd
        if "--upgrade" in cmd:
            return _completed(cmd)
        if "-r" in cmd:
            install_cmd = cmd
            return _completed(cmd)
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(bootstrap_install, "_run", fake_run)

    bootstrap_install._install_step_env_from_lock(Path("conda"), tmp_path, _step_spec())

    assert install_cmd is not None
    assert "--no-deps" in install_cmd


def test_cuda_step_env_lock_install_keeps_extra_index_and_pip_resilience_flags(monkeypatch, tmp_path):
    lock_path = _write_lock(tmp_path)
    lock_path.write_text("torch==2.5.1+cu121\ntorchvision==0.20.1+cu121\n", encoding="utf-8")
    install_cmd: list[str] | None = None

    def fake_run(cmd: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        nonlocal install_cmd
        if "--upgrade" in cmd:
            return _completed(cmd)
        if "-r" in cmd:
            install_cmd = cmd
            return _completed(cmd)
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(bootstrap_install, "_run", fake_run)

    bootstrap_install._install_step_env_from_lock(Path("conda"), tmp_path, _step_spec())

    assert install_cmd is not None
    assert "--no-deps" in install_cmd
    assert "--extra-index-url" in install_cmd
    assert bootstrap_install.TORCH_CUDA_INDEX_URL in install_cmd
    assert "--retries" in install_cmd
    assert "--timeout" in install_cmd
