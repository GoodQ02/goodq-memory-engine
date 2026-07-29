from pathlib import Path

import pytest


def _plan() -> dict:
    return {"status": "ready", "processing_root": "unused", "batch_index": 1, "batch_size": 10, "scene_count": 1}


def test_serial_runner_rebuilds_the_immediate_next_plan_and_audits_each_batch(tmp_path: Path) -> None:
    from cli.signature_backfill_serial_run import run_serial

    calls: list[str] = []
    def executor(plan: dict, token: str) -> dict:
        calls.append(token)
        return {"status": "fake", "batch_root": str(tmp_path)}

    result = run_serial(tmp_path, max_batches=2, plan_builder=lambda _: _plan(), batch_executor=executor, auditor=lambda _: {"status": "audited"})

    assert result["status"] == "committed"
    assert len(result["completed_batches"]) == 2
    assert len(calls) == 2


def test_serial_runner_stops_when_an_audit_fails(tmp_path: Path) -> None:
    from cli.signature_backfill_serial_run import SerialRunError, run_serial

    with pytest.raises(SerialRunError, match="stopped after 0 audited batches"):
        run_serial(tmp_path, max_batches=1, plan_builder=lambda _: _plan(), batch_executor=lambda *_: {"status": "fake"}, auditor=lambda _: (_ for _ in ()).throw(SerialRunError("audit failed")))
