"""Fallback audit writes must survive real, independent Windows file handles."""
import json
import os
from pathlib import Path
import subprocess
import sys


def test_independent_process_fallback_writers_preserve_every_record(tmp_path):
    worker = r'''
import sys, time
from pathlib import Path
from steps.common.retrieval_events import RetrievalEvent, RetrievalEventPolicy, _emit_jsonl_fallback
root=Path(sys.argv[1]); identity=sys.argv[2]
policy=RetrievalEventPolicy(enabled=True,jsonl_fallback=True,log_dir=str(root))
(root/(identity+'.ready')).touch()
deadline=time.monotonic()+15
while not (root/'go').exists():
    if time.monotonic()>deadline: raise RuntimeError('start barrier timed out')
    time.sleep(.01)
for i in range(120):
    event=RetrievalEvent(ts_utc='2026-09-16T00:00:00Z',store='qdrant',embedding_id=identity+'-'+str(i))
    if not _emit_jsonl_fallback([event],policy=policy):raise RuntimeError('fallback failed')
'''
    repo = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    processes = [subprocess.Popen([sys.executable, "-B", "-c", worker, str(tmp_path), str(i)],
                                 cwd=repo, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                 for i in range(4)]
    import time
    deadline = time.monotonic() + 15
    try:
        while len(list(tmp_path.glob("*.ready"))) != len(processes):
            assert time.monotonic() < deadline, "workers failed to reach start barrier"
            time.sleep(.01)
        (tmp_path / "go").touch()
        for process in processes:
            _, error = process.communicate(timeout=20)
            assert process.returncode == 0, error.decode(errors="replace")
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
    rows = [json.loads(line) for line in (tmp_path / "retrieval_events.jsonl").read_text().splitlines()]
    expected = {f"{worker}-{index}" for worker in range(4) for index in range(120)}
    assert len(rows) == len(expected)
    assert {row["embedding_id"] for row in rows} == expected
