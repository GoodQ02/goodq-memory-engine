from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path

import pytest

from api.utils import temporal_summary_results
from api.utils.temporal_summary_results import (
    TemporalSummaryResultConflict,
    TemporalSummaryResultRecoveryError,
    TemporalSummaryResultStore,
)


JOB_ID = "job_" + "a" * 32
EPOCH_ID = "epoch_2026_07_family"
REQUEST_SHA256 = "b" * 64
POLICY_SHA256 = "c" * 64


def _success_result() -> dict:
    return {
        "summary": "A concise grounded account.",
        "segments": [
            {
                "scene_index": 1,
                "scene_id": "scene_0001",
                "text": "A grounded scene account.",
                "start_time": 1.25,
                "end_time": 4.5,
            }
        ],
        "source_scene_ids": ["scene_0001"],
        "source_count": 1,
        "truncated": False,
        "warning_codes": [],
    }


def _write_success(store: TemporalSummaryResultStore, **overrides) -> dict:
    arguments = {
        "job_id": JOB_ID,
        "epoch_id": EPOCH_ID,
        "request_sha256": REQUEST_SHA256,
        "execution_policy_sha256": POLICY_SHA256,
        "started_at_utc": "2026-07-13T05:59:00+00:00",
        "result": _success_result(),
        "model_evidence": {
            "model_id": "Llama3.2-Ollama",
            "provider": "ollama",
        },
    }
    arguments.update(overrides)
    return store.write_success(**arguments)


def test_absent_exact_job_read_is_passive(tmp_path: Path) -> None:
    root = tmp_path / "absent" / "temporal-results"
    store = TemporalSummaryResultStore(root)

    assert store.load(JOB_ID) is None
    assert not root.exists()


def test_success_record_is_strict_digest_bound_and_exactly_reloadable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        temporal_summary_results,
        "_utc_now_iso",
        lambda: "2026-07-13T06:00:00+00:00",
    )
    store = TemporalSummaryResultStore(tmp_path / "results")

    record = _write_success(store)

    assert set(record) == {
        "schema",
        "job_id",
        "epoch_id",
        "request_sha256",
        "execution_policy_sha256",
        "started_at_utc",
        "completed_at_utc",
        "terminal_state",
        "result",
        "error_code",
        "model_evidence",
        "result_sha256",
    }
    assert record["schema"] == "goodq.temporal-summary-result.v1"
    assert record["terminal_state"] == "succeeded"
    assert record["error_code"] is None
    assert record["started_at_utc"] == "2026-07-13T05:59:00+00:00"
    assert record["completed_at_utc"] == "2026-07-13T06:00:00+00:00"
    assert record["model_evidence"] == {
        "model_id": "Llama3.2-Ollama",
        "provider": "ollama",
    }
    assert record["result"] == _success_result()
    assert store.load(JOB_ID) == record
    assert store.load_exact(
        job_id=JOB_ID,
        epoch_id=EPOCH_ID,
        request_sha256=REQUEST_SHA256,
        execution_policy_sha256=POLICY_SHA256,
    ) == record
    assert temporal_summary_results.result_record_sha256(record) == record[
        "result_sha256"
    ]


def test_failure_record_contains_only_sanitized_error_code(tmp_path: Path) -> None:
    store = TemporalSummaryResultStore(tmp_path / "results")

    record = store.write_failure(
        job_id=JOB_ID,
        epoch_id=EPOCH_ID,
        request_sha256=REQUEST_SHA256,
        execution_policy_sha256=POLICY_SHA256,
        started_at_utc="2026-07-13T05:59:00+00:00",
        error_code="model_unavailable",
    )

    assert record["terminal_state"] == "failed"
    assert record["result"] is None
    assert record["error_code"] == "model_unavailable"
    assert record["model_evidence"] is None
    serialized = json.dumps(record)
    assert "traceback" not in serialized.lower()
    assert "source_file" not in serialized


@pytest.mark.parametrize(
    "mutate",
    [
        lambda result: result.update({"query": {"entities": ["private"]}}),
        lambda result: result["segments"][0].update(
            {"source_file": "private-source.mp4"}
        ),
        lambda result: result.update({"warnings": ["raw failure detail"]}),
        lambda result: result.update({"warning_codes": ["raw error: private"]}),
    ],
)
def test_success_write_rejects_raw_request_path_or_error_surfaces(
    tmp_path: Path,
    mutate,
) -> None:
    store = TemporalSummaryResultStore(tmp_path / "results")
    result = _success_result()
    mutate(result)

    with pytest.raises(ValueError):
        _write_success(store, result=result)

    assert not (tmp_path / "results").exists()


@pytest.mark.parametrize(
    "private_text",
    [
        "/mnt/l/private/source.mp4",
        "/home/operator/private/source.mp4",
        "file:///private/source.mp4",
        "http://127.0.0.1:30000/private",
        "source=/mnt/l/private/source.mp4",
        "(/home/operator/private/source.mp4)",
        "[source](file:///private/source.mp4)",
    ],
)
def test_success_write_rejects_posix_uri_or_endpoint_path_detail(
    tmp_path: Path,
    private_text: str,
) -> None:
    store = TemporalSummaryResultStore(tmp_path / "results")
    result = _success_result()
    result["segments"][0]["text"] = private_text

    with pytest.raises(ValueError, match="path detail"):
        _write_success(store, result=result)

    assert not (tmp_path / "results").exists()


def test_success_write_rejects_unsafe_model_evidence_or_inconsistent_sources(
    tmp_path: Path,
) -> None:
    store = TemporalSummaryResultStore(tmp_path / "results")
    result = _success_result()
    result["source_count"] = 2

    with pytest.raises(ValueError):
        _write_success(store, result=result)
    with pytest.raises(ValueError):
        _write_success(
            store,
            model_evidence={
                "model_id": "C:\\private\\model",
                "provider": "ollama",
            },
        )

    assert not (tmp_path / "results").exists()


def test_success_requires_grounding_unless_no_match_is_explicit(tmp_path: Path) -> None:
    store = TemporalSummaryResultStore(tmp_path / "results")
    ungrounded = _success_result()
    ungrounded.update(
        {
            "segments": [],
            "source_scene_ids": [],
            "source_count": 0,
        }
    )

    with pytest.raises(ValueError, match="grounding"):
        _write_success(store, result=ungrounded, model_evidence=None)

    ungrounded["warning_codes"] = ["no_matching_scenes"]
    record = _write_success(store, result=ungrounded, model_evidence=None)
    assert record["terminal_state"] == "succeeded"
    assert record["result"]["warning_codes"] == ["no_matching_scenes"]


@pytest.mark.parametrize("invalid_index", [2, 0])
def test_segments_must_bind_unique_source_order(
    tmp_path: Path,
    invalid_index: int,
) -> None:
    store = TemporalSummaryResultStore(tmp_path / "results")
    result = _success_result()
    result["segments"][0]["scene_index"] = invalid_index

    with pytest.raises(ValueError, match="scene index|source order"):
        _write_success(store, result=result)

    assert not (tmp_path / "results").exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("epoch_id", "../epoch"),
        ("request_sha256", "not-a-digest"),
        ("execution_policy_sha256", "D" * 64),
    ],
)
def test_write_rejects_invalid_binding_without_creating_store(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    store = TemporalSummaryResultStore(tmp_path / "results")

    with pytest.raises(ValueError):
        _write_success(store, **{field: value})

    assert not (tmp_path / "results").exists()


def test_invalid_or_traversal_job_ids_are_rejected_without_reads(
    tmp_path: Path,
) -> None:
    store = TemporalSummaryResultStore(tmp_path / "results")

    for invalid in ("job_short", "../outside", "..\\outside", "C:\\outside"):
        with pytest.raises(ValueError, match="job ID"):
            store.load(invalid)

    assert not (tmp_path / "results").exists()


def test_exact_load_rejects_mismatched_scope_without_mutating_record(
    tmp_path: Path,
) -> None:
    store = TemporalSummaryResultStore(tmp_path / "results")
    record = _write_success(store)
    before = store.record_path(JOB_ID).read_bytes()

    with pytest.raises(TemporalSummaryResultConflict, match="binding"):
        store.load_exact(
            job_id=JOB_ID,
            epoch_id=EPOCH_ID,
            request_sha256="d" * 64,
            execution_policy_sha256=POLICY_SHA256,
        )

    assert store.load(JOB_ID) == record
    assert store.record_path(JOB_ID).read_bytes() == before


def test_malformed_or_digest_tampered_record_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "results"
    root.mkdir()
    path = root / f"{JOB_ID}.json"
    malformed = b"{not-json"
    path.write_bytes(malformed)
    store = TemporalSummaryResultStore(root)

    with pytest.raises(RuntimeError, match="malformed"):
        store.load(JOB_ID)
    assert path.read_bytes() == malformed

    path.unlink()
    record = _write_success(store)
    tampered = deepcopy(record)
    tampered["result"]["summary"] = "Changed after digest."
    path.write_text(json.dumps(tampered), encoding="utf-8")
    tampered_bytes = path.read_bytes()

    with pytest.raises(RuntimeError, match="digest"):
        store.load(JOB_ID)
    assert path.read_bytes() == tampered_bytes


def test_concurrent_exact_writes_converge_and_conflict_is_immutable(
    tmp_path: Path,
) -> None:
    root = tmp_path / "results"

    def write_exact(_index: int) -> dict:
        return _write_success(TemporalSummaryResultStore(root))

    with ThreadPoolExecutor(max_workers=8) as executor:
        records = list(executor.map(write_exact, range(16)))

    assert len({record["result_sha256"] for record in records}) == 1
    assert len(list(root.glob("job_*.json"))) == 1
    authoritative = (root / f"{JOB_ID}.json").read_bytes()
    changed = _success_result()
    changed["summary"] = "A different result."

    with pytest.raises(TemporalSummaryResultConflict, match="immutable"):
        _write_success(TemporalSummaryResultStore(root), result=changed)

    assert (root / f"{JOB_ID}.json").read_bytes() == authoritative


def test_replace_failure_leaves_no_record_or_owned_temp(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "results"
    store = TemporalSummaryResultStore(root)
    monkeypatch.setattr(
        temporal_summary_results.os,
        "replace",
        lambda *_args: (_ for _ in ()).throw(OSError("simulated replace failure")),
    )

    with pytest.raises(RuntimeError, match="persist"):
        _write_success(store)

    assert not store.record_path(JOB_ID).exists()
    assert list(root.glob(f"{JOB_ID}.json.tmp-*")) == []


def test_failed_post_replace_inspection_removes_untrusted_first_write(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "results"
    store = TemporalSummaryResultStore(root)
    real_replace = temporal_summary_results.os.replace

    def replace_then_corrupt(source, destination):
        real_replace(source, destination)
        Path(destination).write_text("{", encoding="utf-8")

    monkeypatch.setattr(temporal_summary_results.os, "replace", replace_then_corrupt)

    with pytest.raises(RuntimeError, match="persist"):
        _write_success(store)

    assert not store.record_path(JOB_ID).exists()
    assert list(root.glob(f"{JOB_ID}.json.tmp-*")) == []


def test_failed_post_replace_cleanup_retains_artifact_for_manual_recovery(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "results"
    store = TemporalSummaryResultStore(root)
    target = store.record_path(JOB_ID)
    real_replace = temporal_summary_results.os.replace
    real_unlink = Path.unlink

    def replace_then_corrupt(source, destination):
        real_replace(source, destination)
        Path(destination).write_text("{", encoding="utf-8")

    def fail_target_unlink(path, *args, **kwargs):
        if Path(path) == target:
            raise OSError("simulated recovery removal failure")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(temporal_summary_results.os, "replace", replace_then_corrupt)
    monkeypatch.setattr(Path, "unlink", fail_target_unlink)

    with pytest.raises(TemporalSummaryResultRecoveryError, match="manual recovery"):
        _write_success(store)

    assert target.exists()
    assert target.read_text(encoding="utf-8") == "{"
    assert list(root.glob(f"{JOB_ID}.json.tmp-*")) == []
