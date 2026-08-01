from pathlib import Path
import subprocess
import sys

import pytest

from scripts import sync_wsl_audio_worker as sync


def _worker_root(tmp_path: Path) -> Path:
    root = tmp_path / "worker"
    root.mkdir()
    for name, content in {
        "setup_cuda_env.sh": b"setup\n",
        "process_audio.py": b"processor\n",
        "model_cache.py": b"cache\n",
    }.items():
        (root / name).write_bytes(content)
    return root


def test_synchronize_worker_skips_writes_when_hashes_match(tmp_path: Path, monkeypatch) -> None:
    root = _worker_root(tmp_path)
    expected = sync.expected_worker_hashes(root)
    monkeypatch.setattr(sync, "deployed_worker_hashes", lambda *_: dict(expected))
    writes: list[str] = []
    monkeypatch.setattr(sync, "_write_worker_file", lambda _d, _w, name, _source: writes.append(name))

    assert sync.synchronize_worker("Ubuntu-22.04", "/home/test/goodq_audio", source_root=root) == ()
    assert writes == []


def test_synchronize_worker_writes_only_stale_files_and_requires_postwrite_match(tmp_path: Path, monkeypatch) -> None:
    root = _worker_root(tmp_path)
    expected = sync.expected_worker_hashes(root)
    calls = iter((
        {"setup_cuda_env.sh": expected["setup_cuda_env.sh"], "process_audio.py": "0" * 64},
        dict(expected),
    ))
    monkeypatch.setattr(sync, "deployed_worker_hashes", lambda *_: next(calls))
    writes: list[str] = []
    monkeypatch.setattr(sync, "_write_worker_file", lambda _d, _w, name, _source: writes.append(name))

    assert sync.synchronize_worker("Ubuntu-22.04", "/home/test/goodq_audio", source_root=root) == (
        "process_audio.py",
        "model_cache.py",
    )
    assert writes == ["process_audio.py", "model_cache.py"]


def test_synchronize_worker_fails_closed_when_postwrite_hashes_remain_stale(tmp_path: Path, monkeypatch) -> None:
    root = _worker_root(tmp_path)
    monkeypatch.setattr(sync, "deployed_worker_hashes", lambda *_: {})
    monkeypatch.setattr(sync, "_write_worker_file", lambda *_: None)

    with pytest.raises(RuntimeError, match="process_audio.py"):
        sync.synchronize_worker("Ubuntu-22.04", "/home/test/goodq_audio", source_root=root)


def test_sync_helper_direct_execution_can_import_project_package() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/sync_wsl_audio_worker.py", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Synchronize only versioned GoodQ WSL audio worker files" in completed.stdout


def test_worker_copy_command_uses_an_explicit_atomic_temp_path(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(sync, "_wsl", lambda _d, command: calls.append(command) or type("R", (), {"returncode": 0})())

    sync._write_worker_file(
        "Ubuntu-22.04",
        "/home/test/goodq_audio",
        "process_audio.py",
        Path("L:/repo/wsl2_audio/process_audio.py"),
    )

    assert "$tmp" not in calls[0]
    assert "process_audio.py.goodq-new" in calls[0]
