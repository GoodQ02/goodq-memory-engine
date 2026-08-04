from __future__ import annotations

import json
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


def test_execute_records_preflight_failure(monkeypatch, tmp_path: Path):
    root = tmp_path / "witness"
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"clip")
    monkeypatch.setattr(remote_witness, "prepare_witness_run", lambda *_: (_ for _ in ()).throw(RuntimeError("ffmpeg unavailable")))

    assert remote_witness.execute(root, source) == 1
    receipt = json.loads(remote_witness.receipt_path(root).read_text(encoding="utf-8"))
    assert receipt["phase"] == "failed"
    assert "ffmpeg unavailable" in receipt["error"]


def test_launch_uses_task_scheduler_on_windows(monkeypatch, tmp_path: Path):
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
