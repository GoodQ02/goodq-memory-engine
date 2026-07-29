"""
R-08 seam 7: Error response redaction — identity and stitch routes.
TDD contract: RED on missing redaction, GREEN after redaction is in place.

Routes under test (identity.py):
  POST /api/identity/rebuild-face-clusters  — subprocess stderr must not leak
  POST /api/identity/roster/validate        — raw subprocess output must not leak
  POST /api/identity/roster/save            — exception detail must not leak
  POST /api/identity/roster/export          — path must not leak in success response

Routes under test (system.py stitch handlers):
  GET  /api/system/identity/unstitched      — db path must not leak
  POST /api/system/identity/stitch/preview  — db path + exception detail must not leak
  POST /api/system/identity/stitch          — db path + exception detail must not leak
  GET  /api/system/identity/mappings        — exception detail must not leak
  POST /api/system/identity/stitch/revoke   — db path + exception detail must not leak

Redaction invariants:
  - No filesystem path separators (/:/ or backslash) followed by path-like chars
  - No Python exception class names in response body
  - No raw subprocess stderr/stdout content
  - Opaque snake_case error code present in detail on failure
"""
from __future__ import annotations

import json
import io
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from api.main import app


# ── Helpers ───────────────────────────────────────────────────────────────────

_PATH_PATTERN = re.compile(r"[A-Za-z]:[/\\]|/[A-Za-z_]")
_EXC_NAMES = (
    "FileNotFoundError",
    "PermissionError",
    "OSError",
    "IOError",
    "RuntimeError",
    "ValueError",
    "KeyError",
    "AttributeError",
    "TypeError",
    "Exception",
)

SENTINEL_STDERR = "SENTINEL_STDERR_SHOULD_NOT_APPEAR_IN_RESPONSE"
SENTINEL_PATH = "/SENTINEL/INTERNAL/PATH/SHOULD_NOT_APPEAR"


def _body_text(response) -> str:
    """Return the raw response body as a string for pattern checks."""
    try:
        return json.dumps(response.json())
    except Exception:
        return response.text


def _assert_no_leak(body: str) -> None:
    """Assert the body contains no path or exception class names."""
    assert not _PATH_PATTERN.search(body), (
        f"Filesystem path leaked in response body: {body[:400]}"
    )
    for exc in _EXC_NAMES:
        assert exc not in body, (
            f"Exception class name '{exc}' leaked in response body: {body[:400]}"
        )
    assert SENTINEL_STDERR not in body, (
        f"Subprocess stderr content leaked in response body: {body[:400]}"
    )
    assert SENTINEL_PATH not in body, (
        f"Internal path sentinel leaked in response body: {body[:400]}"
    )


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False, client=("127.0.0.1", 50000))


@pytest.fixture(autouse=True)
def isolate_cfg(monkeypatch):
    monkeypatch.setattr("api.routes.identity._CFG", {})


class _MockAuthority:
    """Authorized MiniAgentClient stub."""

    def __init__(self):
        self.record_calls: list = []

    def authorize_action(self, **kwargs) -> tuple[Dict[str, Any], int]:
        envelope = {
            "status": "ok",
            "request_id": "req-" + "a" * 16,
            "result": {"allowed": True},
            "errors": [],
        }
        return envelope, 0

    def record_external_execution_outcome(self, **kwargs) -> Dict[str, Any]:
        self.record_calls.append(kwargs)
        return {"audit_status": "recorded", "error_codes": []}


def _make_subprocess_result(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


# ═════════════════════════════════════════════════════════════════════════════
# rebuild_face_clusters — subprocess stderr must NOT appear in response
# ═════════════════════════════════════════════════════════════════════════════

def test_rebuild_face_clusters_stderr_not_in_response(
    client, tmp_path, monkeypatch
) -> None:
    """When build_face_clusters.py fails, stderr must not appear in HTTP response."""
    identity_dir = tmp_path / "identity"
    identity_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))

    failing_proc = _make_subprocess_result(
        returncode=1,
        stdout="",
        stderr=SENTINEL_STDERR,
    )
    failing_proc.pid = 4321
    failing_proc.stdin = io.StringIO()
    failing_proc.communicate.return_value = ("", SENTINEL_STDERR)
    mock_authority = _MockAuthority()

    with patch("api.routes.identity.MiniAgentClient", return_value=mock_authority), \
         patch("api.routes.identity.subprocess.Popen", return_value=failing_proc), \
         patch("api.routes.identity._probe_process_start_token", return_value=("live", "abc123")), \
         patch("api.routes.identity._epoch_id", return_value="epoch_test"):
        response = client.post(
            "/api/identity/rebuild-face-clusters",
            json={"confirmation_token": "tok-valid"},
        )

    assert response.status_code == 500, response.text
    body = _body_text(response)
    assert SENTINEL_STDERR not in body, (
        f"Subprocess stderr leaked: {body[:400]}"
    )
    # Opaque error code must be present
    assert "face_cluster_rebuild_failed" in body, (
        f"Expected opaque error code 'face_cluster_rebuild_failed' in: {body[:400]}"
    )


# ═════════════════════════════════════════════════════════════════════════════
# validate_roster — raw subprocess output must NOT appear in response
# ═════════════════════════════════════════════════════════════════════════════

def test_validate_roster_raw_output_not_in_response(
    client, tmp_path, monkeypatch, caplog
) -> None:
    """validate_roster must NOT include raw subprocess stdout/stderr in response."""
    script_path = (
        Path(repo_root) / "scripts" / "identity" / "validate_roster.py"
    )
    identity_dir = tmp_path / "identity"
    identity_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))

    raw_output = (
        f" ✓ {SENTINEL_STDERR} passed at {SENTINEL_PATH}\n"
        f" ⚠ {SENTINEL_STDERR} warning at {SENTINEL_PATH}\n"
        f" ✗ {SENTINEL_STDERR} failed at {SENTINEL_PATH}\n"
        f"[ERROR] RuntimeError: {SENTINEL_STDERR} at {SENTINEL_PATH}\n"
    )
    proc = _make_subprocess_result(returncode=0, stdout=raw_output, stderr="")
    mock_authority = _MockAuthority()
    caplog.set_level(logging.DEBUG, logger="api.routes.identity")

    with patch("api.routes.identity.MiniAgentClient", return_value=mock_authority), \
         patch("api.routes.identity.subprocess.run", return_value=proc):
        response = client.post(
            "/api/identity/roster/validate",
            json={"confirmation_token": "tok-valid"},
        )

    assert response.status_code == 200, response.text
    body = _body_text(response)
    assert SENTINEL_STDERR not in body, (
        f"Raw subprocess output leaked in validate response: {body[:400]}"
    )
    # The 'raw' key must be absent or redacted
    assert "\"raw\"" not in body, (
        f"'raw' subprocess output field must not appear in response: {body[:400]}"
    )
    assert response.json()["passed"] == ["validation_check_passed"]
    assert response.json()["warnings"] == ["validation_check_warning"]
    assert response.json()["errors"] == [
        "validation_check_failed",
        "validation_error",
    ]
    assert SENTINEL_STDERR not in caplog.text
    assert SENTINEL_PATH not in caplog.text


def test_validate_roster_returns_allowlisted_actionable_conflicts(
    client, tmp_path, monkeypatch
) -> None:
    identity_dir = tmp_path / "identity"
    identity_dir.mkdir()
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))
    raw_output = (
        " ✗ Face cluster 'face_cluster_9' is assigned to multiple identities — conflict\n"
        f" ✗ {SENTINEL_STDERR} at {SENTINEL_PATH}\n"
    )
    proc = _make_subprocess_result(returncode=1, stdout=raw_output, stderr="")
    mock_authority = _MockAuthority()

    with patch("api.routes.identity.MiniAgentClient", return_value=mock_authority), \
         patch("api.routes.identity.subprocess.run", return_value=proc):
        response = client.post(
            "/api/identity/roster/validate",
            json={"confirmation_token": "tok-valid"},
        )

    assert response.status_code == 200
    assert response.json()["errors"] == [
        {
            "code": "face_cluster_multiple_owners",
            "cluster_id": "face_cluster_9",
            "message": "Face cluster face_cluster_9 is assigned to multiple identities.",
        },
        "validation_check_failed",
    ]
    assert SENTINEL_STDERR not in response.text
    assert SENTINEL_PATH not in response.text


# ═════════════════════════════════════════════════════════════════════════════
# save_roster — exception detail must NOT appear in response
# ═════════════════════════════════════════════════════════════════════════════

def test_save_roster_exception_not_in_response(
    client, tmp_path, monkeypatch
) -> None:
    """When roster save fails with an OS error, exception message must not appear."""
    identity_dir = tmp_path / "identity"
    identity_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))

    mock_authority = _MockAuthority()

    def _exploding_replace(src, dst):
        raise PermissionError(f"PermissionError: [Errno 13] Access denied: '{SENTINEL_PATH}'")

    with patch("api.routes.identity.MiniAgentClient", return_value=mock_authority), \
         patch("api.routes.identity.os.replace", side_effect=_exploding_replace):
        response = client.post(
            "/api/identity/roster/save",
            json={
                "identity": {"id": "person_001", "name": "Test"},
                "confirmation_token": "tok-valid",
            },
        )

    assert response.status_code == 500, response.text
    body = _body_text(response)
    _assert_no_leak(body)
    assert "roster_save_failed" in body, (
        f"Expected opaque error code 'roster_save_failed' in: {body[:400]}"
    )


# ═════════════════════════════════════════════════════════════════════════════
# export_roster — filesystem path must NOT appear in success response
# ═════════════════════════════════════════════════════════════════════════════

def test_export_roster_path_not_in_success_response(
    client, tmp_path, monkeypatch
) -> None:
    """export_roster success response must not include the filesystem path."""
    identity_dir = tmp_path / "identity"
    identity_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))

    mock_authority = _MockAuthority()

    with patch("api.routes.identity.MiniAgentClient", return_value=mock_authority):
        response = client.post(
            "/api/identity/roster/export",
            json={
                "identities": [{"id": "p1", "name": "Alice"}],
                "confirmation_token": "tok-valid",
            },
        )

    assert response.status_code == 200, response.text
    body = _body_text(response)
    # "path" field in success response must not be present
    assert "\"path\"" not in body, (
        f"Filesystem 'path' field must not appear in export response: {body[:400]}"
    )
    _assert_no_leak(body)


# ═════════════════════════════════════════════════════════════════════════════
# export_roster — exception detail must NOT appear in error response
# ═════════════════════════════════════════════════════════════════════════════

def test_export_roster_exception_not_in_response(
    client, tmp_path, monkeypatch
) -> None:
    """When export write fails, exception message must not appear in HTTP response."""
    identity_dir = tmp_path / "identity"
    identity_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("GOODQ_IDENTITY_PATH", str(identity_dir))

    mock_authority = _MockAuthority()

    def _exploding_replace(src, dst):
        raise OSError(f"OSError: disk full writing '{SENTINEL_PATH}'")

    with patch("api.routes.identity.MiniAgentClient", return_value=mock_authority), \
         patch("api.routes.identity.os.replace", side_effect=_exploding_replace):
        response = client.post(
            "/api/identity/roster/export",
            json={
                "identities": [{"id": "p1", "name": "Alice"}],
                "confirmation_token": "tok-valid",
            },
        )

    assert response.status_code == 500, response.text
    body = _body_text(response)
    _assert_no_leak(body)
    assert "roster_export_failed" in body, (
        f"Expected opaque error code 'roster_export_failed' in: {body[:400]}"
    )


# ═════════════════════════════════════════════════════════════════════════════
# system.py stitch routes — db path must not leak in 404
# ═════════════════════════════════════════════════════════════════════════════

def test_unstitched_db_path_not_in_404(client, tmp_path, monkeypatch) -> None:
    """GET /api/system/identity/unstitched — db path must not appear in 404 response."""
    with patch("api.routes.system._get_kg_db_path", return_value=tmp_path / "nonexistent.db"):
        response = client.get("/api/system/identity/unstitched")

    assert response.status_code == 404, response.text
    body = _body_text(response)
    _assert_no_leak(body)
    assert "knowledge_graph_not_found" in body, (
        f"Expected opaque error code 'knowledge_graph_not_found' in: {body[:400]}"
    )


def test_preview_stitch_db_path_not_in_404(client, tmp_path, monkeypatch) -> None:
    """POST /api/system/identity/stitch/preview — db path must not appear in 404 response."""
    with patch("api.routes.system._get_kg_db_path", return_value=tmp_path / "nonexistent.db"):
        response = client.post(
            "/api/system/identity/stitch/preview",
            json={"source_node_name": "SPK_001", "target_person_name": "Alice"},
        )

    assert response.status_code == 404, response.text
    body = _body_text(response)
    _assert_no_leak(body)
    assert "knowledge_graph_not_found" in body, (
        f"Expected opaque error code 'knowledge_graph_not_found' in: {body[:400]}"
    )


def test_preview_stitch_exception_not_in_response(client, tmp_path) -> None:
    """POST /api/system/identity/stitch/preview — exception detail must not appear."""
    real_db = tmp_path / "kg.db"
    real_db.write_bytes(b"")  # exists but not valid SQLite

    with patch("api.routes.system._get_kg_db_path", return_value=real_db):
        response = client.post(
            "/api/system/identity/stitch/preview",
            json={"source_node_name": "SPK_001", "target_person_name": "Alice"},
        )

    assert response.status_code == 500, response.text
    body = _body_text(response)
    _assert_no_leak(body)
    assert "stitch_preview_failed" in body, (
        f"Expected opaque error code 'stitch_preview_failed' in: {body[:400]}"
    )


def test_execute_stitch_db_path_not_in_404(client, tmp_path) -> None:
    """POST /api/system/identity/stitch — db path must not appear in 404 response."""
    mock_authority = _MockAuthority()
    with patch("api.routes.system.MiniAgentClient", return_value=mock_authority), \
         patch("api.routes.system._get_kg_db_path", return_value=tmp_path / "nonexistent.db"):
        response = client.post(
            "/api/system/identity/stitch",
            json={
                "source_node_name": "SPK_001",
                "target_person_name": "Alice",
                "confirm": True,
                "confirmation_token": "tok-valid",
            },
        )

    assert response.status_code == 404, response.text
    body = _body_text(response)
    _assert_no_leak(body)
    assert "knowledge_graph_not_found" in body, (
        f"Expected opaque error code 'knowledge_graph_not_found' in: {body[:400]}"
    )


def test_execute_stitch_exception_not_in_response(client, tmp_path) -> None:
    """POST /api/system/identity/stitch — exception detail must not appear in 500."""
    real_db = tmp_path / "kg.db"
    real_db.write_bytes(b"")  # exists but not valid SQLite

    mock_authority = _MockAuthority()
    with patch("api.routes.system.MiniAgentClient", return_value=mock_authority), \
         patch("api.routes.system._get_kg_db_path", return_value=real_db):
        response = client.post(
            "/api/system/identity/stitch",
            json={
                "source_node_name": "SPK_001",
                "target_person_name": "Alice",
                "confirm": True,
                "confirmation_token": "tok-valid",
            },
        )

    assert response.status_code == 500, response.text
    body = _body_text(response)
    _assert_no_leak(body)
    assert "stitch_execute_failed" in body, (
        f"Expected opaque error code 'stitch_execute_failed' in: {body[:400]}"
    )


def test_get_mappings_exception_not_in_response(client, tmp_path) -> None:
    """GET /api/system/identity/mappings — exception detail must not appear."""
    with patch("api.routes.system._get_kg_db_path", return_value=tmp_path / "nonexistent.db"), \
         patch(
             "api.routes.system.load_manual_mappings",
             side_effect=OSError(f"OSError: cannot open '{SENTINEL_PATH}'"),
         ):
        response = client.get("/api/system/identity/mappings")

    # Either 500 or whatever the handler returns on failure
    assert response.status_code in (500,), response.text
    body = _body_text(response)
    _assert_no_leak(body)
    assert "mappings_load_failed" in body, (
        f"Expected opaque error code 'mappings_load_failed' in: {body[:400]}"
    )


def test_revoke_stitch_db_path_not_in_404(client, tmp_path) -> None:
    """POST /api/system/identity/stitch/revoke — db path must not appear in 404."""
    mock_authority = _MockAuthority()
    with patch("api.routes.system.MiniAgentClient", return_value=mock_authority), \
         patch("api.routes.system._get_kg_db_path", return_value=tmp_path / "nonexistent.db"):
        response = client.post(
            "/api/system/identity/stitch/revoke",
            json={
                "mapping_id": "map_20260101_120000",
                "confirmation_token": "tok-valid",
            },
        )

    assert response.status_code == 404, response.text
    body = _body_text(response)
    _assert_no_leak(body)
    assert "knowledge_graph_not_found" in body, (
        f"Expected opaque error code 'knowledge_graph_not_found' in: {body[:400]}"
    )


def test_revoke_stitch_exception_not_in_response(client, tmp_path) -> None:
    """POST /api/system/identity/stitch/revoke — exception detail must not appear in 500."""
    real_db = tmp_path / "kg.db"
    real_db.write_bytes(b"")

    mock_authority = _MockAuthority()
    with patch("api.routes.system.MiniAgentClient", return_value=mock_authority), \
         patch("api.routes.system._get_kg_db_path", return_value=real_db), \
         patch(
             "api.routes.system.load_manual_mappings",
             side_effect=RuntimeError(f"RuntimeError: internal error at '{SENTINEL_PATH}'"),
         ):
        response = client.post(
            "/api/system/identity/stitch/revoke",
            json={
                "mapping_id": "map_20260101_120000",
                "confirmation_token": "tok-valid",
            },
        )

    assert response.status_code == 500, response.text
    body = _body_text(response)
    _assert_no_leak(body)
    assert "stitch_revoke_failed" in body, (
        f"Expected opaque error code 'stitch_revoke_failed' in: {body[:400]}"
    )
