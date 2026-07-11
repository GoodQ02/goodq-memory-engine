from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from agents.mini_agent_client import MiniAgentClient


def _audit_path() -> Path:
    import os

    return Path(os.environ["GOODQ_TOOL_AUDIT_LOG"])


def _rows() -> list[dict]:
    path = _audit_path()
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _client() -> MiniAgentClient:
    client = MiniAgentClient(
        profile="safe",
        config={"agent": {"execution_mode": "in_process"}},
    )
    client.agent_available = True
    return client


def test_decision_audit_is_durable_redacted_and_path_sanitized():
    client = _client()
    prompt = "PRIVATE PROMPT MUST NOT BE LOGGED"
    args = {
        "input_dir": r"C:\private\incoming.mp4",
        "authorization": "Bearer private-auth",
        "nested": {
            "password": "private-password",
            "HA_TOKEN": "private-ha-token",
            "confirmation_token": "private-confirmation-token",
            "safe": "retained",
        },
    }

    envelope, rc = client.validate_action(
        prompt=prompt,
        mode="ops",
        tool_name="run_ingestion",
        tool_args=args,
    )

    assert rc == 3
    assert envelope["status"] == "needs_confirmation"
    rows = _rows()
    assert len(rows) == 1
    row = rows[0]
    assert row["schema_version"] == "goodq.tool-audit.v1"
    assert row["event_type"] == "decision"
    assert row["tool_name"] == "run_ingestion"
    assert row["status"] == "needs_confirmation"
    assert row["return_code"] == 3
    assert row["arguments"]["input_dir"] == "relative/incoming.mp4"
    assert row["arguments"]["authorization"] == "[REDACTED]"
    assert row["arguments"]["nested"] == {
        "password": "[REDACTED]",
        "HA_TOKEN": "[REDACTED]",
        "confirmation_token": "[REDACTED]",
        "safe": "retained",
    }
    serialized = _audit_path().read_text(encoding="utf-8")
    for forbidden in (
        prompt,
        "private-auth",
        "private-password",
        "private-ha-token",
        "private-confirmation-token",
        "C:\\private",
    ):
        assert forbidden not in serialized


def test_confirmed_execution_appends_decision_and_execution_rows():
    client = _client()
    args = {"input_dir": "incoming", "epoch": "epoch-one"}
    handler = MagicMock(return_value={"status": "staged_complete"})
    client._execute_run_ingestion = handler

    confirmation, confirmation_rc = client.validate_action(
        prompt="Request ingestion",
        mode="ops",
        tool_name="run_ingestion",
        tool_args=args,
    )
    assert confirmation_rc == 3

    result, rc = client.execute_tool(
        tool_name="run_ingestion",
        tool_args=args,
        mode="ops",
        confirm=True,
        confirmation_token=confirmation["result"]["confirmation_token"],
    )

    assert rc == 0
    assert result["status"] == "success"
    handler.assert_called_once_with(args)
    rows = _rows()
    assert [row["event_type"] for row in rows] == [
        "decision",
        "decision",
        "execution",
    ]
    execution = rows[-1]
    assert execution["status"] == "success"
    assert execution["return_code"] == 0
    assert execution["duration_ms"] >= 0
    assert execution["side_effect_report"]["mutated"] is True
    assert execution["error_codes"] == []


def test_handler_failure_appends_execution_failure_row():
    client = _client()
    args = {"input_dir": "incoming", "epoch": "epoch-one"}
    client._execute_run_ingestion = MagicMock(side_effect=RuntimeError("boom"))

    confirmation, confirmation_rc = client.validate_action(
        prompt="Request ingestion",
        mode="ops",
        tool_name="run_ingestion",
        tool_args=args,
    )
    assert confirmation_rc == 3
    result, rc = client.execute_tool(
        tool_name="run_ingestion",
        tool_args=args,
        mode="ops",
        confirm=True,
        confirmation_token=confirmation["result"]["confirmation_token"],
    )

    assert rc == 1
    assert result["status"] == "fatal_error"
    execution = _rows()[-1]
    assert execution["event_type"] == "execution"
    assert execution["status"] == "fatal_error"
    assert execution["return_code"] == 1
    assert execution["error_codes"] == ["execution_failed"]


def test_decision_audit_failure_is_fail_closed_before_handler(monkeypatch):
    client = _client()
    handler = MagicMock(return_value={"status": "staged_complete"})
    client._execute_run_ingestion = handler
    monkeypatch.setattr(
        client,
        "_append_tool_audit",
        MagicMock(side_effect=OSError("audit unavailable")),
    )

    result, rc = client.execute_tool(
        tool_name="run_ingestion",
        tool_args={"input_dir": "incoming", "epoch": "epoch-one"},
        mode="ops",
    )

    assert rc == 1
    assert result["status"] == "error"
    assert result["errors"][0]["code"] == "audit_log_error"
    assert "confirmation_token" not in result.get("result", {})
    handler.assert_not_called()
    import os

    token_store = Path(os.environ["GOODQ_MINI_AGENT_HOME"]) / "confirmation_tokens.json"
    if token_store.exists():
        assert json.loads(token_store.read_text(encoding="utf-8")) == {}


def test_execution_audit_failure_preserves_observed_side_effects(monkeypatch):
    client = _client()
    args = {"input_dir": "incoming", "epoch": "epoch-one"}
    handler = MagicMock(return_value={"status": "staged_complete", "count": 1})
    client._execute_run_ingestion = handler
    confirmation, confirmation_rc = client.validate_action(
        prompt="Request ingestion",
        mode="ops",
        tool_name="run_ingestion",
        tool_args=args,
    )
    assert confirmation_rc == 3

    original_append = client._append_tool_audit

    def fail_execution_row(row):
        if row["event_type"] == "execution":
            raise OSError("audit completion unavailable")
        original_append(row)

    monkeypatch.setattr(client, "_append_tool_audit", fail_execution_row)
    result, rc = client.execute_tool(
        tool_name="run_ingestion",
        tool_args=args,
        mode="ops",
        confirm=True,
        confirmation_token=confirmation["result"]["confirmation_token"],
    )

    assert rc == 1
    assert result["status"] == "error"
    assert result["errors"][0]["code"] == "audit_log_error"
    assert result["errors"][0]["details"]["side_effects_may_have_occurred"] is True
    assert result["side_effect_report"]["mutated"] is True
    assert result["output"] == {"status": "staged_complete", "count": 1}
    handler.assert_called_once_with(args)


def test_multiple_decisions_append_without_overwriting():
    client = _client()

    for epoch in ("epoch-one", "epoch-two"):
        envelope, rc = client.validate_action(
            prompt="Request ingestion",
            mode="ops",
            tool_name="run_ingestion",
            tool_args={"input_dir": "incoming", "epoch": epoch},
        )
        assert rc == 3
        assert envelope["status"] == "needs_confirmation"

    rows = _rows()
    assert len(rows) == 2
    assert [row["arguments"]["epoch"] for row in rows] == [
        "epoch-one",
        "epoch-two",
    ]


def test_authorization_claim_race_audits_final_rejection(monkeypatch):
    client = _client()
    scope = {"request_id": "request-one", "file_sha256": "a" * 64}
    requested, requested_rc = client.authorize_action(
        prompt="Prepare exact staged request",
        mode="ops",
        tool_name="stage_ingest_request",
        tool_args=scope,
    )
    assert requested_rc == 3
    monkeypatch.setattr(
        client,
        "_claim_confirmation_token",
        MagicMock(return_value=(False, None)),
    )

    result, rc = client.authorize_action(
        prompt="Confirm exact staged request",
        mode="ops",
        tool_name="stage_ingest_request",
        tool_args=scope,
        confirm=True,
        confirmation_token=requested["result"]["confirmation_token"],
    )

    assert rc == 1
    assert result["errors"][0]["code"] == "invalid_confirmation_token"
    rows = _rows()
    assert rows[-1]["status"] == "error"
    assert rows[-1]["return_code"] == 1
    assert rows[-1]["error_codes"] == ["invalid_confirmation_token"]


def test_blocked_handler_outcome_is_not_audited_as_mutation():
    client = _client()
    args = {"video_hash": "video-one", "epoch_id": "epoch-one"}
    client._execute_promote_ucf_to_memory = MagicMock(
        return_value={
            "status": "blocked",
            "reason": "promotion_blocked_unvalidated_frames",
            "staged_count": 1,
        }
    )
    confirmation, confirmation_rc = client.validate_action(
        prompt="Request promotion",
        mode="ops",
        tool_name="promote_ucf_to_memory",
        tool_args=args,
    )
    assert confirmation_rc == 3

    result, rc = client.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args=args,
        mode="ops",
        confirm=True,
        confirmation_token=confirmation["result"]["confirmation_token"],
    )

    assert rc == 0
    assert result["output"]["status"] == "blocked"
    assert result["side_effect_report"]["mutated"] is False
    execution = _rows()[-1]
    assert execution["event_type"] == "execution"
    assert execution["status"] == "blocked"
    assert execution["handler_status"] == "blocked"
    assert execution["handler_reason"] == "promotion_blocked_unvalidated_frames"
    assert execution["side_effect_report"]["mutated"] is False


def test_handler_declared_error_returns_error_envelope_and_truthful_audit():
    client = _client()
    args = {
        "collection": "goodq_text",
        "query_vector": [0.1] * 384,
        "top_k": 5,
        "ucf_status_filter": "staged",
    }

    result, rc = client.execute_tool(
        tool_name="qdrant_query",
        tool_args=args,
        mode="research",
    )

    assert rc == 1
    assert result["status"] == "error"
    assert result["errors"] == [
        {
            "code": "invalid_ucf_status_filter",
            "message": "Tool handler reported an error.",
        }
    ]
    assert result["output"]["status"] == "error"
    assert result["side_effect_report"]["mutated"] is False
    execution = _rows()[-1]
    assert execution["event_type"] == "execution"
    assert execution["status"] == "error"
    assert execution["return_code"] == 1
    assert execution["error_codes"] == ["invalid_ucf_status_filter"]
    assert execution["handler_status"] == "error"
    assert execution["handler_reason"] == "invalid_ucf_status_filter"
    assert execution["side_effect_report"]["mutated"] is False


def test_handler_declared_error_without_reason_uses_generic_error_code():
    client = _client()
    client._execute_qdrant_query = MagicMock(return_value={"status": "error"})

    result, rc = client.execute_tool(
        tool_name="qdrant_query",
        tool_args={"collection": "goodq_text", "query_vector": [0.1]},
    )

    assert rc == 1
    assert result["status"] == "error"
    assert result["errors"][0]["code"] == "handler_reported_error"
    execution = _rows()[-1]
    assert execution["status"] == "error"
    assert execution["return_code"] == 1
    assert execution["error_codes"] == ["handler_reported_error"]
    assert execution["handler_reason"] is None
