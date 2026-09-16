"""Queue ownership must survive errors and a graceful shutdown."""
from pathlib import Path
from queue import Empty
from threading import Event, Thread
from types import SimpleNamespace

import cli.watchdog as watchdog
from tests.unit.test_watchdog_processed_prefix_idempotent import _watchdog_cfg


def test_worker_acknowledges_failed_item_before_stopping(tmp_path, monkeypatch):
    monkeypatch.setattr(watchdog, "CONTROL_AGENT_AVAILABLE", False)
    processor = watchdog.WatchdogProcessor(_watchdog_cfg(tmp_path))
    processor.queue.put((Path("failed.mp4"), "hash"))
    processor.queue.put((None, None))

    def fail_processing(*_args):
        processor.shutdown.set()
        raise RuntimeError("fixture worker failure")

    monkeypatch.setattr(processor, "process_file", fail_processing)
    processor.worker_loop()

    assert processor.queue.unfinished_tasks == 0
    assert processor.queue.empty()


def test_shutdown_drains_in_flight_and_final_producer_work(tmp_path, monkeypatch):
    monkeypatch.setattr(watchdog, "CONTROL_AGENT_AVAILABLE", False)
    monkeypatch.setattr(watchdog, "MAX_WORKERS", 1)
    processor = watchdog.WatchdogProcessor(_watchdog_cfg(tmp_path))
    first_started, release_first, producer_done = Event(), Event(), Event()
    processed = []
    processor.queue.put((Path("first.mp4"), "first-hash"))

    def process(file_path, _file_hash):
        if file_path.name == "first.mp4":
            first_started.set()
            assert release_first.wait(3)
        processed.append(file_path.name)

    def finish_scan():
        assert processor.shutdown.wait(3)
        processor.queue.put((Path("last.mp4"), "last-hash"))
        producer_done.set()

    def request_shutdown(_seconds):
        assert first_started.wait(3)
        raise KeyboardInterrupt

    monkeypatch.setattr(processor, "process_file", process)
    monkeypatch.setattr(processor, "monitor_loop", finish_scan)
    monkeypatch.setattr(watchdog, "time", SimpleNamespace(sleep=request_shutdown))
    runner = Thread(target=processor.run, daemon=True)
    runner.start()
    try:
        assert processor.shutdown.wait(3)
        assert producer_done.wait(3)
        release_first.set()
        runner.join(timeout=3)
        assert not runner.is_alive(), "shutdown stranded queued work"
        assert processed == ["first.mp4", "last.mp4"]
        assert processor.queue.unfinished_tasks == 0
    finally:
        # Keep a failing implementation from leaving a blocked test thread.
        release_first.set()
        if runner.is_alive():
            while True:
                try:
                    processor.queue.get_nowait()
                except Empty:
                    break
                processor.queue.task_done()
            runner.join(timeout=3)
