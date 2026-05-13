from __future__ import annotations

import json
import threading
from pathlib import Path

from cli.watchdog import ProcessedRegistry


def _run_with_timeout(fn, *, timeout_seconds: float = 2.0) -> None:
    errors: list[BaseException] = []
    done = threading.Event()

    def _target() -> None:
        try:
            fn()
        except BaseException as exc:  # pragma: no cover - surfaced below
            errors.append(exc)
        finally:
            done.set()

    worker = threading.Thread(target=_target, daemon=True)
    worker.start()

    assert done.wait(timeout_seconds), "operation timed out (possible lock deadlock)"
    if errors:
        raise errors[0]


def test_mark_processed_completes_without_deadlock(tmp_path: Path) -> None:
    state_file = tmp_path / "watchdog_state.json"
    registry = ProcessedRegistry(state_file)

    _run_with_timeout(lambda: registry.mark_processed("hash-1", "file.mp4"))

    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved["hash-1"]["status"] == "success"
    assert saved["hash-1"]["original_name"] == "file.mp4"


def test_mark_failed_completes_without_deadlock(tmp_path: Path) -> None:
    state_file = tmp_path / "watchdog_state.json"
    registry = ProcessedRegistry(state_file)

    _run_with_timeout(lambda: registry.mark_failed("hash-2", "broken.mp4", "boom"))

    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved["hash-2"]["status"] == "failed"
    assert saved["hash-2"]["error"] == "boom"
