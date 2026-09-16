"""Exercise the real startup lock decision with native process identities."""
import os
import subprocess
import sys

import psutil
import pytest

import cli.watchdog as watchdog


@pytest.fixture
def startup(tmp_path, monkeypatch):
    lock = tmp_path / "watchdog.lock"
    calls = []
    monkeypatch.setattr(watchdog, "load_configs", lambda _: {"paths": {"import_inbox": str(tmp_path), "db_dir": str(tmp_path)}})
    monkeypatch.setattr(watchdog, "_resolve_watchdog_paths", lambda _: {"lock_file": lock, "log_dir": tmp_path})
    monkeypatch.setattr(watchdog, "_configure_watchdog_logging", lambda _: tmp_path / "watchdog.log")
    monkeypatch.setattr(watchdog, "_check_system_restart_events", lambda: None)
    class Processor:
        def __init__(self, *args, **kwargs): pass
        def cleanup_stale_processing_files(self): pass
        def run(self): calls.append("run")
    monkeypatch.setattr(watchdog, "WatchdogProcessor", Processor)
    monkeypatch.delenv("GOODQ_RUNTIME_STOP_EVENT", raising=False)
    return lock, calls


def test_reused_live_pid_cannot_block_an_older_watchdog_lock(startup):
    lock, calls = startup
    with subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)) as child:
        try:
            lock.write_text(str(child.pid))
            past = psutil.Process(child.pid).create_time() - 60
            os.utime(lock, (past, past))
            watchdog.main()
            assert calls == ["run"]
            assert child.poll() is None, "Unrelated reused PID must be left alone"
            assert not lock.exists()
        finally:
            child.terminate()
            child.wait(timeout=5)


def test_live_owner_predating_lock_is_preserved(startup):
    lock, calls = startup
    lock.write_text(str(os.getpid()))
    before = lock.read_bytes()
    with pytest.raises(SystemExit):
        watchdog.main()
    assert calls == []
    assert lock.read_bytes() == before


def test_unknown_process_birth_does_not_remove_lock(startup, monkeypatch):
    lock, calls = startup
    lock.write_text(str(os.getpid()))
    def denied(*args):
        raise psutil.AccessDenied(os.getpid())
    monkeypatch.setattr(psutil, "Process", denied)
    with pytest.raises(SystemExit):
        watchdog.main()
    assert calls == []
    assert lock.read_text() == str(os.getpid())
