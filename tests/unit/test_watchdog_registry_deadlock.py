from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

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


def test_attempt_history_is_flat_and_latest_coverage_stays_authoritative(tmp_path):
    registry = ProcessedRegistry(tmp_path / "state.json")
    registry.mark_processed("same", "first.md", run_id="first", stage_coverage={"text": {"status": "success", "provenance": "v1"}})
    registry.mark_failed("same", "second.md", "second failure", run_id="second")
    registry.mark_failed("same", "second.md", "second failure", run_id="second")
    registry.mark_processed("same", "third.md", run_id="third")
    registry.mark_processed("same", "third.md", run_id="third")
    reloaded = ProcessedRegistry(registry.state_file)
    history = reloaded.processed["same"]["previous_attempts"]
    assert [item["run_id"] for item in history] == ["first", "second"]
    assert all("previous_attempts" not in item and "stage_coverage" not in item for item in history)
    assert history[1]["error"] == "second failure"
    assert reloaded.is_processed("same")
    assert reloaded.coverage_decision("same", {"text": "v1"}) == "recover"


def test_registry_write_failure_preserves_previous_attempt_on_disk_and_in_memory(tmp_path, monkeypatch):
    import cli.watchdog as watchdog

    registry = ProcessedRegistry(tmp_path / "state.json")
    registry.mark_failed("same", "first.md", "first failure", run_id="first")
    before = registry.state_file.read_bytes()
    def denied(*args):
        raise OSError("registry write denied")
    monkeypatch.setattr(watchdog, "atomic_write_json", denied)
    with pytest.raises(OSError, match="registry write denied"):
        registry.mark_processed("same", "retry.md", run_id="retry")
    assert registry.state_file.read_bytes() == before
    assert registry.processed == json.loads(before)
