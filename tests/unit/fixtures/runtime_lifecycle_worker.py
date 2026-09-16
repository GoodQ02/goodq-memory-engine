"""Real entrypoints and OS children; only workload/config use isolated fixtures."""
import asyncio
import json
import importlib.util
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from types import ModuleType

import psutil

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
# A launcher witness begins under its isolated package shim. Imports after this
# point must resolve the real repair entrypoints, including on a restarted role.
for package in ("api", "cli"):
    if package in sys.modules:
        sys.modules[package].__path__ = [str(REPO / package)]
oracle_source = os.environ.get("GOODQ_LIFECYCLE_TEST_SOURCE")
if oracle_source:
    spec = importlib.util.spec_from_file_location("steps.common.runtime_lifecycle", oracle_source)
    oracle_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = oracle_module
    spec.loader.exec_module(oracle_module)
ROOT = Path(os.environ["GOODQ_LIFECYCLE_TEST_ROOT"])
ROLE = sys.argv[1]


def record(name, data):
    target = ROOT / (name + ".json")
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(data), encoding="utf-8")
    temporary.replace(target)


def identity():
    return {"pid": os.getpid(), "birth": psutil.Process().create_time()}


def wait_release():
    deadline = time.monotonic() + 45
    while not (ROOT / "release").exists():
        if time.monotonic() >= deadline:
            raise TimeoutError("fixture work was not released")
        time.sleep(.025)


if ROLE == "transaction":
    with sqlite3.connect(ROOT / "work.sqlite") as database:
        database.execute("INSERT INTO completed VALUES ('active')")
        record("transaction", identity())
        wait_release()
    sys.exit(0)

if ROLE == "step":
    child = subprocess.Popen([sys.executable, __file__, "transaction"])
    record("step", identity())
    sys.exit(child.wait(timeout=50))

record("owner", identity())
record(ROLE, dict(identity(), executable=sys.executable, cwd=os.getcwd(),
                  host=os.environ.get("GOODQ_API_HOST"), port=os.environ.get("GOODQ_API_PORT")))

if ROLE == "watchdog":
    import cli.watchdog as watchdog
    from tests.unit.test_watchdog_processed_prefix_idempotent import _watchdog_cfg

    cfg = _watchdog_cfg(ROOT)
    watchdog.load_configs = lambda _: cfg
    watchdog.CONTROL_AGENT_AVAILABLE = False
    watchdog.MAX_WORKERS = 1
    watchdog._check_system_restart_events = lambda: None
    original_init = watchdog.WatchdogProcessor.__init__

    def initialize(self, config, **kwargs):
        original_init(self, config, **kwargs)
        self.queue.put((Path("active.mp4"), "active-hash"))

    def process(self, path, _hash):
        if path.name == "active.mp4":
            child = subprocess.Popen([sys.executable, __file__, "step"])
            assert child.wait(timeout=50) == 0
        else:
            with sqlite3.connect(ROOT / "work.sqlite") as database:
                database.execute("INSERT INTO completed VALUES ('last-producer-item')")

    def monitor(self):
        assert self.shutdown.wait(45)
        self.queue.put((Path("last.mp4"), "last-hash"))
        record("producer-stopped", identity())

    watchdog.WatchdogProcessor.__init__ = initialize
    watchdog.WatchdogProcessor.process_file = process
    watchdog.WatchdogProcessor.monitor_loop = monitor
    watchdog.main()
elif ROLE == "api":
    import api.server as server

    async def app(scope, receive, send):
        if scope["type"] == "lifespan":
            while True:
                event = await receive()
                if event["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                else:
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        if scope["path"] == "/work":
            child = await asyncio.create_subprocess_exec(sys.executable, __file__, "step")
            assert await child.wait() == 0
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"complete"})

    module = ModuleType("api.main")
    module.app = app
    sys.modules["api.main"] = module
    server._resolve_api_bind_defaults = lambda: ("127.0.0.1", int(os.environ["GOODQ_API_PORT"]))
    server.main()
else:
    raise ValueError(ROLE)
record("owner-finished", identity())
