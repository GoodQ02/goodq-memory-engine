"""External Windows control must preserve work; owner death must contain it."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time
from urllib.request import urlopen
import uuid

import psutil
import pytest

REPO = Path(__file__).resolve().parents[2]
WORKER = Path(__file__).parent / "fixtures/runtime_lifecycle_worker.py"
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="native Windows lifecycle")


def wait_until(predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.025)
    pytest.fail("bounded lifecycle condition did not become true")


def is_alive(identity):
    try:
        process = psutil.Process(identity["pid"])
        return process.create_time() == identity["birth"] and process.is_running()
    except psutil.NoSuchProcess:
        return False


def completed(root):
    with sqlite3.connect(root / "work.sqlite") as database:
        return [row[0] for row in database.execute("SELECT name FROM completed ORDER BY rowid")]


@contextmanager
def owned_runtime(root, role):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateEventW.restype = wintypes.HANDLE
    kernel.SetEvent.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    event_name = "Local\\GoodQRuntime-" + uuid.uuid4().hex
    event = kernel.CreateEventW(None, True, False, event_name)
    assert event, ctypes.WinError(ctypes.get_last_error())
    with sqlite3.connect(root / "work.sqlite") as database:
        database.execute("CREATE TABLE completed(name TEXT)")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    env = dict(os.environ, GOODQ_LIFECYCLE_TEST_ROOT=str(root), GOODQ_RUNTIME_STOP_EVENT=event_name,
               GOODQ_API_PORT=str(port), PYTHONIOENCODING="utf-8")
    with (root / "runtime.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen([sys.executable, str(WORKER), role], cwd=REPO, env=env,
                                   stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            yield process, lambda: kernel.SetEvent(event), port
        finally:
            # Only retained parent handles or exact birth + fixture environment
            # matches can be cleaned up, including under a deliberately bad guard.
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            for name in ("transaction", "step"):
                marker = root / (name + ".json")
                if marker.is_file():
                    identity = json.loads(marker.read_text())
                    if is_alive(identity):
                        child = psutil.Process(identity["pid"])
                        assert child.environ().get("GOODQ_LIFECYCLE_TEST_ROOT") == str(root)
                        child.kill()
                        child.wait(timeout=5)
            kernel.CloseHandle(event)


def start_request(pool, port, process):
    def ready():
        assert process.poll() is None, "isolated API exited before readiness"
        try:
            with urlopen(f"http://127.0.0.1:{port}/", timeout=.3) as response:
                return response.status == 200
        except OSError:
            return False
    wait_until(ready)
    def request():
        with urlopen(f"http://127.0.0.1:{port}/work", timeout=20) as response:
            return response.status, response.read()
    return pool.submit(request)


@pytest.mark.parametrize("role", ["watchdog", "api"])
def test_external_stop_drains_active_transaction(tmp_path, role):
    with owned_runtime(tmp_path, role) as (process, stop, port), ThreadPoolExecutor(1) as pool:
        request = start_request(pool, port, process) if role == "api" else None
        wait_until(lambda: (tmp_path / "transaction.json").is_file())
        assert completed(tmp_path) == [], "work was not held inside the transaction"
        assert stop(), "external event request failed"
        try:
            if role == "watchdog":
                wait_until(lambda: (tmp_path / "producer-stopped.json").is_file(), 4)
            else:
                wait_until(lambda: "Waiting for connections" in (tmp_path / "runtime.log").read_text(), 4)
            assert process.poll() is None, "stop abandoned active work"
            assert completed(tmp_path) == []
        finally:
            (tmp_path / "release").touch()
        assert process.wait(timeout=10) == 0, (tmp_path / "runtime.log").read_text()
        assert completed(tmp_path) == (["active", "last-producer-item"] if role == "watchdog" else ["active"])
        if request:
            assert request.result(timeout=5) == (200, b"complete")


@pytest.mark.parametrize("role", ["watchdog", "api"])
def test_owner_crash_leaves_no_step_or_partial_commit(tmp_path, role):
    with owned_runtime(tmp_path, role) as (process, _stop, port), ThreadPoolExecutor(1) as pool:
        request = start_request(pool, port, process) if role == "api" else None
        wait_until(lambda: (tmp_path / "transaction.json").is_file())
        identities = [json.loads((tmp_path / (name + ".json")).read_text()) for name in ("step", "transaction")]
        assert all(is_alive(identity) for identity in identities)
        process.kill()
        process.wait(timeout=5)
        wait_until(lambda: not any(is_alive(identity) for identity in identities), 4)
        assert completed(tmp_path) == []
        assert not (tmp_path / "owner-finished.json").exists()
        if request:
            with pytest.raises(OSError):
                request.result(timeout=5)
