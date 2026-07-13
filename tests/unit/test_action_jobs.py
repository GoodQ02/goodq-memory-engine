from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import re

import pytest

from api.utils.action_jobs import ActionJobLedger
from api.utils import action_jobs
from steps.common import atomic_io


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

    monkeypatch.setattr(atomic_io.os, "replace", fail_replace)

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

    monkeypatch.setattr(atomic_io.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        ledger.transition(
            before["job_id"],
            expected_states="queued",
            new_state="running",
        )

    assert ledger.load(before["job_id"]) == before
