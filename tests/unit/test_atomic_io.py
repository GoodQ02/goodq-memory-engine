from __future__ import annotations

import json
from pathlib import Path

from steps.common import atomic_io


def test_concurrent_reader_writer_retries_windows_sharing_violation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "receipt.json"
    target.write_text(json.dumps({"status": "before"}), encoding="utf-8")
    calls = 0
    original = atomic_io._replace_file_allowing_open_readers

    def transient_lock(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls < 3:
            error = PermissionError(32, "sharing violation")
            error.winerror = 32
            raise error
        original(source, destination)

    monkeypatch.setattr(atomic_io, "_replace_file_allowing_open_readers", transient_lock)
    monkeypatch.setattr(atomic_io.time, "sleep", lambda _: None)

    atomic_io.atomic_write_json_for_concurrent_readers(target, {"status": "after"})

    assert calls == 3
    assert json.loads(target.read_text(encoding="utf-8")) == {"status": "after"}
