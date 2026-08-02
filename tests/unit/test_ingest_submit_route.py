from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agents.mini_agent_client import MiniAgentClient
from api.route_effects import ROUTE_EFFECTS, install_route_effect_authority


def _load_route_module():
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    module_path = repo_root / "api" / "routes" / "ingest.py"
    spec = importlib.util.spec_from_file_location("tests.ingest_route", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ingest_module = _load_route_module()


@pytest.fixture(autouse=True)
def _treat_starlette_testclient_as_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep local-ingest tests local on Starlette versions using testclient."""
    from api import route_effects

    original = route_effects.is_loopback_client
    monkeypatch.setattr(
        route_effects,
        "is_loopback_client",
        lambda client: client == ("testclient", 50000) or original(client),
    )


def _runtime_paths(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "ingest_requests": tmp_path / "ingest_requests",
        "import_inbox": tmp_path / "import_inbox",
        "processing": tmp_path / "processing",
        "processed": tmp_path / "processed",
        "failed": tmp_path / "failed",
        "watchdog_state_file": tmp_path / "logs" / "watchdog_state.json",
    }
    for path in paths.values():
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path.mkdir(parents=True, exist_ok=True)
    return paths


def _client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[TestClient, dict[str, Path], MiniAgentClient]:
    runtime_paths = _runtime_paths(tmp_path)
    authority = MiniAgentClient(
        profile="safe",
        config={"agent": {"execution_mode": "in_process"}},
    )
    monkeypatch.setattr(
        ingest_module, "get_ingest_runtime_paths", lambda: runtime_paths
    )
    monkeypatch.setattr(ingest_module, "get_ingest_authority", lambda: authority)
    app = FastAPI()
    app.include_router(ingest_module.router)
    install_route_effect_authority(
        app,
        registry={
            operation: ROUTE_EFFECTS[operation]
            for operation in (
                ("POST", "/api/ingest/submit"),
                ("GET", "/api/ingest/status/{request_id}"),
            )
        },
    )
    return (
        TestClient(app, client=("127.0.0.1", 50000)),
        runtime_paths,
        authority,
    )


def _prepare(client: TestClient, name: str, content: bytes):
    return client.post(
        "/api/ingest/submit",
        files={"file": (name, content, "video/mp4")},
        data={"action": "prepare", "policy_profile": "local_ingest_facade_v1"},
    )


def _confirm_payload(prepared: dict[str, object]) -> dict[str, object]:
    return {
        "action": "confirm",
        "request_id": prepared["request_id"],
        "confirmation_token": prepared["confirmation_token"],
    }


def test_prepare_returns_duplicate_without_issuing_or_restaging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, runtime_paths, _authority = _client(tmp_path, monkeypatch)
    content = b"already-completed"
    file_sha256 = hashlib.sha256(content).hexdigest()
    runtime_paths["watchdog_state_file"].write_text(
        json.dumps(
            {
                file_sha256: {
                    "status": "success",
                    "run_id": "run-321",
                    "timestamp": "2026-07-11T00:00:00Z",
                }
            }
        ),
        encoding="utf-8",
    )

    response = _prepare(client, "sample.mp4", content)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "duplicate"
    assert payload["duplicate_of_run_id"] == "run-321"
    assert payload["confirmation_required"] is False
    assert payload["confirmation_token"] is None
    assert list(runtime_paths["import_inbox"].iterdir()) == []
    pending_dir = runtime_paths["ingest_requests"] / ".pending"
    assert list(pending_dir.iterdir()) == []


def test_remote_client_cannot_prepare_mutating_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local_client, runtime_paths, _authority = _client(tmp_path, monkeypatch)
    remote_client = TestClient(
        local_client.app,
        client=("192.168.1.44", 50000),
    )

    response = _prepare(remote_client, "remote.mp4", b"remote")

    assert response.status_code == 403
    assert list(runtime_paths["ingest_requests"].glob("*.json")) == []
    assert list(runtime_paths["import_inbox"].iterdir()) == []


def test_authenticated_remote_client_cannot_confirm_with_locally_minted_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lan_token = "b" * 64
    monkeypatch.setenv("GOODQ_LAN_API_TOKEN", lan_token)
    local_client, runtime_paths, _authority = _client(tmp_path, monkeypatch)
    prepared = _prepare(local_client, "local.mp4", b"local").json()
    remote_client = TestClient(
        local_client.app,
        client=("192.168.1.44", 50000),
        headers={
            "Authorization": "Basic "
            + base64.b64encode(f"goodq:{lan_token}".encode("ascii")).decode("ascii")
        },
    )

    response = remote_client.post(
        "/api/ingest/submit",
        json=_confirm_payload(prepared),
    )

    assert response.status_code == 403
    request_record = json.loads(
        (runtime_paths["ingest_requests"] / f"{prepared['request_id']}.json").read_text(
            encoding="utf-8"
        )
    )
    assert request_record["status"] == "pending_confirmation"
    assert list(runtime_paths["import_inbox"].iterdir()) == []


def test_wrong_or_cross_request_token_never_exposes_file_to_watchdog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, runtime_paths, _authority = _client(tmp_path, monkeypatch)
    first = _prepare(client, "one.mp4", b"one").json()
    second = _prepare(client, "two.mp4", b"two").json()

    invalid = client.post(
        "/api/ingest/submit",
        json={
            "action": "confirm",
            "request_id": first["request_id"],
            "confirmation_token": "invalid-token",
        },
    )
    crossed = client.post(
        "/api/ingest/submit",
        json={
            "action": "confirm",
            "request_id": second["request_id"],
            "confirmation_token": first["confirmation_token"],
        },
    )

    assert invalid.status_code == 403
    assert crossed.status_code == 403
    assert list(runtime_paths["import_inbox"].iterdir()) == []


def test_request_id_path_traversal_is_rejected_before_ledger_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, runtime_paths, _authority = _client(tmp_path, monkeypatch)
    outside = tmp_path / "outside.json"
    outside.write_text('{"status":"forged"}', encoding="utf-8")

    confirm = client.post(
        "/api/ingest/submit",
        json={
            "action": "confirm",
            "request_id": "../../outside",
            "confirmation_token": "forged",
        },
    )
    status = client.get("/api/ingest/status/..%2F..%2Foutside")

    assert confirm.status_code == 422
    assert status.status_code in {400, 404}
    assert outside.read_text(encoding="utf-8") == '{"status":"forged"}'
    assert list(runtime_paths["import_inbox"].iterdir()) == []


def test_ordinary_move_failure_records_stage_failed_without_inbox_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, runtime_paths, _authority = _client(tmp_path, monkeypatch)
    prepared = _prepare(client, "sample.mp4", b"video").json()

    def fail_move(_source: Path, _destination: Path) -> None:
        raise OSError("simulated move failure")

    monkeypatch.setattr(ingest_module, "_place_staged_file", fail_move)
    response = client.post(
        "/api/ingest/submit",
        json=_confirm_payload(prepared),
    )

    assert response.status_code == 500
    assert list(runtime_paths["import_inbox"].iterdir()) == []
    record = json.loads(
        (
            runtime_paths["ingest_requests"] / f"{prepared['request_id']}.json"
        ).read_text(encoding="utf-8")
    )
    assert record["status"] == "stage_failed"
    assert record["error"] == "Failed to stage ingest request"


def test_authority_evidence_failure_removes_pending_copy_and_exposes_no_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, runtime_paths, authority = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(
        authority,
        "authorize_action",
        lambda **_kwargs: (
            {
                "request_id": "task-failed",
                "status": "error",
                "result": {"allowed": False},
                "errors": [{"code": "audit_log_error"}],
            },
            1,
        ),
    )

    response = _prepare(client, "sample.mp4", b"video")

    assert response.status_code == 500
    assert "confirmation_token" not in response.text
    assert list(runtime_paths["import_inbox"].iterdir()) == []
    pending_dir = runtime_paths["ingest_requests"] / ".pending"
    assert list(pending_dir.iterdir()) == []
    records = list(runtime_paths["ingest_requests"].glob("*.json"))
    assert len(records) == 1
    assert json.loads(records[0].read_text(encoding="utf-8"))["status"] == (
        "authorization_failed"
    )


def test_concurrent_confirms_stage_exactly_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, runtime_paths, _authority = _client(tmp_path, monkeypatch)
    prepared = _prepare(client, "sample.mp4", b"video").json()
    payload = _confirm_payload(prepared)

    def confirm_once() -> int:
        with TestClient(client.app, client=("127.0.0.1", 50001)) as concurrent_client:
            return concurrent_client.post(
                "/api/ingest/submit",
                json=payload,
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = sorted(pool.map(lambda _index: confirm_once(), range(2)))

    assert statuses == [202, 409]
    assert len(list(runtime_paths["import_inbox"].iterdir())) == 1


def test_confirm_cancel_race_has_one_legal_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, runtime_paths, _authority = _client(tmp_path, monkeypatch)
    prepared = _prepare(client, "sample.mp4", b"video").json()
    confirm_payload = _confirm_payload(prepared)
    cancel_payload = {
        "action": "cancel",
        "request_id": prepared["request_id"],
        "confirmation_token": prepared["confirmation_token"],
    }

    def transition(payload: dict[str, object]) -> int:
        with TestClient(client.app, client=("127.0.0.1", 50001)) as concurrent_client:
            return concurrent_client.post(
                "/api/ingest/submit",
                json=payload,
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = sorted(pool.map(transition, [confirm_payload, cancel_payload]))

    assert statuses in ([200, 409], [202, 409])
    record = json.loads(
        (
            runtime_paths["ingest_requests"] / f"{prepared['request_id']}.json"
        ).read_text(encoding="utf-8")
    )
    assert record["status"] in {"canceled", "staged"}
    assert len(list(runtime_paths["import_inbox"].iterdir())) in {0, 1}
