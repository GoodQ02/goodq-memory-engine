from __future__ import annotations

import json
import errno
import socket
from pathlib import Path

import pytest

from cli import remote_witness


def test_execute_persists_terminal_receipt(monkeypatch, tmp_path: Path):
    root = tmp_path / "witness"
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"clip")
    sealed = root / "prepared-receipt.json"

    monkeypatch.setattr(remote_witness, "prepare_witness_run", lambda *_: {"status": "prepared"})
    monkeypatch.setattr(remote_witness, "seal_prepared_receipt", lambda *_: sealed)
    monkeypatch.setattr(remote_witness, "_start_isolated_qdrant", lambda *_: type("Qdrant", (), {"pid": 24})())
    monkeypatch.setattr(remote_witness, "_stop_isolated_qdrant", lambda *_: None)

    class Process:
        pid = 42

        def wait(self):
            return 0

    monkeypatch.setattr(remote_witness.subprocess, "Popen", lambda *_, **__: Process())

    assert remote_witness.execute(root, source) == 0
    receipt = json.loads(remote_witness.receipt_path(root).read_text(encoding="utf-8"))
    assert receipt["phase"] == "runner_finished"
    assert receipt["runner_exit_code"] == 0
    assert receipt["runner_pid"] == 42


def test_execute_bounds_each_isolated_witness_step(monkeypatch, tmp_path: Path):
    import multiprocessing
    monkeypatch.setattr(multiprocessing, "cpu_count", lambda: 24)
    root = tmp_path / "witness"
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"clip")
    sealed = root / "prepared-receipt.json"
    captured = {}

    monkeypatch.setattr(remote_witness, "prepare_witness_run", lambda *_: {"status": "prepared"})
    monkeypatch.setattr(remote_witness, "seal_prepared_receipt", lambda *_: sealed)
    monkeypatch.setattr(remote_witness, "_start_isolated_qdrant", lambda *_: type("Qdrant", (), {"pid": 24})())
    monkeypatch.setattr(remote_witness, "_stop_isolated_qdrant", lambda *_: None)

    class Process:
        pid = 43

        def wait(self):
            return 0

    def _popen(command, **_kwargs):
        captured["command"] = command
        return Process()

    monkeypatch.setattr(remote_witness.subprocess, "Popen", _popen)

    assert remote_witness.execute(root, source) == 0
    assert captured["command"][-2:] == ["--step-timeout", "600"]
    output_index = captured["command"].index("--output")
    assert captured["command"][output_index + 1] == str(root / "output" / "results.json")


def test_execute_records_preflight_failure(monkeypatch, tmp_path: Path):
    root = tmp_path / "witness"
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"clip")
    monkeypatch.setattr(remote_witness, "prepare_witness_run", lambda *_: (_ for _ in ()).throw(RuntimeError("ffmpeg unavailable")))

    assert remote_witness.execute(root, source) == 1
    receipt = json.loads(remote_witness.receipt_path(root).read_text(encoding="utf-8"))
    assert receipt["phase"] == "failed"
    assert "ffmpeg unavailable" in receipt["error"]


def test_execute_owns_and_stops_isolated_qdrant(monkeypatch, tmp_path: Path):
    root = tmp_path / "witness"
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"clip")
    sealed = root / "prepared-receipt.json"
    qdrant = type("Qdrant", (), {"pid": 24})()
    stopped = []

    monkeypatch.setattr(remote_witness, "prepare_witness_run", lambda *_: {"status": "prepared"})
    monkeypatch.setattr(remote_witness, "seal_prepared_receipt", lambda *_: sealed)
    monkeypatch.setattr(remote_witness, "_start_isolated_qdrant", lambda *_: qdrant)
    monkeypatch.setattr(remote_witness, "_stop_isolated_qdrant", lambda process: stopped.append(process))

    class Process:
        pid = 42

        def wait(self):
            return 0

    monkeypatch.setattr(remote_witness.subprocess, "Popen", lambda *_, **__: Process())

    assert remote_witness.execute(root, source) == 0
    assert stopped == [qdrant]


def test_qdrant_port_probe_accepts_a_successful_loopback_bind(monkeypatch):
    bound = []

    class Probe:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def bind(self, address):
            bound.append(address)

    monkeypatch.setattr(remote_witness.socket, "socket", lambda *_args: Probe())

    remote_witness._assert_qdrant_port_is_free()

    assert bound == [("127.0.0.1", 6333)]


def test_qdrant_port_probe_reports_an_occupied_port(monkeypatch):
    class Probe:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def bind(self, _address):
            raise OSError(errno.EADDRINUSE, "address already in use")

    monkeypatch.setattr(remote_witness.socket, "socket", lambda *_args: Probe())

    with pytest.raises(remote_witness.WitnessRuntimeError, match="already in use"):
        remote_witness._assert_qdrant_port_is_free()


def test_qdrant_port_probe_reports_a_bind_error(monkeypatch):
    def raise_socket_error(*_args, **_kwargs):
        raise OSError("socket unavailable")

    monkeypatch.setattr(remote_witness.socket, "socket", raise_socket_error)

    with pytest.raises(remote_witness.WitnessRuntimeError, match="could not bind"):
        remote_witness._assert_qdrant_port_is_free()


def test_launch_uses_task_scheduler_on_windows_without_a_scheduled_replay(monkeypatch, tmp_path: Path):
    root = tmp_path / "witness"
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"clip")
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))

    monkeypatch.setattr(remote_witness.os, "name", "nt")
    monkeypatch.setattr(remote_witness.subprocess, "run", run)

    receipt_path = remote_witness.launch(root, source)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["phase"] == "launcher_started"
    assert receipt["scheduler_task"] == "GoodQ4All-RemoteWitness-witness"
    assert Path(receipt["scheduler_worker"]).exists()
    assert receipt["command"][1:4] == ["-m", "cli.remote_witness", "execute"]
    assert [call[0][1] for call in calls] == ["/Create", "/Run"]
    worker = Path(receipt["scheduler_worker"]).read_text(encoding="utf-8")
    assert 'schtasks.exe /Change /TN "GoodQ4All-RemoteWitness-witness" /Disable' in worker
    assert 'schtasks.exe /Delete /TN "GoodQ4All-RemoteWitness-witness" /F' in worker


def test_launch_records_scheduler_failure(monkeypatch, tmp_path: Path):
    root = tmp_path / "witness"
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"clip")
    monkeypatch.setattr(remote_witness.os, "name", "nt")
    monkeypatch.setattr(
        remote_witness,
        "_launch_with_task_scheduler",
        lambda *_: (_ for _ in ()).throw(RuntimeError("scheduler unavailable")),
    )

    with pytest.raises(RuntimeError, match="scheduler unavailable"):
        remote_witness.launch(root, source)

    receipt = json.loads(remote_witness.receipt_path(root).read_text(encoding="utf-8"))
    assert receipt["phase"] == "failed"
    assert "scheduler unavailable" in receipt["error"]
