from __future__ import annotations

import copy
import io
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from api.main import app
from api.routes import identity as identity_route
from api.utils.action_jobs import ActionJobLedger
from scripts.identity import build_face_clusters


@pytest.fixture
def client() -> TestClient:
    return TestClient(
        app,
        raise_server_exceptions=False,
        client=("127.0.0.1", 50000),
    )


@pytest.fixture(autouse=True)
def isolate_identity_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_route, "_CFG", {})


class _Authority:
    def __init__(self) -> None:
        self.audit_calls: list[dict[str, Any]] = []

    def authorize_action(self, **_kwargs: Any) -> tuple[dict[str, Any], int]:
        return (
            {
                "status": "ok",
                "request_id": "req-" + "a" * 16,
                "result": {"allowed": True},
                "errors": [],
            },
            0,
        )

    def record_external_execution_outcome(self, **kwargs: Any) -> dict[str, Any]:
        self.audit_calls.append(kwargs)
        return {"audit_status": "recorded", "error_codes": []}


def _valid_manifest(*, epoch_id: str = "epoch-test", eps: float = 0.4) -> dict[str, Any]:
    return {
        "epoch_id": epoch_id,
        "generated_at": "2026-07-20T12:00:00+00:00",
        "eps_used": eps,
        "note": "Candidate clusters for operator review",
        "cluster_count": 1,
        "unassigned_count": 1,
        "clusters": [
            {
                "cluster_id": "face_cluster_0",
                "status": "candidate",
                "label": None,
                "confirmed": False,
                "face_count": 2,
                "video_count": 1,
                "video_hashes": ["video-a"],
                "timestamp_range": [1.0, 2.0],
                "face_ids": ["face-a", "face-b"],
                "representative_frame": "frame-a.jpg",
            }
        ],
        "unassigned_face_ids": ["face-c"],
    }


class _FakeStdin:
    def __init__(
        self,
        events: list[str],
        *,
        on_flush: Callable[[], None] | None = None,
        flush_error: Exception | None = None,
    ) -> None:
        self.events = events
        self.on_flush = on_flush
        self.flush_error = flush_error
        self.writes: list[str] = []
        self.closed = False

    def write(self, marker: str) -> int:
        self.events.append("stdin_write")
        self.writes.append(marker)
        return len(marker)

    def flush(self) -> None:
        self.events.append("stdin_flush")
        if self.on_flush is not None:
            self.on_flush()
        if self.flush_error is not None:
            raise self.flush_error

    def close(self) -> None:
        self.events.append("stdin_close")
        self.closed = True


class _FakeProcess:
    def __init__(
        self,
        events: list[str],
        *,
        pid: int = 4321,
        returncode: int = 0,
        on_communicate: Callable[[], None] | None = None,
        communicate_results: list[Any] | None = None,
        wait_results: list[Any] | None = None,
        stdin_flush_error: Exception | None = None,
        on_stdin_flush: Callable[[], None] | None = None,
    ) -> None:
        self.events = events
        self.pid = pid
        self.returncode: int | None = None
        self.final_returncode = returncode
        self.on_communicate = on_communicate
        self.communicate_results = list(communicate_results or [])
        self.wait_results = list(wait_results or [])
        self.input_stream = _FakeStdin(
            events,
            on_flush=on_stdin_flush,
            flush_error=stdin_flush_error,
        )
        self.stdin: _FakeStdin | None = self.input_stream
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        self.events.append("communicate")
        if self.on_communicate is not None:
            callback, self.on_communicate = self.on_communicate, None
            callback()
        if self.communicate_results:
            result = self.communicate_results.pop(0)
            if isinstance(result, BaseException):
                raise result
            self.returncode = self.final_returncode
            return result
        self.returncode = self.final_returncode
        return "", ""

    def terminate(self) -> None:
        self.events.append("terminate")

    def kill(self) -> None:
        self.events.append("kill")

    def wait(self, timeout: float | None = None) -> int:
        self.events.append("wait")
        if self.wait_results:
            result = self.wait_results.pop(0)
            if isinstance(result, BaseException):
                raise result
            self.returncode = int(result)
            return int(result)
        self.returncode = self.final_returncode
        return self.final_returncode

    def poll(self) -> int | None:
        return self.returncode


def _install_rebuild_fakes(
    monkeypatch: pytest.MonkeyPatch,
    identity_dir: Path,
    process: _FakeProcess,
    authority: _Authority,
) -> MagicMock:
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))
    monkeypatch.setattr(identity_route, "_epoch_id", lambda: "epoch-test")
    monkeypatch.setattr(identity_route, "MiniAgentClient", lambda **_kw: authority)
    monkeypatch.setattr(
        identity_route,
        "_probe_process_start_token",
        lambda pid: ("live", "abc123") if pid == process.pid else ("unknown", None),
    )
    popen = MagicMock(return_value=process)
    monkeypatch.setattr(identity_route.subprocess, "Popen", popen)
    return popen


@pytest.mark.parametrize(
    "marker",
    [
        b"",
        b"START job_11111111111111111111111111111111",
        b"START job_11111111111111111111111111111111\r\r\n",
        b"START job_11111111111111111111111111111111 \n",
        b"WRONG job_11111111111111111111111111111111\n",
    ],
)
def test_gate_eof_or_wrong_marker_exits_before_identity_path_creation(
    tmp_path: Path,
    marker: bytes,
) -> None:
    job_id = "job_" + "1" * 32
    data_path = tmp_path / "identity"
    command = [
        sys.executable,
        str(repo_root / "scripts" / "identity" / "build_face_clusters.py"),
        "--epoch-id",
        "epoch-test",
        "--epoch-root",
        str(tmp_path / "missing-epochs"),
        "--data-path",
        str(data_path),
        "--start-gate-job-id",
        job_id,
    ]

    result = subprocess.run(
        command,
        input=marker,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode != 0
    assert not data_path.exists()


@pytest.mark.parametrize("line_ending", [b"\n", b"\r\n"])
def test_correct_marker_alone_crosses_gate_before_builder_path(
    tmp_path: Path,
    line_ending: bytes,
) -> None:
    job_id = "job_" + "2" * 32
    data_path = tmp_path / "identity"
    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "identity" / "build_face_clusters.py"),
            "--epoch-id",
            "epoch-test",
            "--epoch-root",
            str(tmp_path / "missing-epochs"),
            "--data-path",
            str(data_path),
            "--start-gate-job-id",
            job_id,
        ],
        input=f"START {job_id}".encode("ascii") + line_ending,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode != 0
    assert data_path.is_dir()
    assert not (data_path / "face_clusters.json").exists()


def test_direct_cli_without_gate_never_reads_stdin_and_runs_existing_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ForbiddenStdin:
        def readline(self, *_args: Any, **_kwargs: Any) -> str:
            raise AssertionError("direct CLI read stdin")

    data_path = tmp_path / "identity"
    epoch_dir = tmp_path / "epochs" / "epoch-test"
    monkeypatch.setattr(sys, "stdin", _ForbiddenStdin())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_face_clusters.py",
            "--epoch-id",
            "epoch-test",
            "--epoch-root",
            str(tmp_path / "epochs"),
            "--data-path",
            str(data_path),
        ],
    )
    monkeypatch.setattr(build_face_clusters, "_epoch_dir", lambda *_a: epoch_dir)
    monkeypatch.setattr(build_face_clusters, "_ucf_db", lambda *_a: tmp_path / "ucf.db")
    monkeypatch.setattr(
        build_face_clusters,
        "load_face_ucf_provenance",
        lambda *_a: {"frame": {"video_hash": "video-a"}},
    )
    detections = [
        {"detection_id": "face-a", "video_hash": "video-a", "t_start": 1.0, "raw_ref": "frame-a"},
        {"detection_id": "face-b", "video_hash": "video-a", "t_start": 2.0, "raw_ref": "frame-b"},
    ]
    monkeypatch.setattr(build_face_clusters, "collect_face_detections", lambda *_a: detections)
    monkeypatch.setattr(build_face_clusters, "run_dbscan", lambda *_a: build_face_clusters.np.array([0, 0]))
    monkeypatch.setattr(build_face_clusters, "generate_html_sheet", lambda *_a: None)

    build_face_clusters.main()

    assert (data_path / "face_clusters.json").is_file()


def test_protocol_and_child_pair_are_durable_before_first_marker_write(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_dir = tmp_path / "identity"
    identity_dir.mkdir()
    events: list[str] = []
    manifest_path = identity_dir / "face_clusters.json"
    process = _FakeProcess(
        events,
        on_communicate=lambda: manifest_path.write_text(
            json.dumps(_valid_manifest()), encoding="utf-8"
        ),
    )
    authority = _Authority()
    popen = _install_rebuild_fakes(
        monkeypatch, identity_dir, process, authority
    )
    real_ledger = ActionJobLedger

    class _TrackingLedger(real_ledger):
        def transition(self, job_id: str, **kwargs: Any) -> dict[str, Any]:
            result = super().transition(job_id, **kwargs)
            if kwargs.get("new_state") == "running":
                assert result.get("launch_protocol") == "stdin_gate_v1"
                events.append("protocol_persisted")
            return result

        def compare_and_update(self, job_id: str, **kwargs: Any) -> dict[str, Any]:
            result = super().compare_and_update(job_id, **kwargs)
            assert result["child_pid"] == process.pid
            assert result["child_start_token"] == "abc123"
            events.append("child_pair_persisted")
            return result

    monkeypatch.setattr(identity_route, "ActionJobLedger", _TrackingLedger)

    def _spawn(*args: Any, **kwargs: Any) -> _FakeProcess:
        events.append("spawn")
        return process

    popen.side_effect = _spawn
    monkeypatch.setattr(
        identity_route.subprocess,
        "run",
        MagicMock(side_effect=AssertionError("rebuild must use Popen")),
    )

    response = client.post(
        "/api/identity/rebuild-face-clusters",
        json={"eps": 0.4, "confirmation_token": "tok-order"},
    )

    assert response.status_code == 200, response.text
    assert events.index("protocol_persisted") < events.index("spawn")
    assert events.index("spawn") < events.index("child_pair_persisted")
    assert events.index("child_pair_persisted") < events.index("stdin_write")
    assert events.index("stdin_write") < events.index("stdin_flush")
    assert process.input_stream.writes == [
        f"START {response.json()['job']['job_id']}\n"
    ]
    args, kwargs = popen.call_args
    command = args[0]
    assert "--data-path" in command
    assert command[command.index("--data-path") + 1] == str(identity_dir)
    assert "--start-gate-job-id" in command
    assert kwargs["shell"] is False
    assert kwargs["close_fds"] is True
    assert kwargs["stdin"] is subprocess.PIPE
    assert kwargs["stdout"] is subprocess.PIPE
    assert kwargs["stderr"] is subprocess.PIPE
    persisted = ActionJobLedger(identity_dir / "process_jobs").list_records()[0]
    assert persisted["state"] == "succeeded"
    assert persisted["launch_protocol"] == "stdin_gate_v1"
    assert persisted["child_pid"] == 4321
    assert persisted["child_start_token"] == "abc123"
    serialized = json.dumps(response.json()) + json.dumps(authority.audit_calls)
    assert "child_pid" not in serialized
    assert "child_start_token" not in serialized
    assert "launch_protocol" not in serialized


def test_child_capture_failure_never_sends_marker_and_confirms_death_before_terminalizing(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_dir = tmp_path / "capture-failure"
    identity_dir.mkdir()
    events: list[str] = []
    process = _FakeProcess(events, wait_results=[1])
    authority = _Authority()
    _install_rebuild_fakes(monkeypatch, identity_dir, process, authority)
    monkeypatch.setattr(
        identity_route,
        "_probe_process_start_token",
        lambda _pid: ("unknown", None),
    )
    monkeypatch.setattr(
        identity_route.subprocess,
        "run",
        lambda *_a, **_kw: subprocess.CompletedProcess([], 0, "", ""),
    )

    response = client.post(
        "/api/identity/rebuild-face-clusters",
        json={"eps": 0.4, "confirmation_token": "tok-capture-failure"},
    )

    assert response.status_code == 500, response.text
    assert process.input_stream.writes == []
    assert events.index("stdin_close") < events.index("terminate")
    persisted = ActionJobLedger(identity_dir / "process_jobs").list_records()[0]
    assert persisted["state"] == "failed"
    assert "child_pid" not in persisted
    assert len(authority.audit_calls) == 1


def test_child_registration_cas_failure_preserves_record_and_never_sends_marker(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_dir = tmp_path / "cas-failure"
    identity_dir.mkdir()
    events: list[str] = []
    process = _FakeProcess(events, wait_results=[1])
    authority = _Authority()
    _install_rebuild_fakes(monkeypatch, identity_dir, process, authority)
    real_ledger = ActionJobLedger

    class _FailingRegistrationLedger(real_ledger):
        before_registration: bytes | None = None

        def compare_and_update(self, job_id: str, **kwargs: Any) -> dict[str, Any]:
            type(self).before_registration = self.record_path(job_id).read_bytes()
            raise identity_route.ActionJobTransitionError("simulated stale owner")

    monkeypatch.setattr(identity_route, "ActionJobLedger", _FailingRegistrationLedger)
    monkeypatch.setattr(
        identity_route.subprocess,
        "run",
        lambda *_a, **_kw: subprocess.CompletedProcess([], 0, "", ""),
    )

    response = client.post(
        "/api/identity/rebuild-face-clusters",
        json={"eps": 0.4, "confirmation_token": "tok-cas-failure"},
    )

    assert response.status_code == 500, response.text
    assert process.input_stream.writes == []
    records = real_ledger(identity_dir / "process_jobs").list_records()
    assert len(records) == 1
    path = real_ledger(identity_dir / "process_jobs").record_path(records[0]["job_id"])
    assert path.read_bytes() == _FailingRegistrationLedger.before_registration
    assert records[0]["state"] == "running"
    assert "child_pid" not in records[0]
    assert authority.audit_calls == []


def test_popen_value_error_terminalizes_with_opaque_target_evidence(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_dir = tmp_path / "popen-value-error"
    identity_dir.mkdir()
    authority = _Authority()
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))
    monkeypatch.setattr(identity_route, "_epoch_id", lambda: "epoch-test")
    monkeypatch.setattr(identity_route, "MiniAgentClient", lambda **_kw: authority)

    def fail_spawn(*_args: Any, **_kwargs: Any) -> None:
        (identity_dir / "face_clusters.json").write_text(
            json.dumps(_valid_manifest()), encoding="utf-8"
        )
        raise ValueError("SUBPROCESS_SENTINEL private spawn detail")

    monkeypatch.setattr(identity_route.subprocess, "Popen", fail_spawn)

    response = client.post(
        "/api/identity/rebuild-face-clusters",
        json={"eps": 0.4, "confirmation_token": "tok-popen-value"},
    )

    assert response.status_code == 500, response.text
    assert response.json() == {"detail": "face_cluster_rebuild_failed"}
    assert "SUBPROCESS_SENTINEL" not in response.text
    persisted = ActionJobLedger(identity_dir / "process_jobs").list_records()[0]
    assert persisted["state"] == "failed"
    assert authority.audit_calls[0]["side_effect_report"] == {
        "mutated": True,
        "targets": [
            "face_clusters.json",
            "reports/face_cluster_sheet.html",
        ],
    }


def test_rebuild_logs_exclude_launch_child_and_subprocess_sentinels(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    identity_dir = tmp_path / "opaque-logs"
    identity_dir.mkdir()
    events: list[str] = []
    process = _FakeProcess(
        events,
        pid=987654321,
        returncode=7,
        communicate_results=[
            (
                "SUBPROCESS_STDOUT_SENTINEL launch_protocol=stdin_gate_v1",
                "SUBPROCESS_STDERR_SENTINEL child_start_token=deadbeefcafebabe",
            )
        ],
    )
    authority = _Authority()
    _install_rebuild_fakes(monkeypatch, identity_dir, process, authority)
    monkeypatch.setattr(
        identity_route,
        "_probe_process_start_token",
        lambda pid: ("live", "deadbeefcafebabe")
        if pid == process.pid
        else ("unknown", None),
    )
    caplog.set_level("DEBUG", logger="api.routes.identity")

    response = client.post(
        "/api/identity/rebuild-face-clusters",
        json={"eps": 0.4, "confirmation_token": "tok-log-opacity"},
    )

    assert response.status_code == 500, response.text
    combined = caplog.text + response.text + json.dumps(authority.audit_calls)
    for sentinel in (
        "SUBPROCESS_STDOUT_SENTINEL",
        "SUBPROCESS_STDERR_SENTINEL",
        "stdin_gate_v1",
        "987654321",
        "deadbeefcafebabe",
    ):
        assert sentinel not in combined


def _invalid_manifest(case: str) -> Any:
    manifest = _valid_manifest()
    cluster = manifest["clusters"][0]
    if case == "malformed":
        return "{not-json"
    if case == "list":
        return []
    if case == "scalar":
        return 7
    if case == "thin":
        return {"clusters": []}
    if case == "wrong_epoch":
        manifest["epoch_id"] = "other-epoch"
    elif case == "wrong_eps":
        manifest["eps_used"] = 0.40000000001
    elif case == "eps_nonfinite":
        manifest["eps_used"] = math.inf
    elif case == "eps_bool":
        manifest["eps_used"] = True
    elif case == "generated_at_empty":
        manifest["generated_at"] = ""
    elif case == "generated_at_naive":
        manifest["generated_at"] = "2026-07-20T12:00:00"
    elif case == "note_empty":
        manifest["note"] = "   "
    elif case == "cluster_count_bool":
        manifest["cluster_count"] = True
    elif case == "cluster_count_negative":
        manifest["cluster_count"] = -1
    elif case == "cluster_count_mismatch":
        manifest["cluster_count"] = 2
    elif case == "unassigned_count_bool":
        manifest["unassigned_count"] = True
    elif case == "unassigned_count_negative":
        manifest["unassigned_count"] = -1
    elif case == "unassigned_count_mismatch":
        manifest["unassigned_count"] = 0
    elif case == "clusters_wrong_type":
        manifest["clusters"] = {}
    elif case == "unassigned_wrong_type":
        manifest["unassigned_face_ids"] = {}
    elif case == "cluster_non_dict":
        manifest["clusters"] = [7]
    elif case == "cluster_missing_key":
        del cluster["representative_frame"]
    elif case == "cluster_id_shape":
        cluster["cluster_id"] = "cluster-zero"
    elif case == "cluster_status":
        cluster["status"] = "confirmed"
    elif case == "cluster_label":
        cluster["label"] = "Alice"
    elif case == "cluster_confirmed":
        cluster["confirmed"] = True
    elif case == "face_count_bool":
        cluster["face_count"] = True
    elif case == "face_count_mismatch":
        cluster["face_count"] = 1
    elif case == "video_count_bool":
        cluster["video_count"] = True
    elif case == "video_count_mismatch":
        cluster["video_count"] = 2
    elif case == "video_hashes_empty":
        cluster["video_hashes"] = []
        cluster["video_count"] = 0
    elif case == "video_hashes_duplicate":
        cluster["video_hashes"] = ["video-a", "video-a"]
        cluster["video_count"] = 2
    elif case == "video_hash_nonstring":
        cluster["video_hashes"] = [7]
    elif case == "face_ids_empty":
        cluster["face_ids"] = []
        cluster["face_count"] = 0
    elif case == "face_ids_duplicate":
        cluster["face_ids"] = ["face-a", "face-a"]
    elif case == "face_id_nonstring":
        cluster["face_ids"] = ["face-a", 7]
    elif case == "timestamp_shape":
        cluster["timestamp_range"] = [1.0]
    elif case == "timestamp_nonfinite":
        cluster["timestamp_range"] = [1.0, math.inf]
    elif case == "timestamp_bool":
        cluster["timestamp_range"] = [True, 2.0]
    elif case == "timestamp_descending":
        cluster["timestamp_range"] = [2.0, 1.0]
    elif case == "representative_empty":
        cluster["representative_frame"] = ""
    elif case == "representative_wrong_type":
        cluster["representative_frame"] = 7
    elif case == "duplicate_cluster_id":
        second = copy.deepcopy(cluster)
        second["face_ids"] = ["face-d", "face-e"]
        second["representative_frame"] = "frame-b.jpg"
        manifest["clusters"].append(second)
        manifest["cluster_count"] = 2
    elif case == "face_id_cross_cluster":
        second = copy.deepcopy(cluster)
        second["cluster_id"] = "face_cluster_1"
        second["face_ids"] = ["face-a", "face-d"]
        second["representative_frame"] = "frame-b.jpg"
        manifest["clusters"].append(second)
        manifest["cluster_count"] = 2
    elif case == "unassigned_duplicate":
        manifest["unassigned_face_ids"] = ["face-c", "face-c"]
        manifest["unassigned_count"] = 2
    elif case == "unassigned_overlap":
        manifest["unassigned_face_ids"] = ["face-a"]
    elif case == "unassigned_empty":
        manifest["unassigned_face_ids"] = [""]
    elif case == "unassigned_nonstring":
        manifest["unassigned_face_ids"] = [7]
    return manifest


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "malformed",
        "list",
        "scalar",
        "thin",
        "wrong_epoch",
        "wrong_eps",
        "eps_nonfinite",
        "eps_bool",
        "generated_at_empty",
        "generated_at_naive",
        "note_empty",
        "cluster_count_bool",
        "cluster_count_negative",
        "cluster_count_mismatch",
        "unassigned_count_bool",
        "unassigned_count_negative",
        "unassigned_count_mismatch",
        "clusters_wrong_type",
        "unassigned_wrong_type",
        "cluster_non_dict",
        "cluster_missing_key",
        "cluster_id_shape",
        "cluster_status",
        "cluster_label",
        "cluster_confirmed",
        "face_count_bool",
        "face_count_mismatch",
        "video_count_bool",
        "video_count_mismatch",
        "video_hashes_empty",
        "video_hashes_duplicate",
        "video_hash_nonstring",
        "face_ids_empty",
        "face_ids_duplicate",
        "face_id_nonstring",
        "timestamp_shape",
        "timestamp_nonfinite",
        "timestamp_bool",
        "timestamp_descending",
        "representative_empty",
        "representative_wrong_type",
        "duplicate_cluster_id",
        "face_id_cross_cluster",
        "unassigned_duplicate",
        "unassigned_overlap",
        "unassigned_empty",
        "unassigned_nonstring",
    ],
)
def test_successful_child_requires_generator_shaped_manifest_before_success_audit(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    identity_dir = tmp_path / case
    identity_dir.mkdir()
    manifest_path = identity_dir / "face_clusters.json"
    if case != "missing":
        invalid = _invalid_manifest(case)
        if isinstance(invalid, str):
            manifest_path.write_text(invalid, encoding="utf-8")
        else:
            manifest_path.write_text(json.dumps(invalid), encoding="utf-8")
    events: list[str] = []
    process = _FakeProcess(events)
    authority = _Authority()
    _install_rebuild_fakes(monkeypatch, identity_dir, process, authority)
    monkeypatch.setattr(
        identity_route.subprocess,
        "run",
        lambda *_a, **_kw: subprocess.CompletedProcess([], 0, "", ""),
    )

    response = client.post(
        "/api/identity/rebuild-face-clusters",
        json={"eps": 0.4, "confirmation_token": "tok-invalid"},
    )

    assert response.status_code == 500, (case, response.text)
    assert response.json() == {"detail": "face_cluster_rebuild_failed"}
    persisted = ActionJobLedger(identity_dir / "process_jobs").list_records()[0]
    assert persisted["state"] == "failed"
    assert all(call["status"] != "succeeded" for call in authority.audit_calls)


def test_generator_shaped_manifest_with_extensions_succeeds(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_dir = tmp_path / "identity"
    identity_dir.mkdir()
    manifest = _valid_manifest()
    manifest["future_top_level"] = {"version": 2}
    manifest["clusters"][0]["future_cluster_field"] = ["accepted"]
    manifest_path = identity_dir / "face_clusters.json"
    process = _FakeProcess(
        [],
        on_communicate=lambda: manifest_path.write_text(
            json.dumps(manifest), encoding="utf-8"
        ),
    )
    authority = _Authority()
    popen = _install_rebuild_fakes(monkeypatch, identity_dir, process, authority)
    run = MagicMock(return_value=subprocess.CompletedProcess([], 0, "", ""))
    monkeypatch.setattr(identity_route.subprocess, "run", run)

    response = client.post(
        "/api/identity/rebuild-face-clusters",
        json={"eps": 0.4, "confirmation_token": "tok-valid"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["future_top_level"] == {"version": 2}
    assert response.json()["clusters"][0]["future_cluster_field"] == ["accepted"]
    assert authority.audit_calls[0]["status"] == "succeeded"
    popen.assert_called_once()
    run.assert_not_called()


@pytest.mark.parametrize("changed", [False, True])
def test_nonzero_child_uses_conclusive_target_comparison_for_mutation_truth(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed: bool,
) -> None:
    identity_dir = tmp_path / ("changed" if changed else "unchanged")
    identity_dir.mkdir()
    manifest_path = identity_dir / "face_clusters.json"
    manifest_path.write_text(json.dumps(_valid_manifest()), encoding="utf-8")

    def mutate() -> None:
        if changed:
            manifest_path.write_text(
                json.dumps(_valid_manifest(eps=0.41)), encoding="utf-8"
            )

    process = _FakeProcess([], returncode=7, on_communicate=mutate)
    authority = _Authority()
    _install_rebuild_fakes(monkeypatch, identity_dir, process, authority)

    def old_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        mutate()
        return subprocess.CompletedProcess([], 7, "", "")

    monkeypatch.setattr(identity_route.subprocess, "run", old_run)

    response = client.post(
        "/api/identity/rebuild-face-clusters",
        json={"eps": 0.4, "confirmation_token": "tok-nonzero"},
    )

    assert response.status_code == 500, response.text
    assert authority.audit_calls[0]["side_effect_report"]["mutated"] is changed


def test_nonzero_child_with_sheet_only_change_audits_both_sanitized_targets(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_dir = tmp_path / "sheet-only-change"
    reports_dir = identity_dir / "reports"
    reports_dir.mkdir(parents=True)
    manifest_path = identity_dir / "face_clusters.json"
    sheet_path = reports_dir / "face_cluster_sheet.html"
    manifest_path.write_text(json.dumps(_valid_manifest()), encoding="utf-8")
    sheet_path.write_text("before", encoding="utf-8")

    process = _FakeProcess(
        [],
        returncode=7,
        on_communicate=lambda: sheet_path.write_text("after", encoding="utf-8"),
    )
    authority = _Authority()
    _install_rebuild_fakes(monkeypatch, identity_dir, process, authority)

    response = client.post(
        "/api/identity/rebuild-face-clusters",
        json={"eps": 0.4, "confirmation_token": "tok-sheet-change"},
    )

    assert response.status_code == 500, response.text
    assert authority.audit_calls[0]["side_effect_report"] == {
        "mutated": True,
        "targets": [
            "face_clusters.json",
            "reports/face_cluster_sheet.html",
        ],
    }


def test_timeout_proves_terminate_wait_kill_wait_drain_and_audits_changed_target(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_dir = tmp_path / "timeout"
    identity_dir.mkdir()
    manifest_path = identity_dir / "face_clusters.json"
    manifest_path.write_text(json.dumps(_valid_manifest()), encoding="utf-8")
    events: list[str] = []

    def mutate() -> None:
        manifest_path.write_text(json.dumps(_valid_manifest(eps=0.41)), encoding="utf-8")

    process = _FakeProcess(
        events,
        on_communicate=mutate,
        communicate_results=[subprocess.TimeoutExpired("builder", 120), ("", "")],
        wait_results=[subprocess.TimeoutExpired("builder", 2), -9],
    )
    authority = _Authority()
    _install_rebuild_fakes(monkeypatch, identity_dir, process, authority)

    def old_run(*_args: Any, **_kwargs: Any) -> Any:
        mutate()
        raise subprocess.TimeoutExpired("builder", 120)

    monkeypatch.setattr(identity_route.subprocess, "run", old_run)

    response = client.post(
        "/api/identity/rebuild-face-clusters",
        json={"eps": 0.4, "confirmation_token": "tok-timeout"},
    )

    assert response.status_code == 500, response.text
    failure_sequence = [event for event in events if event in {"terminate", "wait", "kill", "communicate"}]
    assert failure_sequence == ["communicate", "terminate", "wait", "kill", "wait", "communicate"]
    assert authority.audit_calls[0]["side_effect_report"]["mutated"] is True


def test_post_gate_flush_failure_with_unknown_death_preserves_running_pair_without_audit(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_dir = tmp_path / "unknown-death"
    identity_dir.mkdir()
    (identity_dir / "face_clusters.json").write_text(
        json.dumps(_valid_manifest()), encoding="utf-8"
    )
    events: list[str] = []
    process = _FakeProcess(
        events,
        stdin_flush_error=BrokenPipeError("marker status unknown"),
        wait_results=[subprocess.TimeoutExpired("builder", 2), OSError("wait unavailable")],
    )
    authority = _Authority()
    _install_rebuild_fakes(monkeypatch, identity_dir, process, authority)
    monkeypatch.setattr(
        identity_route.subprocess,
        "run",
        lambda *_a, **_kw: subprocess.CompletedProcess([], 0, "", ""),
    )

    response = client.post(
        "/api/identity/rebuild-face-clusters",
        json={"eps": 0.4, "confirmation_token": "tok-flush"},
    )

    assert response.status_code == 500, response.text
    persisted = ActionJobLedger(identity_dir / "process_jobs").list_records()[0]
    assert persisted["state"] == "running"
    assert persisted["child_pid"] == 4321
    assert persisted["child_start_token"] == "abc123"
    assert authority.audit_calls == []
    assert events.count("stdin_write") == 1
    assert events.count("stdin_flush") == 1
    assert "terminate" in events and "kill" in events
