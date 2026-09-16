"""Run the Windows logon launcher against real, test-owned child processes."""

from __future__ import annotations

import json
import errno
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time

import pytest
import psutil


REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS = Path(__file__).parent / "fixtures" / "dev_startup_harness.ps1"
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows logon contract")

DUMMY = '''
import json, os, sys, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
root = Path(os.environ["GOODQ_STARTUP_TEST_ROOT"])
mode = os.environ["GOODQ_STARTUP_TEST_MODE"]
from steps.common.runtime_lifecycle import RuntimeLifecycle
lifecycle = None if mode == "missing_lifecycle" else RuntimeLifecycle.from_environment(ROLE)
record = {"pid": os.getpid(), "executable": sys.executable,
          "cwd": os.getcwd(), "host": os.environ.get("GOODQ_API_HOST"),
          "port": os.environ.get("GOODQ_API_PORT")}
(root / (ROLE + ".json")).write_text(json.dumps(record), encoding="utf-8")
if ROLE == "api" and mode == "api_early_exit":
    print("fixture API failed before readiness", file=sys.stderr, flush=True)
    sys.exit(17)
if ROLE == "watchdog" and mode == "watchdog_early_exit":
    print("fixture Watchdog failed during startup", file=sys.stderr, flush=True)
    sys.exit(23)
if ROLE == "api":
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            override = root / "api-status.txt"
            status = int(override.read_text()) if override.is_file() else (503 if mode == "api_unhealthy" else 200)
            with (root / "http-paths.txt").open("a") as stream:
                print(self.path, file=stream)
            self.send_response(status)
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        def log_message(self, *args):
            pass
    port = 0 if mode == "api_fallback" else int(os.environ["GOODQ_API_PORT"])
    server = HTTPServer(("127.0.0.1", port), Handler)
    (root / "api-bound.json").write_text(json.dumps({"port":server.server_port}), encoding="utf-8")
    if lifecycle is None:
        server.serve_forever()
    else:
        server.timeout = 0.1
        while not lifecycle.stop_requested(): server.handle_request()
        server.server_close()
else:
    if mode == "owned_descendant":
        import subprocess
        leaf = "import json,os,time; from pathlib import Path; import psutil; root=Path(os.environ['GOODQ_STARTUP_TEST_ROOT']); p=psutil.Process(); (root/('leaf-'+str(p.pid)+'.json')).write_text(json.dumps({'pid':p.pid,'birth':p.create_time()})); time.sleep(45)"
        subprocess.Popen([sys.executable, "-c", leaf])
    if mode in ("active_work", "startup_active_work"):
        (root / "active-work.json").write_text(json.dumps(record))
        if mode == "startup_active_work": (root / "api-status.txt").write_text("503")
    while lifecycle is None or not lifecycle.stop_requested():
        time.sleep(0.1)
    (root / "drain-requested.json").write_text(json.dumps(record))
    if mode in ("active_work", "startup_active_work"):
        deadline = time.monotonic() + 45
        while not (root / "release-work").exists():
            if time.monotonic() >= deadline: sys.exit(29)
            time.sleep(0.025)
        (root / "work-completed.json").write_text(json.dumps(record))
'''

LATE_LISTENER = '''
import json, sys, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
root = Path(sys.argv[1])
deadline = time.monotonic() + 15
while not (root / "api-bound.json").is_file():
    if time.monotonic() >= deadline: sys.exit(9)
    time.sleep(0.01)
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"foreign listener")
    def log_message(self, *args): pass
server = HTTPServer(("127.0.0.1", int(sys.argv[2])), Handler)
(root / "foreign-bound.json").write_text(json.dumps({"port":server.server_port}))
server.serve_forever()
'''


def _wait_for_file(path: Path, child: subprocess.Popen, seconds: float = 8) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if path.is_file():
            return
        assert child.poll() is None, "Test-owned fixture exited before initialization"
        time.sleep(0.025)
    pytest.fail(f"Test-owned fixture did not initialize: {path.name}")


def _cleanup_fixture_children(sandbox: Path) -> None:
    candidates = []
    paths = [sandbox / name for name in ("api.json", "watchdog.json", "owned-processes.json", "step.json", "transaction.json")]
    paths.extend(sandbox.glob("owned-process-*.json"))
    paths.extend(sandbox.glob("leaf-*.json"))
    for path in paths:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            candidates.extend(data if isinstance(data, list) else [data])
    for record in candidates:
        try:
            child = psutil.Process(record.get("pid", record.get("Pid")))
            # Never clean up by PID alone: a reused ID must still carry this
            # unique fixture's deployment identity in its process environment.
            if child.environ().get("GOODQ_STARTUP_TEST_ROOT") == str(sandbox):
                child.terminate()
                child.wait(timeout=5)
        except psutil.NoSuchProcess:
            pass


@pytest.fixture
def launch(tmp_path):
    sandbox = tmp_path / "isolated deployment with spaces"
    sandbox.mkdir()
    for package, module, role in [("api", "server", "api"), ("cli", "watchdog", "watchdog")]:
        directory = sandbox / package
        directory.mkdir()
        (directory / "__init__.py").write_text("", encoding="utf-8")
        (directory / f"{module}.py").write_text(f"ROLE = {role!r}\n" + DUMMY, encoding="utf-8")
    bindings = sandbox / "scripts" / "_lib"
    bindings.mkdir(parents=True)
    common = sandbox / "steps" / "common"
    common.mkdir(parents=True)
    (common.parent / "__init__.py").touch()
    (common / "__init__.py").touch()
    shutil.copyfile(REPO_ROOT / "steps/common/runtime_lifecycle.py", common / "runtime_lifecycle.py")
    shutil.copyfile(REPO_ROOT / "scripts" / "_lib" / "interpreter_bindings.ps1", bindings / "interpreter_bindings.ps1")
    # Environment discovery is external to the startup contract. Bind the
    # fixture to its invoking interpreter even when its prefix is not named
    # goodq_core; keep the real environment-name policy and ownership checks.
    with (bindings / "interpreter_bindings.ps1").open("a", encoding="utf-8") as stream:
        stream.write("\nfunction Get-GoodQPythonExe { return $env:GOODQ_STARTUP_TEST_PYTHON }\n")
    source_path = Path(os.environ.get("GOODQ_STARTUP_TEST_SOURCE", REPO_ROOT / "start_goodq_dev.ps1"))
    source = source_path.read_text(encoding="utf-8-sig")
    # Legacy deployment root only; no startup branches or error policy altered.
    source = re.sub(r"(?m)^\$rootDir = '[^']*'$", lambda _: "$rootDir = '" + str(sandbox).replace("'", "''") + "'", source)
    script = sandbox / "start_goodq_dev.ps1"
    script.write_text(source, encoding="utf-8-sig")

    def invoke(mode="healthy", *, port=None, foreign_pid=0, conda_env="goodq_core",
               supervise=None, max_restarts=0, backoff=0.6, drain_timeout=2, check_start=False):
        if mode in ("real_work", "supervisor_crash"):
            import sqlite3
            worker = Path(__file__).parent / "fixtures/runtime_lifecycle_worker.py"
            with sqlite3.connect(sandbox / "work.sqlite") as database:
                database.execute("CREATE TABLE completed(name TEXT)")
            for package, module, role in [("api", "server", "api"), ("cli", "watchdog", "watchdog")]:
                (sandbox / package / (module + ".py")).write_text(
                    f"import runpy,sys\nsys.argv=[{str(worker)!r},{role!r}]\nrunpy.run_path({str(worker)!r},run_name='__main__')\n",
                    encoding="utf-8",
                )
        if port is None:
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
        env = os.environ.copy()
        # Codex runs PowerShell 7; this fixture exercises the logon shell's own
        # Windows PowerShell modules, without changing the host environment.
        for key in list(env):
            if key.casefold() == "psmodulepath":
                del env[key]
        env["PSMODULEPATH"] = str(Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/Modules")
        env.update({
            "GOODQ_STARTUP_TEST_ROOT": str(sandbox), "GOODQ_STARTUP_TEST_MODE": mode,
            "GOODQ_STARTUP_TEST_PYTHON": sys.executable,
            "GOODQ_LIFECYCLE_TEST_ROOT": str(sandbox),
            "GOODQ_API_HOST": "127.0.0.1", "GOODQ_API_PORT": str(port),
            "GOODQ_CONDA_ENV": conda_env, "CONDA_PREFIX": str(Path(sys.executable).parent),
            "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""),
            "TEMP": str(sandbox), "TMP": str(sandbox),
        })
        receipt = sandbox / "receipt.json"
        console_path = sandbox / "harness-console.log"
        intruder = None
        intruder_alive = False
        if mode == "api_fallback":
            intruder = subprocess.Popen(
                [sys.executable, "-c", LATE_LISTENER, str(sandbox), str(port)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            foreign_pid = intruder.pid
        try:
            # Descendants must not hold a communicate() pipe open after a
            # failing harness exits. The process wait itself stays bounded.
            with console_path.open("wb") as console:
                command = [
                    "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                    "-File", str(HARNESS), "-StartupScript", str(script), "-PythonExe", sys.executable,
                    "-SandboxRoot", str(sandbox), "-Port", str(port), "-Scenario", mode,
                    "-ReceiptPath", str(receipt), "-ForeignPid", str(foreign_pid),
                ]
                if check_start:
                    command += ["-CheckStart"]
                if supervise is not None:
                    command += ["-Supervise", "-MaxRestarts", str(max_restarts),
                                "-RestartBackoffSeconds", str(backoff), "-DrainTimeoutSeconds", str(drain_timeout)]
                with subprocess.Popen(command, env=env, stdout=console, stderr=subprocess.STDOUT) as process:
                    try:
                        if supervise is not None:
                            supervise(sandbox, process)
                        returncode = process.wait(timeout=35)
                    finally:
                        if process.poll() is None:
                            process.terminate()
                            process.wait(timeout=5)
        finally:
            if intruder:
                intruder_alive = intruder.poll() is None
            _cleanup_fixture_children(sandbox)
            if intruder:
                if intruder.poll() is None:
                    intruder.terminate()
                intruder.wait(timeout=5)
        if mode == "supervisor_crash":
            assert returncode != 0, "fixture did not crash the owning PowerShell process"
            assert not receipt.exists(), "a killed supervisor published a terminal harness result"
            return {"sandbox": sandbox, "shell_exit": returncode}
        assert returncode == 0, console_path.read_text(encoding="utf-8", errors="replace")
        result = json.loads(receipt.read_text(encoding="utf-8-sig"))
        result["sandbox"] = sandbox
        result["port"] = port
        result["intruder_alive_after_startup"] = intruder_alive
        return result

    return invoke


def test_healthy_startup_launches_both_real_children(launch):
    result = launch()
    assert result["Completed"], result
    assert result["ServiceRequests"] == 1
    assert result["ChildStarts"] == ["api", "watchdog"]
    assert {c["Role"] for c in result["Children"] if c["Alive"]} == {"api", "watchdog"}
    assert all(Path(c["Record"]["executable"]).samefile(sys.executable) for c in result["Children"])
    paths = list(result["sandbox"].glob("goodq-startup-*/startup.json"))
    assert len(paths) == 1, "Successful startup lacks a durable terminal receipt"
    terminal = json.loads(paths[0].read_text(encoding="utf-8-sig"))
    assert terminal["state"] == "startup_verified"
    assert Path(terminal["python_executable"]).samefile(sys.executable)
    assert terminal["api_pid"] == next(c["Pid"] for c in result["Children"] if c["Role"] == "api")
    assert terminal["watchdog_pid"] == next(c["Pid"] for c in result["Children"] if c["Role"] == "watchdog")
    assert terminal["ongoing_health_verified"] is False


def test_running_store_does_not_require_service_start_rights(launch):
    result = launch("service_already_running")
    assert result["Completed"], result
    assert result["ServiceRequests"] == 0
    assert result["ChildStarts"] == ["api", "watchdog"]


def test_startup_preflight_does_not_start_services_or_children(launch):
    result = launch(check_start=True)
    assert result["Completed"], result
    assert result["ServiceRequests"] == 0, "Preflight started the store service"
    assert result["ChildStarts"] == [], "Preflight launched a workload owner"


def test_stop_current_already_absent_does_not_start_services(launch):
    result = launch(check_start=True)
    with _stop_current(result["sandbox"], result["port"]) as stopper:
        assert stopper.wait(timeout=10) == 0
    assert not (result["sandbox"] / "api.json").exists()
    assert not (result["sandbox"] / "watchdog.json").exists()


def test_foreign_port_collision_refuses_without_stopping_owner(launch, tmp_path):
    marker = tmp_path / "foreign-listener.json"
    code = "import json,socket,sys,time; from pathlib import Path; s=socket.socket(); s.bind(('127.0.0.1',0)); s.listen(); Path(sys.argv[1]).write_text(json.dumps({'port':s.getsockname()[1]})); time.sleep(60)"
    child = subprocess.Popen([sys.executable, "-c", code, str(marker)], creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        _wait_for_file(marker, child)
        port = json.loads(marker.read_text())["port"]
        result = launch(port=port, foreign_pid=child.pid)
        assert child.poll() is None, "Launcher terminated a foreign port owner"
        assert not result["Completed"], result
        assert result["ChildStarts"] == []
        assert result["Failure"]
        paths = list(result["sandbox"].glob("goodq-startup-*/startup.json"))
        assert len(paths) == 1, "Preflight collision has no durable failure receipt"
        terminal = json.loads(paths[0].read_text(encoding="utf-8-sig"))
        assert terminal["state"] == "failed"
        assert terminal["api_pid"] is None
        assert terminal["watchdog_pid"] is None
        assert str(child.pid) in terminal["reason"]
        with _stop_current(result["sandbox"], port) as stopper:
            assert stopper.wait(timeout=10) != 0, "Dev Off accepted an unowned API listener"
        assert child.poll() is None, "Dev Off terminated an unowned API listener"
    finally:
        if child.poll() is None:
            child.terminate()
        child.wait(timeout=5)


def test_os_api_launch_error_blocks_watchdog(launch):
    result = launch("api_launch_error")
    assert not result["Completed"], result
    assert result["ChildStarts"] == ["api"]
    assert result["Failure"]
    assert not any(c["Role"] == "watchdog" for c in result["Children"])


def test_api_exit_before_readiness_blocks_watchdog(launch):
    result = launch("api_early_exit")
    assert not result["Completed"], result
    assert result["ChildStarts"] == ["api"]
    assert "17" in result["Failure"]


def test_watchdog_early_exit_rolls_back_only_owned_api(launch):
    result = launch("watchdog_early_exit")
    assert not result["Completed"], result
    assert "23" in result["Failure"]
    assert not any(c["Alive"] for c in result["Children"]), "Startup rollback left an owned child alive"


def test_listening_api_without_http_health_times_out_and_is_stopped(launch):
    result = launch("api_unhealthy")
    assert not result["Completed"], result
    assert result["ChildStarts"] == ["api"]
    assert result["Failure"]
    assert not any(c["Alive"] for c in result["Children"])


def test_port_takeover_cannot_supply_readiness_for_api_on_fallback_port(launch):
    result = launch("api_fallback")
    own_port = json.loads((result["sandbox"] / "api-bound.json").read_text())["port"]
    foreign_port = json.loads((result["sandbox"] / "foreign-bound.json").read_text())["port"]
    assert own_port != result["port"]
    assert foreign_port == result["port"]
    assert result["intruder_alive_after_startup"], "Launcher stopped the other listener"
    assert not result["Completed"], "Another process's HTTP 200 was accepted as owned API readiness"
    assert result["ChildStarts"] == ["api"]
    assert not any(c["Alive"] for c in result["Children"])


def test_non_core_environment_cannot_fall_back_to_path_python(launch):
    result = launch(conda_env="nonexistent_startup_fixture_environment")
    assert not result["Completed"], "Unknown environment silently fell back to PATH Python"
    assert result["ChildStarts"] == []
    assert result["ServiceRequests"] == 0
    assert "goodq_core" in result["Failure"]


def _supervisor_snapshot(sandbox, process, predicate, timeout=15):
    deadline = time.monotonic() + timeout
    latest = None
    while time.monotonic() < deadline:
        paths = list(sandbox.glob("goodq-startup-*/supervisor.json"))
        if paths:
            try:
                latest = json.loads(paths[0].read_text(encoding="utf-8-sig"))
            except PermissionError as exc:
                # ReplaceFile briefly holds a non-sharing handle. Retry only
                # Windows sharing/access errors, within the same test deadline.
                # Python's CRT-backed open may expose EACCES without winerror.
                if exc.errno != errno.EACCES or exc.winerror not in (None, 5, 32, 33):
                    raise
            else:
                if predicate(latest):
                    return latest
        assert process.poll() is None, f"Launcher exited instead of supervising its children: {latest}"
        time.sleep(0.04)
    pytest.fail(f"Supervisor did not reach the required observed state: {latest}")


def _kill_owned_fixture(sandbox, record):
    child = psutil.Process(record["pid"])
    assert child.environ().get("GOODQ_STARTUP_TEST_ROOT") == str(sandbox)
    assert Path(child.exe()).samefile(sys.executable)
    child.kill()
    child.wait(timeout=5)


def _supervisor_receipts(result):
    directory, = result["sandbox"].glob("goodq-startup-*")
    startup = json.loads((directory / "startup.json").read_text(encoding="utf-8-sig"))
    assert startup["state"] == "startup_verified", "Later supervision rewrote historical startup evidence"
    terminal = json.loads((directory / "supervisor.json").read_text(encoding="utf-8-sig"))
    events = [json.loads(line) for line in (directory / "supervisor.events.jsonl").read_text().splitlines()]
    return terminal, events


def test_supervisor_observes_late_crash_and_preserves_running_peer(launch):
    observed = {}

    def exercise(sandbox, process):
        initial = _supervisor_snapshot(sandbox, process, lambda s: s["state"] == "monitoring")
        sustained = _supervisor_snapshot(sandbox, process, lambda s: s["cycle"] >= initial["cycle"] + 3)
        assert sustained["api"]["responsive"] is True
        assert sustained["watchdog"]["alive"] is True
        assert sustained["model_readiness_verified"] is False
        observed.update(sustained)
        _kill_owned_fixture(sandbox, sustained["api"])

    result = launch(supervise=exercise)
    assert not result["Completed"], "A late API crash was reported as successful supervision"
    terminal, events = _supervisor_receipts(result)
    assert terminal["state"] == "failed"
    assert terminal["api"]["alive"] is False
    assert terminal["watchdog"]["pid"] == observed["watchdog"]["pid"]
    assert any(c["Role"] == "watchdog" and c["Alive"] for c in result["Children"])
    assert result["ChildStarts"] == ["api", "watchdog"]
    assert "restart budget" in terminal["reason"].lower()
    assert any(e["event"] == "child_exit" and e["role"] == "api" for e in events)
    assert set((result["sandbox"] / "http-paths.txt").read_text().splitlines()) == {"/"}


@pytest.mark.parametrize("role", ["api", "watchdog"])
def test_supervisor_restarts_exited_child_with_backoff_and_finite_budget(launch, role):
    peer = "watchdog" if role == "api" else "api"
    identities = []

    def exercise(sandbox, process):
        snapshot = _supervisor_snapshot(sandbox, process, lambda s: s["state"] == "monitoring")
        original_peer = snapshot[peer]["pid"]
        for attempt in range(3):
            identities.append(snapshot[role]["pid"])
            assert snapshot[peer]["pid"] == original_peer
            assert snapshot[peer]["alive"] is True
            _kill_owned_fixture(sandbox, snapshot[role])
            if attempt < 2:
                snapshot = _supervisor_snapshot(sandbox, process, lambda s:
                    s["state"] == "monitoring" and s[role]["restarts"] == attempt + 1
                    and s[role]["pid"] not in identities)

    result = launch(supervise=exercise, max_restarts=2)
    terminal, events = _supervisor_receipts(result)
    assert not result["Completed"]
    assert terminal["state"] == "failed"
    assert terminal[role]["restarts"] == 2
    assert terminal[peer]["restarts"] == 0
    assert len(set(identities)) == 3
    assert result["ChildStarts"].count(role) == 3
    assert result["ChildStarts"].count(peer) == 1
    assert any(c["Role"] == peer and c["Alive"] for c in result["Children"])
    scheduled = [e for e in events if e["event"] == "restart_scheduled" and e["role"] == role]
    restarted = [e for e in events if e["event"] == "child_started" and e["role"] == role]
    assert [e["delay_seconds"] for e in scheduled] == [0.6, 1.2]
    assert len(restarted) == 2
    for waiting, started in zip(scheduled, restarted):
        assert started["elapsed_seconds"] - waiting["elapsed_seconds"] >= waiting["delay_seconds"]
        assert started["pid"] != waiting["pid"]
        assert Path(started["stdout"]).is_file()
        assert Path(started["stderr"]).is_file()
    assert len({e["stdout"] for e in restarted}) == 2, "Restart overwrote the previous attempt's log"


def test_supervisor_records_late_http_failure_and_recovery_without_killing_live_children(launch):
    def exercise(sandbox, process):
        initial = _supervisor_snapshot(sandbox, process, lambda s: s["state"] == "monitoring")
        (sandbox / "api-status.txt").write_text("503")
        degraded = _supervisor_snapshot(sandbox, process, lambda s: s["state"] == "degraded")
        assert degraded["api"]["alive"] and not degraded["api"]["responsive"]
        assert degraded["watchdog"]["alive"]
        assert degraded["api"]["pid"] == initial["api"]["pid"]
        assert degraded["api"]["restarts"] == 0
        (sandbox / "api-status.txt").write_text("200")
        recovered = _supervisor_snapshot(sandbox, process, lambda s: s["state"] == "monitoring")
        assert recovered["api"]["pid"] == initial["api"]["pid"]
        assert recovered["watchdog"]["pid"] == initial["watchdog"]["pid"]
        _kill_owned_fixture(sandbox, recovered["watchdog"])

    result = launch(supervise=exercise)
    terminal, events = _supervisor_receipts(result)
    assert terminal["state"] == "failed"
    assert result["ChildStarts"] == ["api", "watchdog"]
    assert any(c["Role"] == "api" and c["Alive"] for c in result["Children"])
    states = [e["state"] for e in events if e["event"] == "health_changed"]
    assert states[:3] == ["monitoring", "degraded", "monitoring"]


def test_supervisor_restarts_api_that_exits_between_http_response_and_ownership_recheck(launch):
    def exercise(sandbox, process):
        initial = _supervisor_snapshot(sandbox, process, lambda s: s["state"] == "monitoring")
        (sandbox / "exit-after-http.json").write_text(json.dumps({"pid": initial["api"]["pid"]}))
        recovered = _supervisor_snapshot(sandbox, process, lambda s:
            s["state"] == "monitoring" and s["api"]["restarts"] == 1)
        assert recovered["api"]["pid"] != initial["api"]["pid"]
        assert recovered["watchdog"]["pid"] == initial["watchdog"]["pid"]
        _kill_owned_fixture(sandbox, recovered["api"])

    result = launch(supervise=exercise, max_restarts=1)
    terminal, events = _supervisor_receipts(result)
    assert not result["Completed"]
    assert terminal["state"] == "failed"
    assert "restart budget" in terminal["reason"]
    assert len([e for e in events if e["event"] == "child_exit" and e["role"] == "api"]) == 2


def test_supervisor_refuses_foreign_port_owner_during_restart_backoff(launch):
    foreign = []

    def exercise(sandbox, process):
        initial = _supervisor_snapshot(sandbox, process, lambda s: s["state"] == "monitoring")
        _kill_owned_fixture(sandbox, initial["api"])
        marker = sandbox / "restart-foreign.json"
        code = "import json,socket,sys,time; from pathlib import Path; s=socket.socket(); s.bind(('127.0.0.1',int(sys.argv[1]))); s.listen(); Path(sys.argv[2]).write_text(json.dumps({'port':s.getsockname()[1]})); time.sleep(60)"
        port = initial["api_endpoint"].rsplit(":", 1)[1]
        foreign.append(subprocess.Popen([sys.executable, "-c", code, port, str(marker)],
                                        creationflags=subprocess.CREATE_NO_WINDOW))
        _wait_for_file(marker, foreign[0])

    try:
        result = launch(supervise=exercise, max_restarts=1, backoff=2)
        terminal, _ = _supervisor_receipts(result)
        assert not result["Completed"]
        assert foreign[0].poll() is None, "Supervisor killed a foreign listener during restart"
        assert "refusing takeover" in terminal["reason"]
        assert str(foreign[0].pid) in terminal["reason"]
        assert result["ChildStarts"] == ["api", "watchdog"]
        assert any(c["Role"] == "watchdog" and c["Alive"] for c in result["Children"])
    finally:
        for child in foreign:
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=5)


def test_supervisor_observes_both_crashes_during_backoff_and_restores_api_before_watchdog(launch):
    def exercise(sandbox, process):
        initial = _supervisor_snapshot(sandbox, process, lambda s: s["state"] == "monitoring")
        _kill_owned_fixture(sandbox, initial["api"])
        _supervisor_snapshot(sandbox, process, lambda s: s["state"] == "backoff")
        _kill_owned_fixture(sandbox, initial["watchdog"])
        waiting = _supervisor_snapshot(sandbox, process, lambda s:
            not s["watchdog"]["alive"] and s["api"]["restarts"] == 0)
        assert waiting["state"] == "backoff"
        recovered = _supervisor_snapshot(sandbox, process, lambda s:
            s["state"] == "monitoring" and s["api"]["restarts"] == s["watchdog"]["restarts"] == 1)
        _kill_owned_fixture(sandbox, recovered["api"])

    result = launch(supervise=exercise, max_restarts=1, backoff=2)
    assert not result["Completed"]
    assert result["ChildStarts"] == ["api", "watchdog", "api", "watchdog"]
    terminal, events = _supervisor_receipts(result)
    exits = [e for e in events if e["event"] == "child_exit"]
    restarts = [e for e in events if e["event"] == "child_started"]
    assert [e["role"] for e in exits[:2]] == ["api", "watchdog"]
    assert exits[1]["elapsed_seconds"] < restarts[0]["elapsed_seconds"]
    assert terminal["watchdog"]["alive"]


@pytest.mark.parametrize("permanent", [False, True])
def test_supervisor_receipt_reader_contention_is_bounded_and_visible(launch, permanent):
    def exercise(sandbox, process):
        initial = _supervisor_snapshot(sandbox, process, lambda s: s["state"] == "monitoring")
        path, = sandbox.glob("goodq-startup-*/supervisor.json")
        deadline = time.monotonic() + 5
        while True:
            try:
                reader = path.open("rb")
                break
            except PermissionError:
                assert time.monotonic() < deadline, "Could not acquire test-owned reader lock"
                time.sleep(0.02)
        with reader:
            while not path.with_suffix(".json.tmp").exists():
                assert time.monotonic() < deadline, "Supervisor never attempted the next receipt publication"
                assert process.poll() is None
                time.sleep(0.01)
            if permanent:
                # Normal publication and its terminal-failure receipt each have
                # a bounded retry. Neither may hang supervision indefinitely.
                process.wait(timeout=8)
            else:
                time.sleep(0.15)
        if not permanent:
            continued = _supervisor_snapshot(sandbox, process, lambda s:
                s["cycle"] > initial["cycle"] and s["state"] == "monitoring")
            _kill_owned_fixture(sandbox, continued["api"])

    result = launch(supervise=exercise)
    assert not result["Completed"]
    console = (result["sandbox"] / "harness-console.log").read_text(errors="replace")
    assert "Receipt replacement temporarily blocked" in console
    if permanent:
        assert "Could not persist supervisor failure" in console
        assert "Replace" in result["Failure"]
        assert {c["Role"] for c in result["Children"] if c["Alive"]} == {"api", "watchdog"}
    else:
        terminal, _ = _supervisor_receipts(result)
        assert "restart budget" in terminal["reason"]


def _request_stop(sandbox, receipt=None):
    if receipt is None:
        receipt, = sandbox.glob("goodq-startup-*/supervisor.json")
    data = json.loads(receipt.read_text(encoding="utf-8-sig"))
    env = {key: value for key, value in os.environ.items() if key.casefold() != "psmodulepath"}
    env["PSMODULEPATH"] = str(Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/Modules")
    env["GOODQ_STARTUP_TEST_PYTHON"] = sys.executable
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-File", str(sandbox / "start_goodq_dev.ps1"), "-StopReceipt", str(receipt),
         "-ApiPort", data["api_endpoint"].rsplit(":", 1)[1]],
        env=env, capture_output=True, text=True, timeout=8, creationflags=subprocess.CREATE_NO_WINDOW,
    )


def _stop_current(sandbox, port, timeout=3, action="StopCurrent"):
    """Run the real stop caller; only the unrelated machine process scan is scoped."""
    harness = sandbox / "stop-current-harness.ps1"
    harness.write_text(
        "param($Script, [int]$Port, [double]$Timeout, $Action)\n"
        "function Get-CimInstance { param($ClassName,$Filter) }\n"
        "function Start-Service { param($Name); throw 'Unexpected service action in a stop/preflight control' }\n"
        "$arguments=@{ApiPort=$Port;DrainTimeoutSeconds=$Timeout}; $arguments[$Action]=$true\n"
        "& $Script @arguments\n",
        encoding="utf-8-sig",
    )
    env = {k: v for k, v in os.environ.items() if k.casefold() != "psmodulepath"}
    env.update(TEMP=str(sandbox), TMP=str(sandbox), GOODQ_STARTUP_TEST_PYTHON=sys.executable)
    env["PSMODULEPATH"] = str(Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/Modules")
    log = (sandbox / "stop-current.log").open("wb")
    try:
        return subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", str(harness), "-Script", str(sandbox / "start_goodq_dev.ps1"),
             "-Port", str(port), "-Timeout", str(timeout), "-Action", action],
            env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW,
        )
    finally:
        log.close()


@pytest.mark.parametrize("newer_stale_receipt", [False, True])
def test_stop_current_discovers_owner_and_waits_for_verified_drain(launch, newer_stale_receipt):
    def exercise(sandbox, process):
        initial = _supervisor_snapshot(sandbox, process, lambda s: s["state"] == "monitoring")
        if newer_stale_receipt:
            stale = dict(initial, stop_event="Local\\GoodQRuntime-" + "0" * 32)
            directory = sandbox / "goodq-startup-stale"
            directory.mkdir()
            (directory / "supervisor.json").write_text(json.dumps(stale), encoding="utf-8")
        port = int(initial["api_endpoint"].rsplit(":", 1)[1])
        with _stop_current(sandbox, port) as stopper:
            try:
                _wait_for_file(sandbox / "drain-requested.json", stopper, seconds=8)
                assert stopper.poll() is None, "Stop caller returned before active work drained"
                assert not (sandbox / "work-completed.json").exists()
                (sandbox / "release-work").touch()
                assert stopper.wait(timeout=10) == 0, (sandbox / "stop-current.log").read_text(errors="replace")
                snapshots = [json.loads(p.read_text(encoding="utf-8-sig")) for p in sandbox.glob("goodq-startup-*/supervisor.json")]
                terminal = next(s for s in snapshots if s["stop_event"] == initial["stop_event"])
                assert terminal["state"] == "stopped" and terminal["drain_verified"] is True
                assert not terminal["api"]["alive"] and not terminal["watchdog"]["alive"]
            finally:
                if stopper.poll() is None:
                    stopper.kill()
                    stopper.wait(timeout=5)

    result = launch("active_work", supervise=exercise, max_restarts=2, drain_timeout=12)
    assert result["Completed"], result
    assert result["ChildStarts"] == ["api", "watchdog"]


def test_stop_current_timeout_preserves_busy_owner_and_returns_failure(launch):
    def exercise(sandbox, process):
        initial = _supervisor_snapshot(sandbox, process, lambda s: s["state"] == "monitoring")
        with _stop_current(sandbox, int(initial["api_endpoint"].rsplit(":", 1)[1]), timeout=.5) as stopper:
            assert stopper.wait(timeout=10) != 0
        assert (sandbox / "drain-requested.json").exists(), "Caller never requested the owning runtime to drain"
        child = psutil.Process(initial["watchdog"]["pid"])
        assert child.environ()["GOODQ_STARTUP_TEST_ROOT"] == str(sandbox)
        assert child.is_running() and not (sandbox / "work-completed.json").exists()
        (sandbox / "release-work").touch()

    result = launch("active_work", supervise=exercise, drain_timeout=12)
    assert result["Completed"], result


def test_stop_current_does_not_claim_absence_during_double_child_backoff(launch):
    def exercise(sandbox, process):
        initial = _supervisor_snapshot(sandbox, process, lambda s: s["state"] == "monitoring")
        _kill_owned_fixture(sandbox, initial["api"])
        _kill_owned_fixture(sandbox, initial["watchdog"])
        waiting = _supervisor_snapshot(sandbox, process, lambda s:
            s["state"] == "backoff" and not s["api"]["alive"] and not s["watchdog"]["alive"])
        port = int(waiting["api_endpoint"].rsplit(":", 1)[1])
        with _stop_current(sandbox, port) as stopper:
            assert stopper.wait(timeout=5) != 0, "Armed supervisor was mistaken for an absent runtime"
        with _stop_current(sandbox, port, action="CheckStart") as checker:
            assert checker.wait(timeout=5) != 0, "Dev On accepted another supervisor during backoff"
        assert process.poll() is None, "The active supervisor was terminated"
        _supervisor_snapshot(sandbox, process, lambda s: s["state"] == "monitoring" and s["api"]["restarts"] == 1)
        assert _request_stop(sandbox).returncode == 0

    result = launch(supervise=exercise, max_restarts=1, backoff=8)
    assert result["Completed"], result


def test_stop_current_does_not_claim_absence_before_the_first_child_starts(launch):
    def exercise(sandbox, process):
        _wait_for_file(sandbox / "awaiting-store.json", process)
        port = json.loads((sandbox / "awaiting-store.json").read_text(encoding="utf-8-sig"))
        with _stop_current(sandbox, port) as stopper:
            assert stopper.wait(timeout=5) != 0, "Starting owner was mistaken for an absent runtime"
        with _stop_current(sandbox, port, action="CheckStart") as checker:
            assert checker.wait(timeout=5) != 0, "Dev On accepted another starting owner"
        assert not (sandbox / "api.json").exists()
        (sandbox / "release-store").touch()
        _supervisor_snapshot(sandbox, process, lambda s: s["state"] == "monitoring")
        assert _request_stop(sandbox).returncode == 0

    result = launch("startup_owner_wait", supervise=exercise)
    assert result["Completed"], result


def test_external_stop_freezes_restarts_and_waits_for_active_work(launch):
    def exercise(sandbox, process):
        initial = _supervisor_snapshot(sandbox, process, lambda s: s["state"] == "monitoring")
        assert _request_stop(sandbox).returncode == 0, "launcher has no external stop control"
        _wait_for_file(sandbox / "drain-requested.json", process)
        stopping = _supervisor_snapshot(sandbox, process, lambda s: s["state"] == "stopping")
        assert stopping["watchdog"]["pid"] == initial["watchdog"]["pid"]
        assert stopping["watchdog"]["alive"]
        assert not (sandbox / "work-completed.json").exists()
        (sandbox / "release-work").touch()

    result = launch("active_work", supervise=exercise, max_restarts=2)
    terminal, events = _supervisor_receipts(result)
    assert result["Completed"], result
    assert terminal["state"] == "stopped"
    assert terminal["drain_verified"] is True
    assert not any(c["Alive"] for c in result["Children"])
    assert (result["sandbox"] / "work-completed.json").exists()
    assert result["ChildStarts"] == ["api", "watchdog"]
    assert not any(e["event"] == "restart_scheduled" for e in events)


def test_drain_timeout_preserves_busy_child_and_does_not_claim_completion(launch):
    def exercise(sandbox, process):
        _supervisor_snapshot(sandbox, process, lambda s: s["state"] == "monitoring")
        assert _request_stop(sandbox).returncode == 0, "launcher has no external stop control"
        _wait_for_file(sandbox / "drain-requested.json", process)

    result = launch("active_work", supervise=exercise, max_restarts=2, drain_timeout=.7)
    terminal, _ = _supervisor_receipts(result)
    assert not result["Completed"]
    assert terminal["state"] == "failed"
    assert terminal["drain_verified"] is False
    assert "drain" in terminal["reason"].lower() and "timed out" in terminal["reason"].lower()
    assert any(c["Role"] == "watchdog" and c["Alive"] for c in result["Children"])
    assert not (result["sandbox"] / "work-completed.json").exists()
    assert result["ChildStarts"] == ["api", "watchdog"]


def test_startup_failure_drains_work_that_started_in_the_startup_window(launch):
    def exercise(sandbox, process):
        _wait_for_file(sandbox / "active-work.json", process)
        _wait_for_file(sandbox / "drain-requested.json", process)
        assert not (sandbox / "work-completed.json").exists()
        (sandbox / "release-work").touch()

    result = launch("startup_active_work", supervise=exercise)
    assert not result["Completed"], "initial API health failure must remain visible"
    assert "API lost startup health" in result["Failure"]
    assert (result["sandbox"] / "work-completed.json").exists(), "startup rollback killed active work"
    assert not any(c["Alive"] for c in result["Children"])
    receipt, = result["sandbox"].glob("goodq-startup-*/startup.json")
    assert json.loads(receipt.read_text(encoding="utf-8-sig"))["drain_verified"] is True


def test_restart_waits_for_old_job_to_empty_before_replacement(launch):
    import ctypes
    from ctypes import wintypes
    from tests.unit.test_runtime_lifecycle import is_alive, wait_until

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenJobObjectW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.OpenJobObjectW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]

    def exercise(sandbox, process):
        initial = _supervisor_snapshot(sandbox, process, lambda s: s["state"] == "monitoring")
        wait_until(lambda: bool(list(sandbox.glob("leaf-*.json"))))
        leaf_path, = sandbox.glob("leaf-*.json")
        leaf = json.loads(leaf_path.read_text())
        job = kernel.OpenJobObjectW(4, False, f"{initial['stop_event']}.watchdog.{initial['watchdog']['pid']}")
        assert job, "test could not hold the real job open"
        try:
            _kill_owned_fixture(sandbox, initial["watchdog"])
            waiting = _supervisor_snapshot(sandbox, process, lambda s: s["cycle"] >= initial["cycle"] + 4)
            assert is_alive(leaf), "fixture did not retain the descendant through the last job handle"
            assert waiting["watchdog"]["restarts"] == 0, "replacement overlaps an old live descendant"
        finally:
            kernel.CloseHandle(job)
        recovered = _supervisor_snapshot(sandbox, process, lambda s:
            s["state"] == "monitoring" and s["watchdog"]["restarts"] == 1)
        assert not is_alive(leaf)
        assert recovered["api"]["pid"] == initial["api"]["pid"]
        assert _request_stop(sandbox).returncode == 0

    result = launch("owned_descendant", supervise=exercise, max_restarts=1, backoff=.1)
    terminal, events = _supervisor_receipts(result)
    assert result["Completed"], result
    assert terminal["state"] == "stopped"
    emptied = next(e for e in events if e["event"] == "descendants_exited" and e["role"] == "watchdog")
    restarted = next(e for e in events if e["event"] == "child_started" and e["role"] == "watchdog")
    assert emptied["elapsed_seconds"] < restarted["elapsed_seconds"]


def test_stop_receipt_rejects_a_reused_pid_identity(launch):
    def exercise(sandbox, process):
        initial = _supervisor_snapshot(sandbox, process, lambda s: s["state"] == "monitoring")
        initial["api"]["started_at_utc"] = "2000-01-01T00:00:00Z"
        tampered = sandbox / "stale-receipt.json"
        tampered.write_text(json.dumps(initial))
        rejected = _request_stop(sandbox, tampered)
        assert rejected.returncode != 0
        assert "identity no longer matches" in rejected.stderr
        current = _supervisor_snapshot(sandbox, process, lambda s: s["cycle"] > initial["cycle"])
        assert current["state"] == "monitoring"
        assert _request_stop(sandbox).returncode == 0

    result = launch(supervise=exercise)
    assert result["Completed"], result


def test_supervised_readiness_requires_the_child_to_own_its_lifecycle(launch):
    def exercise(sandbox, process):
        _wait_for_file(sandbox / "api.json", process)
        try:
            process.wait(timeout=6)
        except subprocess.TimeoutExpired:
            # Let a broken guard finish normally so the final assertion tests
            # its decision, not a test-harness timeout.
            _kill_owned_fixture(sandbox, json.loads((sandbox / "api.json").read_text()))

    result = launch("missing_lifecycle", supervise=exercise, drain_timeout=.5)
    assert not result["Completed"]
    assert "lifecycle ownership" in result["Failure"].lower()
    assert result["ChildStarts"] == ["api"]


def test_stop_receipt_cannot_substitute_an_unrelated_event(launch):
    import ctypes
    from ctypes import wintypes
    import uuid
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateEventW.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]

    def exercise(sandbox, process):
        initial = _supervisor_snapshot(sandbox, process, lambda s: s["state"] == "monitoring")
        name = "Local\\GoodQRuntime-" + uuid.uuid4().hex
        event = kernel.CreateEventW(None, True, False, name)
        assert event
        try:
            initial["stop_event"] = name
            tampered = sandbox / "mismatched-event.json"
            tampered.write_text(json.dumps(initial))
            rejected = _request_stop(sandbox, tampered)
            assert rejected.returncode != 0, "receipt redirected stop to an unrelated event"
            assert kernel.WaitForSingleObject(event, 0) == 258
        finally:
            kernel.CloseHandle(event)
            assert _request_stop(sandbox).returncode == 0

    result = launch(supervise=exercise)
    assert result["Completed"], result


def test_real_launcher_watchdog_crash_recovery_and_external_drain(launch):
    from tests.unit.test_runtime_lifecycle import completed, is_alive

    def exercise(sandbox, process):
        initial = _supervisor_snapshot(sandbox, process, lambda s: s["state"] == "monitoring")
        _wait_for_file(sandbox / "transaction.json", process)
        old_workers = [json.loads((sandbox / (name + ".json")).read_text()) for name in ("step", "transaction")]
        assert completed(sandbox) == []
        _kill_owned_fixture(sandbox, initial["watchdog"])
        recovered = _supervisor_snapshot(sandbox, process, lambda s:
            s["state"] == "monitoring" and s["watchdog"]["restarts"] == 1)
        assert not any(is_alive(identity) for identity in old_workers)
        assert completed(sandbox) == [], "crashed owner committed partial work"
        assert recovered["api"]["pid"] == initial["api"]["pid"]
        _wait_for_file(sandbox / "transaction.json", process)
        current = json.loads((sandbox / "transaction.json").read_text())
        assert current["pid"] != old_workers[1]["pid"] and is_alive(current)
        requested = _request_stop(sandbox)
        assert requested.returncode == 0, requested.stderr
        _wait_for_file(sandbox / "producer-stopped.json", process)
        assert completed(sandbox) == []
        (sandbox / "release").touch()

    result = launch("real_work", supervise=exercise, max_restarts=1, drain_timeout=5)
    terminal, _ = _supervisor_receipts(result)
    assert result["Completed"], result
    assert terminal["state"] == "stopped" and terminal["drain_verified"]
    assert completed(result["sandbox"]) == ["active", "last-producer-item"]
    assert result["ChildStarts"] == ["api", "watchdog", "watchdog"]


def test_supervisor_crash_preserves_work_and_receipt_bound_stop_still_reaches_owners(launch):
    from tests.unit.test_runtime_lifecycle import completed, is_alive, wait_until

    def exercise(sandbox, process):
        initial = _supervisor_snapshot(sandbox, process, lambda s: s["state"] == "monitoring")
        _wait_for_file(sandbox / "transaction.json", process)
        owners = [{"pid": initial[role]["pid"], "birth": psutil.Process(initial[role]["pid"]).create_time()}
                  for role in ("api", "watchdog")]
        process.kill()
        process.wait(timeout=5)
        assert all(is_alive(owner) for owner in owners), "supervisor crash abandoned live work"
        assert completed(sandbox) == []
        receipt_path, = sandbox.glob("goodq-startup-*/supervisor.json")
        stale = receipt_path.read_bytes()
        requested = _request_stop(sandbox)
        assert requested.returncode == 0, requested.stderr
        wait_until(lambda: (sandbox / "producer-stopped.json").is_file())
        assert completed(sandbox) == []
        (sandbox / "release").touch()
        wait_until(lambda: not any(is_alive(owner) for owner in owners))
        assert completed(sandbox) == ["active", "last-producer-item"]
        assert receipt_path.read_bytes() == stale, "dead writer cannot attest current health or drain"

    result = launch("supervisor_crash", supervise=exercise)
    assert result["shell_exit"] != 0
