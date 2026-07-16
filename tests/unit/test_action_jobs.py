from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import re
from threading import Event

import pytest

from api.utils.action_jobs import ActionJobLedger
from api.utils import action_jobs
from steps.common import atomic_io


def test_passive_reader_missing_reads_do_not_create_root(tmp_path):
    root = tmp_path / "missing-jobs"
    reader = action_jobs.PassiveActionJobReader(root)
    job_id = "job_" + "a" * 32

    assert not root.exists()
    assert reader.load(job_id) is None
    assert reader.latest(
        operation="video_summary.generate",
        scope={"video_hash": "a" * 32},
    ) is None
    assert not root.exists()


def test_passive_reader_matches_writer_projection_without_constructing_lock(
    tmp_path, monkeypatch
):
    root = tmp_path / "jobs"
    ledger = ActionJobLedger(root)
    target_scope = {"video_hash": "a" * 32}
    older = ledger.create_pending(
        operation="video_summary.generate",
        scope=target_scope,
        owner_instance="api-1",
    )
    ledger.create_pending(
        operation="identity.rebuild",
        scope=target_scope,
        owner_instance="api-1",
    )
    newer = ledger.create_pending(
        operation="video_summary.generate",
        scope=target_scope,
        owner_instance="api-1",
    )
    before = {
        path.name: (path.read_bytes(), path.stat().st_size, path.stat().st_mtime_ns)
        for path in root.iterdir()
    }

    class ForbiddenFileLock:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("passive reader must not construct a file lock")

    monkeypatch.setattr(action_jobs, "FileLock", ForbiddenFileLock)
    reader = action_jobs.PassiveActionJobReader(root)

    assert reader.load(older["job_id"]) == older
    assert reader.latest(
        operation="video_summary.generate",
        scope=target_scope,
    ) == newer
    after = {
        path.name: (path.read_bytes(), path.stat().st_size, path.stat().st_mtime_ns)
        for path in root.iterdir()
    }
    assert after == before


def test_passive_reader_observes_only_complete_atomic_replacements(tmp_path):
    root = tmp_path / "jobs"
    ledger = ActionJobLedger(root)
    before = ledger.create_pending(
        operation="video_summary.generate",
        scope={"video_hash": "a" * 32},
        owner_instance="api-1",
    )
    after = dict(before)
    after.update(
        {
            "state": "failed",
            "updated_at_utc": "2099-01-01T00:00:00+00:00",
            "outcome": {"code": "test_failure", "message": "Test failure"},
        }
    )
    reader = action_jobs.PassiveActionJobReader(root)
    path = ledger.record_path(before["job_id"])
    start = Event()
    observed = []

    def replace_records():
        start.wait()
        writer_ledger = ActionJobLedger(root)
        for index in range(100):
            with writer_ledger._lock:
                atomic_io.atomic_write_json_for_concurrent_readers(
                    path,
                    before if index % 2 == 0 else after,
                )

    def read_records():
        start.wait()
        for _ in range(300):
            observed.append(reader.load(before["job_id"]))

    with ThreadPoolExecutor(max_workers=2) as executor:
        writer = executor.submit(replace_records)
        reader_task = executor.submit(read_records)
        start.set()
        writer.result()
        reader_task.result()

    assert observed
    assert all(record in (before, after) for record in observed)


def test_passive_latest_observes_only_complete_atomic_replacements(tmp_path):
    root = tmp_path / "jobs"
    scope = {"video_hash": "a" * 32}
    ledger = ActionJobLedger(root)
    before = ledger.create_pending(
        operation="video_summary.generate",
        scope=scope,
        owner_instance="api-1",
    )
    after = dict(before)
    after.update(
        {
            "state": "failed",
            "updated_at_utc": "2099-01-01T00:00:00+00:00",
            "outcome": {"code": "test_failure", "message": "Test failure"},
        }
    )
    reader = action_jobs.PassiveActionJobReader(root)
    path = ledger.record_path(before["job_id"])
    start = Event()
    observed = []

    def replace_records():
        start.wait()
        writer_ledger = ActionJobLedger(root)
        for index in range(100):
            with writer_ledger._lock:
                atomic_io.atomic_write_json_for_concurrent_readers(
                    path,
                    before if index % 2 == 0 else after,
                )

    def read_records():
        start.wait()
        for _ in range(300):
            observed.append(
                reader.latest(
                    operation="video_summary.generate",
                    scope=scope,
                )
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        writer = executor.submit(replace_records)
        reader_task = executor.submit(read_records)
        start.set()
        writer.result()
        reader_task.result()

    assert observed
    assert all(record in (before, after, None) for record in observed)


def test_writer_ledger_still_enters_lock_for_persistence(tmp_path):
    ledger = ActionJobLedger(tmp_path / "jobs")
    actual_lock = ledger._lock
    entered = []

    class LockSpy:
        def __enter__(self):
            actual_lock.acquire()
            entered.append(True)
            return self

        def __exit__(self, exc_type, exc, traceback):
            actual_lock.release()

    ledger._lock = LockSpy()
    ledger.create_pending(
        operation="video_summary.generate",
        scope={"video_hash": "a" * 32},
        owner_instance="api-1",
    )

    assert entered == [True]


def test_action_job_updates_use_open_reader_compatible_replace(
    tmp_path, monkeypatch
):
    ledger = ActionJobLedger(tmp_path / "jobs")
    pending = ledger.create_pending(
        operation="video_summary.generate",
        scope={"video_hash": "a" * 32},
        owner_instance="api-1",
    )
    replacements = []

    def compatible_replace(source, destination):
        replacements.append((source, destination))
        atomic_io.os.replace(source, destination)

    monkeypatch.setattr(
        atomic_io,
        "_replace_file_allowing_open_readers",
        compatible_replace,
        raising=False,
    )

    ledger.transition(
        pending["job_id"],
        expected_states="pending_confirmation",
        new_state="failed",
        outcome={"code": "test_failure", "message": "Test failure"},
    )

    assert len(replacements) == 1


def test_create_pending_record_has_v1_schema_and_normalized_scope(tmp_path):
    ledger = ActionJobLedger(tmp_path / "jobs")

    record = ledger.create_pending(
        operation="video_summary.generate",
        scope={"z": [3, {"b": True, "a": None}], "a": "video-7"},
        owner_instance="api-1",
    )

    assert record == ledger.load(record["job_id"])
    assert record["schema"] == "goodq.action-job.v1"
    assert record["state"] == "pending_confirmation"
    assert record["operation"] == "video_summary.generate"
    assert record["scope"] == {
        "a": "video-7",
        "z": [3, {"a": None, "b": True}],
    }
    assert record["owner_instance"] == "api-1"
    assert record["token_fingerprint"] is None
    assert record["authorization_request_id"] is None
    assert record["outcome"] is None
    assert record["audit_status"] is None
    assert datetime.fromisoformat(record["created_at_utc"]).tzinfo is not None
    assert record["updated_at_utc"] == record["created_at_utc"]
    assert ledger.record_path(record["job_id"]).parent == tmp_path / "jobs"


def test_job_ids_are_opaque_and_invalid_or_traversal_ids_are_rejected(tmp_path):
    ledger = ActionJobLedger(tmp_path / "jobs")
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps({"job_id": "outside"}), encoding="utf-8")

    assert re.fullmatch(r"job_[0-9a-f]{32}", ledger.allocate_job_id())
    for invalid in ("job_short", "../outside", "..\\outside", "C:\\outside"):
        with pytest.raises(ValueError, match="Invalid action job ID"):
            ledger.load(invalid)


@pytest.mark.parametrize(
    "scope",
    [
        {"video_id": "video-7", "bearer_token": "private"},
        {"video_id": "video-7", "nested": {"authorization": "Bearer private"}},
        {"video_id": "video-7", "access_token": "private"},
        {"video_id": "video-7", "Access-Token": "private"},
        {"video_id": "video-7", "refresh_token": "private"},
        {"video_id": "video-7", "refresh token": "private"},
        {"video_id": "video-7", "id_token": "private"},
        {"video_id": "video-7", "id.token": "private"},
        {"video_id": "video-7", "session_token": "private"},
        {"video_id": "video-7", "sessionToken": "private"},
        {"video_id": "video-7", "nested": {"oauth/token": "private"}},
    ],
)
def test_create_rejects_secret_bearing_scope(scope, tmp_path):
    ledger = ActionJobLedger(tmp_path / "jobs")

    with pytest.raises(ValueError, match="secret-bearing"):
        ledger.create_pending(
            operation="video_summary.generate",
            scope=scope,
            owner_instance="api-1",
        )

    assert list((tmp_path / "jobs").glob("job_*.json")) == []


def test_concurrent_prepare_converges_on_exact_normalized_scope(tmp_path):
    root = tmp_path / "jobs"

    def prepare(scope):
        return ActionJobLedger(root).prepare_or_find_active(
            operation="video_summary.generate",
            scope=scope,
            owner_instance="api-1",
        )

    scopes = [
        {"video_id": "video-7", "options": {"style": "brief", "max": 5}},
        {"options": {"max": 5, "style": "brief"}, "video_id": "video-7"},
    ] * 6
    with ThreadPoolExecutor(max_workers=8) as executor:
        records = list(executor.map(prepare, scopes))

    assert len({record["job_id"] for record in records}) == 1
    assert len(list(root.glob("job_*.json"))) == 1


def test_prepare_with_status_reports_created_then_found(tmp_path):
    ledger = ActionJobLedger(tmp_path / "jobs")
    arguments = {
        "operation": "video_summary.generate",
        "scope": {"video_id": "video-7", "options": {"style": "brief"}},
        "owner_instance": "api-1",
    }

    first, first_created = ledger.prepare_or_find_active_with_status(**arguments)
    repeat, repeat_created = ledger.prepare_or_find_active_with_status(**arguments)

    assert first_created is True
    assert repeat_created is False
    assert repeat == first == ledger.load(first["job_id"])


def test_concurrent_prepare_with_status_has_exactly_one_creator(tmp_path):
    root = tmp_path / "jobs"

    def prepare(scope):
        return ActionJobLedger(root).prepare_or_find_active_with_status(
            operation="video_summary.generate",
            scope=scope,
            owner_instance="api-1",
        )

    scopes = [
        {"video_id": "video-7", "options": {"style": "brief", "max": 5}},
        {"options": {"max": 5, "style": "brief"}, "video_id": "video-7"},
    ] * 6
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(prepare, scopes))

    assert sum(created for _, created in results) == 1
    assert len({record["job_id"] for record, _ in results}) == 1
    assert len(list(root.glob("job_*.json"))) == 1


def test_legacy_prepare_returns_record_created_by_status_operation(tmp_path):
    ledger = ActionJobLedger(tmp_path / "jobs")
    arguments = {
        "operation": "video_summary.generate",
        "scope": {"video_id": "video-7"},
        "owner_instance": "api-1",
    }
    created, was_created = ledger.prepare_or_find_active_with_status(**arguments)

    legacy = ledger.prepare_or_find_active(**arguments)

    assert was_created is True
    assert legacy == created == ledger.load(created["job_id"])


def test_prepare_with_status_persists_complete_initial_metadata_in_first_write(
    tmp_path,
    monkeypatch,
):
    ledger = ActionJobLedger(tmp_path / "jobs")
    expiry = "2026-07-13T18:05:00+00:00"
    writes = []
    original_write = action_jobs.atomic_write_json_for_concurrent_readers

    def capture_write(path, payload):
        writes.append(dict(payload))
        return original_write(path, payload)

    monkeypatch.setattr(
        action_jobs,
        "atomic_write_json_for_concurrent_readers",
        capture_write,
    )

    record, created = ledger.prepare_or_find_active_with_status(
        operation="clean_memory.apply",
        scope={"job_id": "job_" + "1" * 32},
        owner_instance="api-1",
        initial_metadata={
            "authorization_request_id": "clean-auth-1",
            "authorization_expires_at_utc": expiry,
        },
    )

    assert created is True
    assert len(writes) == 1
    assert writes[0] == record == ledger.load(record["job_id"])
    assert record["authorization_request_id"] == "clean-auth-1"
    assert record["authorization_expires_at_utc"] == expiry


def test_prepare_creation_blocks_observer_until_complete_record_is_durable(
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "jobs"
    writer_entered = Event()
    observer_started = Event()
    release_writer = Event()
    original_write = action_jobs.atomic_write_json_for_concurrent_readers

    def pause_first_write(path, payload):
        writer_entered.set()
        assert release_writer.wait(timeout=10)
        return original_write(path, payload)

    monkeypatch.setattr(
        action_jobs,
        "atomic_write_json_for_concurrent_readers",
        pause_first_write,
    )

    def create():
        return ActionJobLedger(root).prepare_or_find_active_with_status(
            operation="clean_memory.apply",
            scope={"job_id": "job_" + "1" * 32},
            owner_instance="api-approve",
            initial_metadata={
                "authorization_request_id": "clean-auth-1",
                "authorization_expires_at_utc": "2026-07-13T18:05:00+00:00",
            },
        )

    def observe():
        observer_started.set()
        return ActionJobLedger(root).list_records(
            operation="clean_memory.apply",
            states="pending_confirmation",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        create_future = executor.submit(create)
        assert writer_entered.wait(timeout=10)
        observe_future = executor.submit(observe)
        assert observer_started.wait(timeout=10)
        assert not observe_future.done()
        release_writer.set()
        created, was_created = create_future.result(timeout=10)
        observed = observe_future.result(timeout=10)

    assert was_created is True
    assert observed == [created]
    assert created["authorization_request_id"] == "clean-auth-1"
    assert created["authorization_expires_at_utc"] == "2026-07-13T18:05:00+00:00"


def test_prepare_with_status_does_not_apply_initial_metadata_to_found_record(
    tmp_path,
):
    ledger = ActionJobLedger(tmp_path / "jobs")
    arguments = {
        "operation": "clean_memory.apply",
        "scope": {"job_id": "job_" + "1" * 32},
        "owner_instance": "api-1",
    }
    first, first_created = ledger.prepare_or_find_active_with_status(
        **arguments,
        initial_metadata={
            "authorization_request_id": "clean-auth-first",
            "authorization_expires_at_utc": "2026-07-13T18:05:00+00:00",
        },
    )
    before = ledger.record_path(first["job_id"]).read_bytes()

    found, found_created = ledger.prepare_or_find_active_with_status(
        **arguments,
        initial_metadata={
            "authorization_request_id": "clean-auth-second",
            "authorization_expires_at_utc": "2026-07-13T18:06:00+00:00",
        },
    )

    assert first_created is True
    assert found_created is False
    assert found == first
    assert ledger.record_path(first["job_id"]).read_bytes() == before


def test_concurrent_prepare_with_status_keeps_one_complete_initial_metadata_set(
    tmp_path,
):
    root = tmp_path / "jobs"
    metadata_options = [
        {
            "authorization_request_id": "clean-auth-one",
            "authorization_expires_at_utc": "2026-07-13T18:05:00+00:00",
        },
        {
            "authorization_request_id": "clean-auth-two",
            "authorization_expires_at_utc": "2026-07-13T18:06:00+00:00",
        },
    ]

    def prepare(initial_metadata):
        return ActionJobLedger(root).prepare_or_find_active_with_status(
            operation="clean_memory.apply",
            scope={"job_id": "job_" + "1" * 32},
            owner_instance="api-1",
            initial_metadata=initial_metadata,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(prepare, metadata_options * 4))

    assert sum(created for _, created in results) == 1
    assert len({record["job_id"] for record, _ in results}) == 1
    final = ActionJobLedger(root).load(results[0][0]["job_id"])
    persisted_metadata = {
        "authorization_request_id": final["authorization_request_id"],
        "authorization_expires_at_utc": final["authorization_expires_at_utc"],
    }
    assert persisted_metadata in metadata_options
    assert all(record == final for record, _ in results)


def test_legacy_prepare_callers_preserve_record_shape_without_expiry(tmp_path):
    ledger = ActionJobLedger(tmp_path / "jobs")

    direct = ledger.create_pending(
        operation="video_summary.generate",
        scope={"video_id": "video-direct"},
        owner_instance="api-1",
    )
    prepared = ledger.prepare_or_find_active(
        operation="video_summary.generate",
        scope={"video_id": "video-prepared"},
        owner_instance="api-1",
    )

    assert "authorization_expires_at_utc" not in direct
    assert "authorization_expires_at_utc" not in prepared


@pytest.mark.parametrize("entrypoint", ["create_pending", "prepare", "prepare_status"])
def test_clean_memory_job_creation_requires_complete_initial_metadata(
    entrypoint,
    tmp_path,
):
    root = tmp_path / "jobs"
    ledger = ActionJobLedger(root)
    arguments = {
        "operation": "clean_memory.apply",
        "scope": {"job_id": "job_" + "1" * 32},
        "owner_instance": "api-1",
    }

    with pytest.raises(ValueError, match="initial authorization metadata"):
        if entrypoint == "create_pending":
            ledger.create_pending(**arguments)
        elif entrypoint == "prepare":
            ledger.prepare_or_find_active(**arguments)
        else:
            ledger.prepare_or_find_active_with_status(**arguments)

    assert list(root.glob("job_*.json")) == []


@pytest.mark.parametrize(
    "initial_metadata",
    [
        {"authorization_request_id": "clean-auth-1"},
        {"authorization_expires_at_utc": "2026-07-13T18:05:00+00:00"},
        {
            "authorization_request_id": "clean-auth-1",
            "authorization_expires_at_utc": "2026-07-13T18:05:00",
        },
        {
            "authorization_request_id": "clean-auth-1",
            "authorization_expires_at_utc": "2026-07-13T18:05:00Z",
        },
        {
            "authorization_request_id": "clean-auth-1",
            "authorization_expires_at_utc": "2026-07-13T13:05:00-05:00",
        },
        {
            "authorization_request_id": "clean-auth-1",
            "authorization_expires_at_utc": "2026-07-13T18:05:00+00:00",
            "unexpected": "field",
        },
    ],
)
def test_prepare_rejects_incomplete_or_noncanonical_initial_metadata_without_creation(
    initial_metadata,
    tmp_path,
):
    root = tmp_path / "jobs"
    ledger = ActionJobLedger(root)

    with pytest.raises(ValueError):
        ledger.prepare_or_find_active_with_status(
            operation="clean_memory.apply",
            scope={"job_id": "job_" + "1" * 32},
            owner_instance="api-1",
            initial_metadata=initial_metadata,
        )

    assert list(root.glob("job_*.json")) == []


def test_exact_scope_identity_preserves_json_boolean_and_number_types(tmp_path):
    ledger = ActionJobLedger(tmp_path / "jobs")
    boolean_scope = {"video_id": "video-7", "option": True}
    number_scope = {"video_id": "video-7", "option": 1}

    boolean_record = ledger.prepare_or_find_active(
        operation="video_summary.generate",
        scope=boolean_scope,
        owner_instance="api-1",
    )
    number_record = ledger.prepare_or_find_active(
        operation="video_summary.generate",
        scope=number_scope,
        owner_instance="api-1",
    )

    assert boolean_record["job_id"] != number_record["job_id"]
    assert ledger.latest(
        operation="video_summary.generate", scope=boolean_scope
    ) == boolean_record
    assert ledger.latest(
        operation="video_summary.generate", scope=number_scope
    ) == number_record


def test_prepare_separates_scope_and_listing_is_exact_and_bounded(tmp_path):
    ledger = ActionJobLedger(tmp_path / "jobs")
    target_scope = {"video_id": "video-7", "options": {"style": "brief"}}
    first = ledger.prepare_or_find_active(
        operation="video_summary.generate",
        scope=target_scope,
        owner_instance="api-1",
    )
    different_scope = ledger.prepare_or_find_active(
        operation="video_summary.generate",
        scope={"video_id": "video-8", "options": {"style": "brief"}},
        owner_instance="api-1",
    )
    different_operation = ledger.create_pending(
        operation="identity.rebuild",
        scope=target_scope,
        owner_instance="api-1",
    )
    newest = ledger.create_pending(
        operation="video_summary.generate",
        scope={"options": {"style": "brief"}, "video_id": "video-7"},
        owner_instance="api-1",
    )

    assert first["job_id"] != different_scope["job_id"]
    exact = ledger.list_records(
        operation="video_summary.generate",
        scope=target_scope,
        limit=10,
    )
    assert [record["job_id"] for record in exact] == [newest["job_id"], first["job_id"]]
    assert different_scope["job_id"] not in {record["job_id"] for record in exact}
    assert different_operation["job_id"] not in {record["job_id"] for record in exact}
    assert ledger.latest(operation="video_summary.generate", scope=target_scope) == newest
    assert ledger.list_records(operation="video_summary.generate", limit=1) == [newest]
    with pytest.raises(ValueError, match="between 1 and 100"):
        ledger.list_records(limit=101)


def _record_in_state(ledger, state, *, owner_instance="api-1"):
    record = ledger.create_pending(
        operation="video_summary.generate",
        scope={"video_id": state},
        owner_instance=owner_instance,
    )
    path = {
        "pending_confirmation": [],
        "authorizing": ["authorizing"],
        "queued": ["authorizing", "queued"],
        "running": ["authorizing", "queued", "running"],
    }[state]
    current = "pending_confirmation"
    for next_state in path:
        record = ledger.transition(
            record["job_id"],
            expected_states=current,
            new_state=next_state,
        )
        current = next_state
    return record


def test_list_prior_owner_records_filters_exact_states_newest_first(
    tmp_path, monkeypatch
):
    ledger = ActionJobLedger(tmp_path / "jobs")
    timestamps = iter(
        [
            "2026-07-12T10:00:00+00:00",
            "2026-07-12T10:01:00+00:00",
            "2026-07-12T10:02:00+00:00",
            "2026-07-12T10:03:00+00:00",
            "2026-07-12T10:04:00+00:00",
        ]
    )
    monkeypatch.setattr(action_jobs, "_utc_now_iso", lambda: next(timestamps))
    oldest = ledger.create_pending(
        operation="video_summary.generate",
        scope={"video_id": "oldest"},
        owner_instance="api-old",
    )
    unrequested = _record_in_state(
        ledger, "authorizing", owner_instance="api-old"
    )
    current = ledger.create_pending(
        operation="video_summary.generate",
        scope={"video_id": "current"},
        owner_instance="api-current",
    )
    newest = ledger.create_pending(
        operation="video_summary.generate",
        scope={"video_id": "newest"},
        owner_instance="api-old",
    )

    records = ledger.list_prior_owner_records(
        current_owner_instance="api-current",
        states={"pending_confirmation"},
    )

    assert [record["job_id"] for record in records] == [
        newest["job_id"],
        oldest["job_id"],
    ]
    assert current["job_id"] not in {record["job_id"] for record in records}
    assert unrequested["job_id"] not in {record["job_id"] for record in records}


def test_list_prior_owner_records_breaks_timestamp_ties_by_job_id(
    tmp_path, monkeypatch
):
    ledger = ActionJobLedger(tmp_path / "jobs")
    lower_job_id = f"job_{'0' * 31}1"
    higher_job_id = f"job_{'f' * 32}"
    job_ids = iter([lower_job_id, higher_job_id])
    monkeypatch.setattr(ledger, "allocate_job_id", lambda: next(job_ids))
    monkeypatch.setattr(
        action_jobs, "_utc_now_iso", lambda: "2026-07-12T10:00:00+00:00"
    )
    lower = ledger.create_pending(
        operation="video_summary.generate",
        scope={"video_id": "lower"},
        owner_instance="api-old",
    )
    higher = ledger.create_pending(
        operation="video_summary.generate",
        scope={"video_id": "higher"},
        owner_instance="api-old",
    )

    records = ledger.list_prior_owner_records(
        current_owner_instance="api-current",
        states={"pending_confirmation"},
    )

    assert [record["job_id"] for record in records] == [
        higher["job_id"],
        lower["job_id"],
    ]


def test_list_prior_owner_records_excludes_current_owner_and_terminal_records(tmp_path):
    ledger = ActionJobLedger(tmp_path / "jobs")
    prior_queued = _record_in_state(ledger, "queued", owner_instance="api-old")
    current_queued = _record_in_state(
        ledger, "queued", owner_instance="api-current"
    )
    prior_pending = _record_in_state(
        ledger, "pending_confirmation", owner_instance="api-old"
    )
    terminal = ledger.transition(
        prior_pending["job_id"],
        expected_states="pending_confirmation",
        new_state="failed",
    )

    records = ledger.list_prior_owner_records(
        current_owner_instance="api-current",
        states={"queued"},
    )

    assert records == [prior_queued]
    assert current_queued["job_id"] not in {record["job_id"] for record in records}
    assert terminal["job_id"] not in {record["job_id"] for record in records}


def test_list_prior_owner_records_returns_more_than_operator_limit(tmp_path):
    ledger = ActionJobLedger(tmp_path / "jobs")
    expected_ids = {
        ledger.create_pending(
            operation="video_summary.generate",
            scope={"video_id": f"video-{index}"},
            owner_instance="api-old",
        )["job_id"]
        for index in range(105)
    }

    records = ledger.list_prior_owner_records(
        current_owner_instance="api-current",
        states={"pending_confirmation"},
    )

    assert len(records) == 105
    assert {record["job_id"] for record in records} == expected_ids


@pytest.mark.parametrize(
    ("current_owner_instance", "states"),
    [
        ("", {"queued"}),
        ("../../api-current", {"queued"}),
        ("api-current", set()),
        ("api-current", {"unknown"}),
        ("api-current", {"failed"}),
        ("api-current", {"queued", "interrupted"}),
    ],
)
def test_list_prior_owner_records_rejects_invalid_owner_or_state_filters(
    current_owner_instance, states, tmp_path
):
    ledger = ActionJobLedger(tmp_path / "jobs")

    with pytest.raises(ValueError):
        ledger.list_prior_owner_records(
            current_owner_instance=current_owner_instance,
            states=states,
        )


def test_list_prior_owner_records_preserves_record_bytes_and_mtimes(tmp_path):
    root = tmp_path / "jobs"
    ledger = ActionJobLedger(root)
    matching = _record_in_state(ledger, "running", owner_instance="api-old")
    _record_in_state(ledger, "running", owner_instance="api-current")
    paths = sorted(root.glob("job_*.json"))
    before = {
        path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths
    }

    records = ledger.list_prior_owner_records(
        current_owner_instance="api-current",
        states={"running"},
    )

    after = {
        path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths
    }
    assert records == [matching]
    assert after == before


@pytest.mark.parametrize(
    ("current_state", "new_state"),
    [
        ("pending_confirmation", "authorizing"),
        ("pending_confirmation", "expired"),
        ("pending_confirmation", "failed"),
        ("authorizing", "queued"),
        ("authorizing", "failed"),
        ("authorizing", "expired"),
        ("queued", "running"),
        ("queued", "failed"),
        ("queued", "interrupted"),
        ("running", "succeeded"),
        ("running", "failed"),
        ("running", "interrupted"),
    ],
)
def test_each_permitted_transition_edge(current_state, new_state, tmp_path):
    ledger = ActionJobLedger(tmp_path / f"jobs-{current_state}-{new_state}")
    before = _record_in_state(ledger, current_state)

    after = ledger.transition(
        before["job_id"],
        expected_states={current_state},
        new_state=new_state,
    )

    assert after["state"] == new_state
    assert ledger.load(before["job_id"]) == after


_ALL_STATES = {
    "pending_confirmation",
    "authorizing",
    "queued",
    "running",
    "succeeded",
    "failed",
    "interrupted",
    "expired",
}
_VALID_EDGES = {
    ("pending_confirmation", "authorizing"),
    ("pending_confirmation", "expired"),
    ("pending_confirmation", "failed"),
    ("authorizing", "queued"),
    ("authorizing", "failed"),
    ("authorizing", "expired"),
    ("queued", "running"),
    ("queued", "failed"),
    ("queued", "interrupted"),
    ("running", "succeeded"),
    ("running", "failed"),
    ("running", "interrupted"),
}
_INVALID_NONTERMINAL_EDGES = sorted(
    (current, new)
    for current in {
        "pending_confirmation",
        "authorizing",
        "queued",
        "running",
    }
    for new in _ALL_STATES
    if (current, new) not in _VALID_EDGES
)


@pytest.mark.parametrize(("current_state", "new_state"), _INVALID_NONTERMINAL_EDGES)
def test_every_other_nonterminal_edge_is_rejected(current_state, new_state, tmp_path):
    ledger = ActionJobLedger(tmp_path / f"invalid-{current_state}-{new_state}")
    before = _record_in_state(ledger, current_state)

    with pytest.raises(action_jobs.InvalidTransitionError):
        ledger.transition(
            before["job_id"],
            expected_states=current_state,
            new_state=new_state,
        )

    assert ledger.load(before["job_id"]) == before


def test_stale_expectation_is_rejected_without_modifying_record(tmp_path):
    ledger = ActionJobLedger(tmp_path / "jobs")
    before = _record_in_state(ledger, "queued")

    with pytest.raises(action_jobs.StaleTransitionError, match="found queued"):
        ledger.transition(
            before["job_id"],
            expected_states={"pending_confirmation", "authorizing"},
            new_state="running",
        )

    assert ledger.load(before["job_id"]) == before


@pytest.mark.parametrize("terminal_state", ["succeeded", "failed", "interrupted", "expired"])
def test_terminal_records_are_immutable(terminal_state, tmp_path):
    ledger = ActionJobLedger(tmp_path / f"terminal-{terminal_state}")
    if terminal_state in {"failed", "expired"}:
        active = _record_in_state(ledger, "pending_confirmation")
    else:
        active = _record_in_state(ledger, "running")
    terminal = ledger.transition(
        active["job_id"],
        expected_states=active["state"],
        new_state=terminal_state,
    )

    with pytest.raises(action_jobs.TerminalTransitionError):
        ledger.transition(
            terminal["job_id"],
            expected_states=terminal_state,
            new_state="failed",
        )

    assert ledger.load(terminal["job_id"]) == terminal


def test_concurrent_transition_has_exactly_one_winner(tmp_path):
    root = tmp_path / "jobs"
    queued = _record_in_state(ActionJobLedger(root), "queued")

    def claim():
        try:
            return ActionJobLedger(root).transition(
                queued["job_id"],
                expected_states="queued",
                new_state="running",
            )["state"]
        except action_jobs.StaleTransitionError:
            return "stale"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: claim(), range(2)))

    assert sorted(results) == ["running", "stale"]
    assert ActionJobLedger(root).load(queued["job_id"])["state"] == "running"


def test_transition_persists_only_sanitized_control_and_outcome_fields(tmp_path):
    ledger = ActionJobLedger(tmp_path / "jobs")
    pending = _record_in_state(ledger, "pending_confirmation")
    fingerprint = "a" * 64

    authorizing = ledger.transition(
        pending["job_id"],
        expected_states="pending_confirmation",
        new_state="authorizing",
        token_fingerprint=fingerprint,
        authorization_request_id="auth_req-7",
    )
    queued = ledger.transition(
        authorizing["job_id"],
        expected_states="authorizing",
        new_state="queued",
    )
    running = ledger.transition(
        queued["job_id"],
        expected_states="queued",
        new_state="running",
    )
    succeeded = ledger.transition(
        running["job_id"],
        expected_states="running",
        new_state="succeeded",
        outcome={"code": "summary_ready", "message": "Summary generated"},
        audit_status="recorded",
    )

    assert succeeded["token_fingerprint"] == fingerprint
    assert succeeded["authorization_request_id"] == "auth_req-7"
    assert succeeded["outcome"] == {
        "code": "summary_ready",
        "message": "Summary generated",
    }
    assert succeeded["audit_status"] == "recorded"
    serialized = ledger.record_path(succeeded["job_id"]).read_text(encoding="utf-8")
    assert "Bearer " not in serialized
    assert "bearer_token" not in serialized


def test_compare_and_update_persists_metadata_without_changing_state(tmp_path):
    ledger = ActionJobLedger(tmp_path / "jobs")
    pending = _record_in_state(ledger, "pending_confirmation")

    updated = ledger.compare_and_update(
        pending["job_id"],
        expected_state="pending_confirmation",
        token_fingerprint="b" * 64,
        authorization_request_id="auth_req-pending-7",
    )

    assert updated["state"] == "pending_confirmation"
    assert updated["created_at_utc"] == pending["created_at_utc"]
    assert updated["updated_at_utc"] >= pending["updated_at_utc"]
    assert updated["token_fingerprint"] == "b" * 64
    assert updated["authorization_request_id"] == "auth_req-pending-7"
    assert ledger.load(pending["job_id"]) == updated


def test_compare_and_update_rejects_stale_state_without_modification(tmp_path):
    ledger = ActionJobLedger(tmp_path / "jobs")
    authorizing = _record_in_state(ledger, "authorizing")

    with pytest.raises(action_jobs.StaleTransitionError, match="found authorizing"):
        ledger.compare_and_update(
            authorizing["job_id"],
            expected_state="pending_confirmation",
            token_fingerprint="c" * 64,
        )

    assert ledger.load(authorizing["job_id"]) == authorizing


def test_compare_and_update_never_modifies_terminal_record(tmp_path):
    ledger = ActionJobLedger(tmp_path / "jobs")
    pending = _record_in_state(ledger, "pending_confirmation")
    failed = ledger.transition(
        pending["job_id"],
        expected_states="pending_confirmation",
        new_state="failed",
    )

    with pytest.raises(action_jobs.TerminalTransitionError):
        ledger.compare_and_update(
            failed["job_id"],
            expected_state="pending_confirmation",
            audit_status="recorded",
        )

    assert ledger.load(failed["job_id"]) == failed


def test_concurrent_compare_and_update_preserves_distinct_metadata(tmp_path):
    root = tmp_path / "jobs"
    pending = _record_in_state(ActionJobLedger(root), "pending_confirmation")
    updates = [
        {"token_fingerprint": "d" * 64},
        {"authorization_request_id": "auth_req-concurrent"},
    ]

    def update(metadata):
        return ActionJobLedger(root).compare_and_update(
            pending["job_id"],
            expected_state="pending_confirmation",
            **metadata,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(update, updates))

    final = ActionJobLedger(root).load(pending["job_id"])
    assert final["state"] == "pending_confirmation"
    assert final["token_fingerprint"] == "d" * 64
    assert final["authorization_request_id"] == "auth_req-concurrent"


def test_compare_and_update_replace_failure_leaves_prior_record_readable(
    tmp_path, monkeypatch
):
    ledger = ActionJobLedger(tmp_path / "jobs")
    pending = _record_in_state(ledger, "pending_confirmation")

    def fail_replace(source, destination):
        raise OSError("simulated metadata replace failure")

    monkeypatch.setattr(
        atomic_io,
        "_replace_file_allowing_open_readers",
        fail_replace,
    )

    with pytest.raises(OSError, match="simulated metadata replace failure"):
        ledger.compare_and_update(
            pending["job_id"],
            expected_state="pending_confirmation",
            token_fingerprint="e" * 64,
        )

    assert ledger.load(pending["job_id"]) == pending


def test_adopt_owner_requires_exact_state_and_prior_owner(tmp_path):
    ledger = ActionJobLedger(tmp_path / "jobs")
    before = _record_in_state(ledger, "authorizing", owner_instance="api-old")

    adopted = ledger.adopt_owner(
        before["job_id"],
        expected_state="authorizing",
        expected_owner_instance="api-old",
        new_owner_instance="api-current",
    )

    assert set(adopted) == set(before)
    for key in set(before) - {"owner_instance", "updated_at_utc"}:
        assert adopted[key] == before[key]
    assert adopted["owner_instance"] == "api-current"
    assert adopted["updated_at_utc"] >= before["updated_at_utc"]
    assert ledger.load(before["job_id"]) == adopted


def test_adopt_owner_rejects_stale_state_byte_for_byte(tmp_path):
    ledger = ActionJobLedger(tmp_path / "jobs")
    before = _record_in_state(ledger, "authorizing", owner_instance="api-old")
    record_path = ledger.record_path(before["job_id"])
    serialized_before = record_path.read_bytes()

    with pytest.raises(action_jobs.StaleTransitionError, match="found authorizing"):
        ledger.adopt_owner(
            before["job_id"],
            expected_state="pending_confirmation",
            expected_owner_instance="api-old",
            new_owner_instance="api-current",
        )

    assert record_path.read_bytes() == serialized_before


def test_adopt_owner_rejects_stale_owner_byte_for_byte(tmp_path):
    ledger = ActionJobLedger(tmp_path / "jobs")
    before = _record_in_state(ledger, "authorizing", owner_instance="api-old")
    record_path = ledger.record_path(before["job_id"])
    serialized_before = record_path.read_bytes()

    with pytest.raises(action_jobs.StaleTransitionError, match="owner"):
        ledger.adopt_owner(
            before["job_id"],
            expected_state="authorizing",
            expected_owner_instance="api-stale",
            new_owner_instance="api-current",
        )

    assert record_path.read_bytes() == serialized_before


def test_concurrent_owner_adoption_has_exactly_one_winner(tmp_path):
    root = tmp_path / "jobs"
    before = _record_in_state(
        ActionJobLedger(root), "authorizing", owner_instance="api-old"
    )

    def adopt(new_owner_instance):
        try:
            return ActionJobLedger(root).adopt_owner(
                before["job_id"],
                expected_state="authorizing",
                expected_owner_instance="api-old",
                new_owner_instance=new_owner_instance,
            )["owner_instance"]
        except action_jobs.StaleTransitionError:
            return "stale"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(adopt, ["api-one", "api-two"]))

    assert results.count("stale") == 1
    winners = set(results) - {"stale"}
    assert len(winners) == 1
    assert ActionJobLedger(root).load(before["job_id"])["owner_instance"] in winners


def test_adopt_owner_rejects_terminal_record_without_mutation(tmp_path):
    ledger = ActionJobLedger(tmp_path / "jobs")
    pending = _record_in_state(
        ledger, "pending_confirmation", owner_instance="api-old"
    )
    terminal = ledger.transition(
        pending["job_id"],
        expected_states="pending_confirmation",
        new_state="failed",
    )
    record_path = ledger.record_path(terminal["job_id"])
    serialized_before = record_path.read_bytes()

    with pytest.raises(action_jobs.TerminalTransitionError):
        ledger.adopt_owner(
            terminal["job_id"],
            expected_state="pending_confirmation",
            expected_owner_instance="api-old",
            new_owner_instance="api-current",
        )

    assert record_path.read_bytes() == serialized_before


@pytest.mark.parametrize(
    ("argument", "unsafe_owner"),
    [
        ("expected_owner_instance", ""),
        ("new_owner_instance", "   "),
        ("expected_owner_instance", None),
        ("new_owner_instance", 7),
        ("expected_owner_instance", "../../api-old"),
        ("new_owner_instance", "Bearer private"),
    ],
)
def test_adopt_owner_rejects_invalid_owner_values_without_mutation(
    argument, unsafe_owner, tmp_path
):
    ledger = ActionJobLedger(tmp_path / "jobs")
    before = _record_in_state(ledger, "authorizing", owner_instance="api-old")
    record_path = ledger.record_path(before["job_id"])
    serialized_before = record_path.read_bytes()
    owner_arguments = {
        "expected_owner_instance": "api-old",
        "new_owner_instance": "api-current",
    }
    owner_arguments[argument] = unsafe_owner

    with pytest.raises(ValueError, match="owner instance"):
        ledger.adopt_owner(
            before["job_id"],
            expected_state="authorizing",
            **owner_arguments,
        )

    assert record_path.read_bytes() == serialized_before


def test_adopt_and_transition_updates_owner_state_and_metadata_in_one_write(
    tmp_path,
    monkeypatch,
):
    ledger = ActionJobLedger(tmp_path / "jobs")
    before = _record_in_state(
        ledger,
        "pending_confirmation",
        owner_instance="api-old",
    )
    writes = []
    original_write = action_jobs.atomic_write_json_for_concurrent_readers

    def capture_write(path, payload):
        writes.append(dict(payload))
        return original_write(path, payload)

    monkeypatch.setattr(
        action_jobs,
        "atomic_write_json_for_concurrent_readers",
        capture_write,
    )

    after = ledger.adopt_and_transition(
        before["job_id"],
        expected_state="pending_confirmation",
        expected_owner_instance="api-old",
        new_owner_instance="api-current",
        new_state="authorizing",
        token_fingerprint="a" * 64,
    )

    assert len(writes) == 1
    assert writes[0] == after == ledger.load(before["job_id"])
    assert after["owner_instance"] == "api-current"
    assert after["state"] == "authorizing"
    assert after["token_fingerprint"] == "a" * 64


@pytest.mark.parametrize(
    ("expected_state", "expected_owner", "message"),
    [
        ("authorizing", "api-old", "found pending_confirmation"),
        ("pending_confirmation", "api-stale", "owner"),
    ],
)
def test_adopt_and_transition_rejects_stale_state_or_owner_byte_for_byte(
    expected_state,
    expected_owner,
    message,
    tmp_path,
):
    ledger = ActionJobLedger(tmp_path / "jobs")
    before = _record_in_state(
        ledger,
        "pending_confirmation",
        owner_instance="api-old",
    )
    record_path = ledger.record_path(before["job_id"])
    serialized_before = record_path.read_bytes()

    with pytest.raises(action_jobs.StaleTransitionError, match=message):
        ledger.adopt_and_transition(
            before["job_id"],
            expected_state=expected_state,
            expected_owner_instance=expected_owner,
            new_owner_instance="api-current",
            new_state="authorizing",
        )

    assert record_path.read_bytes() == serialized_before


def test_concurrent_adopt_and_transition_has_one_complete_owner_state_winner(
    tmp_path,
):
    root = tmp_path / "jobs"
    before = _record_in_state(
        ActionJobLedger(root),
        "pending_confirmation",
        owner_instance="api-old",
    )

    def claim(new_owner):
        try:
            record = ActionJobLedger(root).adopt_and_transition(
                before["job_id"],
                expected_state="pending_confirmation",
                expected_owner_instance="api-old",
                new_owner_instance=new_owner,
                new_state="authorizing",
            )
            return record["owner_instance"], record["state"]
        except action_jobs.StaleTransitionError:
            return "stale", "stale"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(claim, ["api-one", "api-two"]))

    assert results.count(("stale", "stale")) == 1
    winner = next(result for result in results if result != ("stale", "stale"))
    assert winner[1] == "authorizing"
    final = ActionJobLedger(root).load(before["job_id"])
    assert (final["owner_instance"], final["state"]) == winner


def test_adopt_and_transition_rejects_invalid_edge_and_terminal_without_mutation(
    tmp_path,
):
    ledger = ActionJobLedger(tmp_path / "jobs")
    queued = _record_in_state(ledger, "queued", owner_instance="api-old")
    queued_path = ledger.record_path(queued["job_id"])
    queued_before = queued_path.read_bytes()

    with pytest.raises(action_jobs.InvalidTransitionError):
        ledger.adopt_and_transition(
            queued["job_id"],
            expected_state="queued",
            expected_owner_instance="api-old",
            new_owner_instance="api-current",
            new_state="succeeded",
        )
    assert queued_path.read_bytes() == queued_before

    terminal = ledger.transition(
        queued["job_id"],
        expected_states="queued",
        new_state="failed",
    )
    terminal_before = queued_path.read_bytes()
    with pytest.raises(action_jobs.TerminalTransitionError):
        ledger.adopt_and_transition(
            terminal["job_id"],
            expected_state="failed",
            expected_owner_instance="api-old",
            new_owner_instance="api-current",
            new_state="interrupted",
        )
    assert queued_path.read_bytes() == terminal_before


def test_adopt_and_transition_replace_failure_leaves_prior_record_readable(
    tmp_path,
    monkeypatch,
):
    ledger = ActionJobLedger(tmp_path / "jobs")
    before = _record_in_state(
        ledger,
        "pending_confirmation",
        owner_instance="api-old",
    )
    record_path = ledger.record_path(before["job_id"])
    serialized_before = record_path.read_bytes()

    def fail_replace(source, destination):
        raise OSError("simulated owner-state replace failure")

    monkeypatch.setattr(
        atomic_io,
        "_replace_file_allowing_open_readers",
        fail_replace,
    )

    with pytest.raises(OSError, match="simulated owner-state replace failure"):
        ledger.adopt_and_transition(
            before["job_id"],
            expected_state="pending_confirmation",
            expected_owner_instance="api-old",
            new_owner_instance="api-current",
            new_state="authorizing",
        )

    assert ledger.load(before["job_id"]) == before
    assert record_path.read_bytes() == serialized_before


@pytest.mark.parametrize(
    "updates",
    [
        {"bearer_token": "private"},
        {"authorization": "Bearer private"},
        {"traceback": "Traceback (most recent call last): private"},
        {"exception": RuntimeError("private failure")},
        {
            "outcome": {
                "code": "worker_failed",
                "message": "Traceback (most recent call last): worker failed",
            }
        },
        {
            "outcome": {
                "code": "worker_failed",
                "message": "Failed at C:\\private\\video.mp4",
            }
        },
        {
            "outcome": {
                "code": "worker_failed",
                "message": "stdout=private frame data",
            }
        },
        {
            "outcome": {
                "code": "worker_failed",
                "message": "Worker failed",
                "stderr": "private output",
            }
        },
        {
            "outcome": {
                "code": "worker_failed",
                "message": "Worker failed",
                "secret": "private",
            }
        },
    ],
)
def test_transition_rejects_unsanitized_or_secret_bearing_updates(updates, tmp_path):
    ledger = ActionJobLedger(tmp_path / "jobs")
    before = _record_in_state(ledger, "running")

    with pytest.raises(ValueError):
        ledger.transition(
            before["job_id"],
            expected_states="running",
            new_state="failed",
            **updates,
        )

    assert ledger.load(before["job_id"]) == before


def test_reconcile_interrupts_only_prior_owner_queued_or_running_jobs(tmp_path):
    ledger = ActionJobLedger(tmp_path / "jobs")
    prior_queued = _record_in_state(ledger, "queued", owner_instance="api-old")
    prior_running = _record_in_state(ledger, "running", owner_instance="api-old")
    prior_pending = _record_in_state(
        ledger, "pending_confirmation", owner_instance="api-old"
    )
    prior_authorizing = _record_in_state(
        ledger, "authorizing", owner_instance="api-old"
    )
    current_queued = _record_in_state(ledger, "queued", owner_instance="api-current")

    interrupted = ledger.reconcile_prior_owner("api-current")

    assert {record["job_id"] for record in interrupted} == {
        prior_queued["job_id"],
        prior_running["job_id"],
    }
    for record in interrupted:
        assert record["state"] == "interrupted"
        assert record["outcome"] == {
            "code": "owner_replaced",
            "message": "Interrupted after owner instance changed",
        }
    assert ledger.load(prior_pending["job_id"])["state"] == "pending_confirmation"
    assert ledger.load(prior_authorizing["job_id"])["state"] == "authorizing"
    assert ledger.load(current_queued["job_id"])["state"] == "queued"


def test_terminal_record_does_not_block_new_preparation(tmp_path):
    ledger = ActionJobLedger(tmp_path / "jobs")
    scope = {"video_id": "video-7"}
    pending = ledger.prepare_or_find_active(
        operation="video_summary.generate",
        scope=scope,
        owner_instance="api-1",
    )
    failed = ledger.transition(
        pending["job_id"],
        expected_states="pending_confirmation",
        new_state="failed",
        outcome={"code": "token_issue_failed", "message": "Confirmation unavailable"},
    )

    replacement = ledger.prepare_or_find_active(
        operation="video_summary.generate",
        scope=scope,
        owner_instance="api-1",
    )

    assert failed["state"] == "failed"
    assert replacement["state"] == "pending_confirmation"
    assert replacement["job_id"] != failed["job_id"]


def test_atomic_replace_failure_leaves_prior_record_readable(tmp_path, monkeypatch):
    ledger = ActionJobLedger(tmp_path / "jobs")
    before = _record_in_state(ledger, "queued")

    def fail_replace(source, destination):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(
        atomic_io,
        "_replace_file_allowing_open_readers",
        fail_replace,
    )

    with pytest.raises(OSError, match="simulated replace failure"):
        ledger.transition(
            before["job_id"],
            expected_states="queued",
            new_state="running",
        )

    assert ledger.load(before["job_id"]) == before
