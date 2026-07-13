import pytest
import os
import json
from unittest.mock import MagicMock, patch
from pathlib import Path
from agents.mini_agent_client import MiniAgentClient
import goodq_mini_agent.paths


def _promotion_contract():
    return _tool_contract("promote_ucf_to_memory")


def _tool_contract(tool_name):
    contract_path = (
        Path(__file__).resolve().parents[2]
        / "agents"
        / "stack"
        / "contracts"
        / "goodq-o2-local.contract.json"
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    return next(tool for tool in contract["tools"] if tool["name"] == tool_name)


def _allow_verified_promotion_delivery(client, monkeypatch):
    """Keep non-Qdrant promotion tests isolated from validator/report and delivery I/O."""
    monkeypatch.setattr(
        client,
        "_execute_validate_ucf_epoch",
        lambda _args: {"success": True, "errors": []},
    )
    monkeypatch.setattr(
        client,
        "_sync_qdrant_by_scope",
        lambda **_kwargs: {
            "status": "ok",
            "points_verified": 1,
            "failed_collections": [],
        },
    )


def test_validate_ucf_epoch_uses_configured_report_directory(tmp_path, monkeypatch):
    import scripts.ucf.validate_ucf_epoch

    captured = {}

    def fake_run_validation(*, mode, report_dir):
        captured["mode"] = mode
        captured["report_dir"] = report_dir
        return 0

    monkeypatch.setattr(
        scripts.ucf.validate_ucf_epoch,
        "run_validation",
        fake_run_validation,
    )
    expected_report_dir = tmp_path / "validator-reports"
    client = MiniAgentClient(
        profile="safe",
        config={"paths": {"reports_dir": str(expected_report_dir)}},
    )

    result = client._execute_validate_ucf_epoch({})

    assert result == {"success": True, "errors": []}
    assert captured == {
        "mode": "offline",
        "report_dir": expected_report_dir,
    }


def test_validate_ucf_epoch_reads_failure_from_same_report_directory(tmp_path, monkeypatch):
    import scripts.ucf.validate_ucf_epoch

    expected_report_dir = tmp_path / "validator-reports"

    def fake_run_validation(*, mode, report_dir):
        assert mode == "offline"
        assert report_dir == expected_report_dir
        report_dir.mkdir(parents=True)
        (report_dir / "ucf_validation_report.json").write_text(
            json.dumps({"vector_integrity": {"errors": ["isolated validator failure"]}}),
            encoding="utf-8",
        )
        return 1

    monkeypatch.setattr(
        scripts.ucf.validate_ucf_epoch,
        "run_validation",
        fake_run_validation,
    )
    client = MiniAgentClient(
        profile="safe",
        config={"paths": {"reports_dir": str(expected_report_dir)}},
    )

    result = client._execute_validate_ucf_epoch({})

    assert result == {
        "success": False,
        "errors": ["isolated validator failure"],
    }


def test_validate_ucf_epoch_rejects_stale_failure_report(tmp_path, monkeypatch):
    import scripts.ucf.validate_ucf_epoch

    report_dir = tmp_path / "validator-reports"
    report_dir.mkdir(parents=True)
    (report_dir / "ucf_validation_report.json").write_text(
        json.dumps({"vector_integrity": {"errors": ["stale operator error"]}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        scripts.ucf.validate_ucf_epoch,
        "run_validation",
        lambda **_kwargs: 1,
    )
    client = MiniAgentClient(
        profile="safe",
        config={"paths": {"reports_dir": str(report_dir)}},
    )

    result = client._execute_validate_ucf_epoch({})

    assert result == {
        "success": False,
        "errors": ["Validator script returned non-zero exit code."],
    }


def test_promote_ucf_contract_declares_explicit_scope_and_actual_results():
    tool = _promotion_contract()
    input_schema = tool["input_schema"]

    assert input_schema["required"] == ["video_hash", "epoch_id"]
    assert input_schema["additionalProperties"] is False
    assert input_schema["properties"] == {
        "video_hash": {"type": "string", "minLength": 1},
        "epoch_id": {"type": "string", "minLength": 1},
    }

    output_schema = tool["output_schema"]
    assert output_schema["additionalProperties"] is False
    assert {variant["properties"]["status"]["const"] for variant in output_schema["oneOf"]} == {
        "blocked",
        "promoted_complete",
        "promotion_committed_sync_pending",
    }


def test_reconcile_ucf_qdrant_contract_is_exact_scope_and_human_gated():
    tool = _tool_contract("reconcile_ucf_qdrant")

    assert tool["input_schema"]["required"] == ["video_hash", "epoch_id"]
    assert tool["input_schema"]["additionalProperties"] is False
    assert tool["requires_confirmation"] is True
    assert tool["mutability_class"] == "mutate_canonical"


def test_reconcile_confirmation_token_is_bound_to_exact_pending_scope():
    client = MiniAgentClient(profile="safe")
    requested_scope = {"video_hash": "vh_test_001", "epoch_id": "epoch_one"}

    envelope, rc = client.validate_action(
        prompt="Reconcile pending Qdrant projection",
        tool_name="reconcile_ucf_qdrant",
        tool_args=requested_scope,
    )
    assert rc == 3

    result, confirm_rc = client.validate_action(
        prompt="Reconcile pending Qdrant projection",
        tool_name="reconcile_ucf_qdrant",
        tool_args={"video_hash": "vh_test_002", "epoch_id": "epoch_one"},
        confirm=True,
        confirmation_token=envelope["result"]["confirmation_token"],
    )

    assert confirm_rc == 1
    assert result["errors"][0]["code"] == "token_scope_mismatch"


@pytest.mark.parametrize(
    "tool_args",
    [
        {},
        {"video_hash": "vh_test_001"},
        {"epoch_id": "epoch_test"},
        {"video_hash": "vh_test_001", "epoch_id": "epoch_test", "epoch": "legacy"},
        {"video_id": "vh_test_001", "epoch_id": "epoch_test"},
        {"video_hash": "vh_test_001", "epoch_id": "epoch_test", "vectors": []},
        {"video_hash": "", "epoch_id": "epoch_test"},
        {"video_hash": "vh_test_001", "epoch_id": "   "},
    ],
)
def test_promote_ucf_rejects_missing_extra_ambiguous_or_blank_scope(tool_args):
    client = MiniAgentClient(profile="safe")

    envelope, rc = client.validate_action(
        prompt="Promote scoped UCF evidence",
        tool_name="promote_ucf_to_memory",
        tool_args=tool_args,
    )

    assert rc == 1
    assert envelope["status"] == "error"
    assert envelope["errors"][0]["code"] == "invalid_tool_arguments"


def test_promote_ucf_confirmation_token_is_bound_to_exact_scope():
    client = MiniAgentClient(profile="safe")
    requested_scope = {"video_hash": "vh_test_001", "epoch_id": "epoch_one"}

    envelope, rc = client.validate_action(
        prompt="Promote scoped UCF evidence",
        tool_name="promote_ucf_to_memory",
        tool_args=requested_scope,
    )
    assert rc == 3

    result, confirm_rc = client.validate_action(
        prompt="Promote scoped UCF evidence",
        tool_name="promote_ucf_to_memory",
        tool_args={"video_hash": "vh_test_001", "epoch_id": "epoch_two"},
        confirm=True,
        confirmation_token=envelope["result"]["confirmation_token"],
    )

    assert confirm_rc == 1
    assert result["status"] == "error"
    assert result["errors"][0]["code"] == "token_scope_mismatch"


def test_confirmation_token_store_failure_blocks_execution(tmp_path, monkeypatch):
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(tmp_path / "agent-home"))
    scope = {"video_hash": "vh_test_001", "epoch_id": "epoch_one"}
    client = MiniAgentClient(
        profile="safe",
        config={"agent": {"execution_mode": "in_process"}},
    )
    envelope, rc = client.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args=scope,
    )
    assert rc == 3
    token = envelope["result"]["confirmation_token"]
    handler = MagicMock(return_value={"status": "promoted_complete", "promoted_count": 1})
    monkeypatch.setattr(client, "_execute_promote_ucf_to_memory", handler)

    def fail_save(*_args, **_kwargs):
        raise OSError("simulated token-store write failure")

    monkeypatch.setattr(json, "dump", fail_save)
    result, confirm_rc = client.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args=scope,
        confirm=True,
        confirmation_token=token,
    )

    assert confirm_rc == 1
    assert result["status"] == "error"
    assert result["errors"][0]["code"] == "confirmation_token_store_error"
    handler.assert_not_called()


def test_confirmation_token_store_failure_preserves_last_valid_store(tmp_path, monkeypatch):
    agent_home = tmp_path / "agent-home"
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(agent_home))
    agent_home.mkdir(parents=True)
    token_store = agent_home / "confirmation_tokens.json"
    original = '{"existing":{"used":false}}\n'
    token_store.write_text(original, encoding="utf-8")
    client = MiniAgentClient(
        profile="safe",
        config={"agent": {"execution_mode": "in_process"}},
    )

    def fail_save(*_args, **_kwargs):
        raise OSError("simulated token-store write failure")

    monkeypatch.setattr(json, "dump", fail_save)

    with pytest.raises(OSError, match="simulated token-store write failure"):
        client._save_tokens({"replacement": {"used": True}})

    assert token_store.read_text(encoding="utf-8") == original
    assert list(agent_home.glob("confirmation_tokens.json.tmp-*")) == []


EXPECTED_LOCAL_CONFIRMATION_REQUIRED_TOOLS = {
    "create_summary_collection",
    "delete_summary_collection",
    "generate_video_summary",
    "generate_temporal_summary",
    "stage_ingest_request",
    "run_ingestion",
    "file_delete",
    "promote_ucf_to_memory",
    "reconcile_ucf_qdrant",
    "validate_ucf_frames",
    "reject_ucf_frames",
    "supersede_ucf_frames",
}

EXPECTED_LOCAL_AUTHORIZATION_ONLY_ACTIONS = {
    "create_summary_collection",
    "delete_summary_collection",
    "generate_video_summary",
    "generate_temporal_summary",
    "stage_ingest_request",
}


def test_local_confirmation_required_tools_have_one_module_level_authority():
    import agents.mini_agent_client as mini_agent_client

    assert getattr(mini_agent_client, "LOCAL_CONFIRMATION_REQUIRED_TOOLS", None) == (
        EXPECTED_LOCAL_CONFIRMATION_REQUIRED_TOOLS
    )
    assert getattr(mini_agent_client, "LOCAL_AUTHORIZATION_ONLY_ACTIONS", None) == (
        EXPECTED_LOCAL_AUTHORIZATION_ONLY_ACTIONS
    )
    assert "generate_video_summary" in mini_agent_client.MUTATING_DENY_ON_AGENT_FAILURE
    assert "generate_temporal_summary" in mini_agent_client.MUTATING_DENY_ON_AGENT_FAILURE
    assert (
        "generate_video_summary"
        in mini_agent_client.LOCAL_NATIVE_VALIDATION_BYPASS_TOOLS
    )
    assert (
        "generate_temporal_summary"
        in mini_agent_client.LOCAL_NATIVE_VALIDATION_BYPASS_TOOLS
    )


def _temporal_summary_scope(**overrides):
    scope = {
        "job_id": "job_" + "a" * 32,
        "epoch_id": "epoch_2026_07_family",
        "request_sha256": "b" * 64,
        "execution_policy_sha256": "c" * 64,
    }
    scope.update(overrides)
    return scope


def test_generate_temporal_summary_accepts_only_exact_digest_scope(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(tmp_path / "temporal-exact"))
    client = MiniAgentClient(profile="safe")
    client.agent_available = True

    envelope, rc = client.authorize_action(
        prompt="Prepare one exact temporal summary",
        mode="ops",
        tool_name="generate_temporal_summary",
        tool_args=_temporal_summary_scope(),
    )

    assert rc == 3
    assert envelope["status"] == "needs_confirmation"
    assert envelope["result"]["confirmation_token"]


@pytest.mark.parametrize(
    "tool_args",
    [
        [],
        {},
        _temporal_summary_scope(job_id="job_short"),
        _temporal_summary_scope(epoch_id="../private"),
        _temporal_summary_scope(request_sha256="B" * 64),
        _temporal_summary_scope(execution_policy_sha256="short"),
        _temporal_summary_scope(query={"entities": ["private"]}),
        _temporal_summary_scope(confirmation_token="must-not-persist"),
    ],
)
def test_generate_temporal_summary_rejects_invalid_scope_before_token_issue(
    tool_args,
    tmp_path,
    monkeypatch,
):
    agent_home = tmp_path / "temporal-invalid"
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(agent_home))
    client = MiniAgentClient(profile="safe")
    client.agent_available = True

    envelope, rc = client.authorize_action(
        prompt="Reject an invalid temporal summary scope",
        mode="ops",
        tool_name="generate_temporal_summary",
        tool_args=tool_args,
    )

    assert rc == 1
    assert envelope["errors"][0]["code"] == "invalid_tool_arguments"
    assert not (agent_home / "confirmation_tokens.json").exists()


def test_generate_temporal_summary_token_is_scope_bound_and_single_use(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(tmp_path / "temporal-token"))
    client = MiniAgentClient(profile="safe")
    client.agent_available = True
    scope = _temporal_summary_scope()
    prepared, prepared_rc = client.authorize_action(
        prompt="Prepare temporal summary authority",
        mode="ops",
        tool_name="generate_temporal_summary",
        tool_args=scope,
    )
    assert prepared_rc == 3
    token = prepared["result"]["confirmation_token"]

    mismatch, mismatch_rc = client.authorize_action(
        prompt="Reject changed temporal policy",
        mode="ops",
        tool_name="generate_temporal_summary",
        tool_args={**scope, "execution_policy_sha256": "d" * 64},
        confirm=True,
        confirmation_token=token,
    )
    assert mismatch_rc == 1
    assert mismatch["errors"][0]["code"] == "token_scope_mismatch"

    claimed, claimed_rc = client.authorize_action(
        prompt="Claim exact temporal summary authority",
        mode="ops",
        tool_name="generate_temporal_summary",
        tool_args=scope,
        confirm=True,
        confirmation_token=token,
    )
    assert claimed_rc == 0
    assert claimed["status"] == "ok"

    reused, reused_rc = client.authorize_action(
        prompt="Reject reused temporal summary authority",
        mode="ops",
        tool_name="generate_temporal_summary",
        tool_args=scope,
        confirm=True,
        confirmation_token=token,
    )
    assert reused_rc == 1
    assert reused["errors"][0]["code"] == "token_already_used"


def test_generate_video_summary_accepts_only_exact_nonempty_job_video_scope(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(tmp_path / "exact-scope"))
    client = MiniAgentClient(profile="safe")
    client.agent_available = True

    envelope, rc = client.authorize_action(
        prompt="Prepare one exact video summary",
        mode="ops",
        tool_name="generate_video_summary",
        tool_args={"job_id": "job-one", "video_hash": "video-one"},
    )

    assert rc == 3
    assert envelope["status"] == "needs_confirmation"
    assert envelope["result"]["confirmation_token"]


@pytest.mark.parametrize(
    "tool_args",
    [
        ["job-one", "video-one"],
        {},
        {"job_id": "job-one"},
        {"video_hash": "video-one"},
        {"job_id": "job-one", "video_hash": "video-one", "extra": True},
        {"job_id": "", "video_hash": "video-one"},
        {"job_id": "job-one", "video_hash": "   "},
        {"job_id": 1, "video_hash": "video-one"},
        {"job_id": "job-one", "video_hash": None},
    ],
)
def test_generate_video_summary_rejects_invalid_scope_before_token_issuance(
    tool_args,
    tmp_path,
    monkeypatch,
):
    agent_home = tmp_path / "invalid-scope"
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(agent_home))
    client = MiniAgentClient(profile="safe")
    client.agent_available = True

    envelope, rc = client.authorize_action(
        prompt="Prepare invalid video summary scope",
        mode="ops",
        tool_name="generate_video_summary",
        tool_args=tool_args,
    )

    assert rc == 1
    assert envelope["errors"][0]["code"] == "invalid_tool_arguments"
    assert not (agent_home / "confirmation_tokens.json").exists()


def test_generate_video_summary_rejects_invalid_scope_before_token_claim(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(tmp_path / "claim-scope"))
    client = MiniAgentClient(profile="safe")
    client.agent_available = True
    scope = {"job_id": "job-one", "video_hash": "video-one"}
    requested, requested_rc = client.authorize_action(
        prompt="Prepare one exact video summary",
        mode="ops",
        tool_name="generate_video_summary",
        tool_args=scope,
    )
    assert requested_rc == 3
    claim = MagicMock(side_effect=AssertionError("invalid scope reached claim"))
    monkeypatch.setattr(client, "_claim_confirmation_token", claim)

    envelope, rc = client.authorize_action(
        prompt="Claim changed video summary scope",
        mode="ops",
        tool_name="generate_video_summary",
        tool_args={**scope, "extra": True},
        confirm=True,
        confirmation_token=requested["result"]["confirmation_token"],
    )

    assert rc == 1
    assert envelope["errors"][0]["code"] == "invalid_tool_arguments"
    claim.assert_not_called()


def test_generate_video_summary_preserves_mismatch_expiry_and_single_use(
    tmp_path,
    monkeypatch,
):
    agent_home = tmp_path / "token-lifecycle"
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(agent_home))
    client = MiniAgentClient(profile="safe")
    client.agent_available = True
    scope = {"job_id": "job-one", "video_hash": "video-one"}
    requested, requested_rc = client.authorize_action(
        prompt="Prepare one video summary",
        mode="ops",
        tool_name="generate_video_summary",
        tool_args=scope,
    )
    assert requested_rc == 3
    token = requested["result"]["confirmation_token"]

    mismatch, mismatch_rc = client.authorize_action(
        prompt="Claim changed video summary",
        mode="ops",
        tool_name="generate_video_summary",
        tool_args={"job_id": "job-two", "video_hash": "video-one"},
        confirm=True,
        confirmation_token=token,
    )
    assert mismatch_rc == 1
    assert mismatch["errors"][0]["code"] == "token_scope_mismatch"

    token_store = agent_home / "confirmation_tokens.json"
    tokens = json.loads(token_store.read_text(encoding="utf-8"))
    tokens[token]["timestamp"] = "2020-01-01T00:00:00"
    token_store.write_text(json.dumps(tokens), encoding="utf-8")
    expired, expired_rc = client.authorize_action(
        prompt="Claim expired video summary",
        mode="ops",
        tool_name="generate_video_summary",
        tool_args=scope,
        confirm=True,
        confirmation_token=token,
    )
    assert expired_rc == 1
    assert expired["errors"][0]["code"] == "token_expired"

    fresh, fresh_rc = client.authorize_action(
        prompt="Prepare a fresh video summary",
        mode="ops",
        tool_name="generate_video_summary",
        tool_args=scope,
    )
    assert fresh_rc == 3
    fresh_token = fresh["result"]["confirmation_token"]
    claimed, claimed_rc = client.authorize_action(
        prompt="Claim exact video summary",
        mode="ops",
        tool_name="generate_video_summary",
        tool_args=scope,
        confirm=True,
        confirmation_token=fresh_token,
    )
    assert claimed_rc == 0
    assert claimed["status"] == "ok"

    reused, reused_rc = client.authorize_action(
        prompt="Reuse video summary authority",
        mode="ops",
        tool_name="generate_video_summary",
        tool_args=scope,
        confirm=True,
        confirmation_token=fresh_token,
    )
    assert reused_rc == 1
    assert reused["errors"][0]["code"] == "token_already_used"


def test_generate_video_summary_claim_is_atomic_across_clients(
    tmp_path,
    monkeypatch,
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(tmp_path / "atomic-claim"))
    first = MiniAgentClient(profile="safe")
    second = MiniAgentClient(profile="safe")
    first.agent_available = True
    second.agent_available = True
    scope = {"job_id": "job-one", "video_hash": "video-one"}
    requested, requested_rc = first.authorize_action(
        prompt="Prepare atomic video summary",
        mode="ops",
        tool_name="generate_video_summary",
        tool_args=scope,
    )
    assert requested_rc == 3
    token = requested["result"]["confirmation_token"]
    barrier = Barrier(2)

    def claim(client):
        barrier.wait()
        return client.authorize_action(
            prompt="Claim atomic video summary",
            mode="ops",
            tool_name="generate_video_summary",
            tool_args=scope,
            confirm=True,
            confirmation_token=token,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(claim, (first, second)))

    assert sorted(rc for _envelope, rc in results) == [0, 1]
    rejected = next(envelope for envelope, rc in results if rc == 1)
    assert rejected["errors"][0]["code"] == "token_already_used"


def test_generate_video_summary_is_denied_offline_without_issuing_token(
    tmp_path,
    monkeypatch,
):
    agent_home = tmp_path / "offline"
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(agent_home))
    client = MiniAgentClient(profile="offline")
    client.agent_available = True

    envelope, rc = client.authorize_action(
        prompt="Prepare offline video summary",
        mode="ops",
        tool_name="generate_video_summary",
        tool_args={"job_id": "job-one", "video_hash": "video-one"},
    )

    assert rc == 1
    assert envelope["errors"][0]["code"] == "offline_blocked"
    assert not (agent_home / "confirmation_tokens.json").exists()


@pytest.mark.parametrize("profile", ["safe", "unrestricted"])
def test_run_ingestion_requires_exact_local_confirmation(
    profile,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(tmp_path / profile))
    client = MiniAgentClient(
        profile=profile,
        config={"agent": {"execution_mode": "in_process"}},
    )
    handler = MagicMock(return_value={"status": "staged_complete", "epoch": "epoch-one"})
    monkeypatch.setattr(client, "_execute_run_ingestion", handler)
    requested_args = {"input_dir": "incoming-one", "epoch": "epoch-one"}

    envelope, rc = client.execute_tool(
        tool_name="run_ingestion",
        tool_args=requested_args,
    )

    assert rc == 3
    assert envelope["status"] == "needs_confirmation"
    handler.assert_not_called()
    token = envelope["result"]["confirmation_token"]

    mismatch, mismatch_rc = client.execute_tool(
        tool_name="run_ingestion",
        tool_args={"input_dir": "incoming-two", "epoch": "epoch-one"},
        confirm=True,
        confirmation_token=token,
    )
    assert mismatch_rc == 1
    assert mismatch["errors"][0]["code"] == "token_scope_mismatch"
    handler.assert_not_called()

    result, confirm_rc = client.execute_tool(
        tool_name="run_ingestion",
        tool_args=requested_args,
        confirm=True,
        confirmation_token=token,
    )
    assert confirm_rc == 0
    assert result["status"] == "success"
    handler.assert_called_once_with(requested_args)


def test_authorize_action_claims_exact_scope_once_without_executing_handler(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(tmp_path / "authorize"))
    client = MiniAgentClient(
        profile="safe",
        config={"agent": {"execution_mode": "in_process"}},
    )
    handler = MagicMock(return_value={"status": "should-not-run"})
    monkeypatch.setattr(client, "_execute_run_ingestion", handler)
    scope = {
        "request_id": "ingest-request-one",
        "source_kind": "upload",
        "original_name": "family.mp4",
        "file_size": 12,
        "file_hash": "a" * 64,
        "policy_profile": "local_ingest_facade_v1",
    }

    requested, requested_rc = client.authorize_action(
        prompt="Authorize one exact staged ingestion request",
        mode="ops",
        tool_name="stage_ingest_request",
        tool_args=scope,
    )
    assert requested_rc == 3
    assert requested["status"] == "needs_confirmation"
    token = requested["result"]["confirmation_token"]

    authorized, authorized_rc = client.authorize_action(
        prompt="Confirm one exact staged ingestion request",
        mode="ops",
        tool_name="stage_ingest_request",
        tool_args=scope,
        confirm=True,
        confirmation_token=token,
    )
    assert authorized_rc == 0
    assert authorized["status"] == "ok"
    handler.assert_not_called()

    changed_after_use, changed_after_use_rc = client.authorize_action(
        prompt="Attempt used authorization against changed scope",
        mode="ops",
        tool_name="stage_ingest_request",
        tool_args={**scope, "request_id": "ingest-request-two"},
        confirm=True,
        confirmation_token=token,
    )
    assert changed_after_use_rc == 1
    assert changed_after_use["errors"][0]["code"] == "token_scope_mismatch"

    reused, reused_rc = client.authorize_action(
        prompt="Attempt confirmation token reuse",
        mode="ops",
        tool_name="stage_ingest_request",
        tool_args=scope,
        confirm=True,
        confirmation_token=token,
    )
    assert reused_rc == 1
    assert reused["errors"][0]["code"] == "token_already_used"
    handler.assert_not_called()


def test_authorize_action_scope_mismatch_does_not_consume_token(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(tmp_path / "scope"))
    client = MiniAgentClient(
        profile="safe",
        config={"agent": {"execution_mode": "in_process"}},
    )
    scope = {"request_id": "request-one", "file_hash": "a" * 64}
    requested, requested_rc = client.authorize_action(
        prompt="Request exact ingestion authorization",
        mode="ops",
        tool_name="stage_ingest_request",
        tool_args=scope,
    )
    assert requested_rc == 3
    token = requested["result"]["confirmation_token"]

    mismatch, mismatch_rc = client.authorize_action(
        prompt="Attempt changed ingestion scope",
        mode="ops",
        tool_name="stage_ingest_request",
        tool_args={"request_id": "request-two", "file_hash": "a" * 64},
        confirm=True,
        confirmation_token=token,
    )
    assert mismatch_rc == 1
    assert mismatch["errors"][0]["code"] == "token_scope_mismatch"

    authorized, authorized_rc = client.authorize_action(
        prompt="Confirm original ingestion scope",
        mode="ops",
        tool_name="stage_ingest_request",
        tool_args=scope,
        confirm=True,
        confirmation_token=token,
    )
    assert authorized_rc == 0
    assert authorized["status"] == "ok"


def test_authorize_action_fails_closed_when_token_disappears_before_claim(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(tmp_path / "claim-race"))
    client = MiniAgentClient(
        profile="safe",
        config={"agent": {"execution_mode": "in_process"}},
    )
    scope = {"request_id": "request-one", "file_hash": "a" * 64}
    requested, requested_rc = client.authorize_action(
        prompt="Request exact ingestion authorization",
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
        prompt="Confirm exact ingestion authorization",
        mode="ops",
        tool_name="stage_ingest_request",
        tool_args=scope,
        confirm=True,
        confirmation_token=requested["result"]["confirmation_token"],
    )

    assert rc == 1
    assert result["errors"][0]["code"] == "invalid_confirmation_token"


def test_authorize_action_rejects_native_execution_tools_without_claiming(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(tmp_path / "native-reject"))
    client = MiniAgentClient(
        profile="safe",
        config={"agent": {"execution_mode": "in_process"}},
    )

    result, rc = client.authorize_action(
        prompt="Attempt standalone native authorization",
        mode="ops",
        tool_name="run_ingestion",
        tool_args={"ucf_records": []},
    )

    assert rc == 1
    assert result["errors"][0]["code"] == "authorization_only_action_required"
    token_store = Path(tmp_path / "native-reject" / "confirmation_tokens.json")
    assert not token_store.exists()


def test_revoke_action_authorization_requires_exact_scope_and_removes_token(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(tmp_path / "revoke"))
    client = MiniAgentClient(
        profile="safe",
        config={"agent": {"execution_mode": "in_process"}},
    )
    scope = {"request_id": "request-one", "file_sha256": "a" * 64}
    requested, requested_rc = client.authorize_action(
        prompt="Prepare exact staged ingestion request",
        mode="ops",
        tool_name="stage_ingest_request",
        tool_args=scope,
    )
    assert requested_rc == 3
    token = requested["result"]["confirmation_token"]

    mismatch, mismatch_rc = client.revoke_action_authorization(
        prompt="Cancel changed staged ingestion request",
        mode="ops",
        tool_name="stage_ingest_request",
        tool_args={"request_id": "request-two", "file_sha256": "a" * 64},
        confirmation_token=token,
    )
    assert mismatch_rc == 1
    assert mismatch["errors"][0]["code"] == "token_scope_mismatch"

    revoked, revoked_rc = client.revoke_action_authorization(
        prompt="Cancel exact staged ingestion request",
        mode="ops",
        tool_name="stage_ingest_request",
        tool_args=scope,
        confirmation_token=token,
    )
    assert revoked_rc == 0
    assert revoked["status"] == "ok"

    reused, reused_rc = client.authorize_action(
        prompt="Attempt revoked staged ingestion request",
        mode="ops",
        tool_name="stage_ingest_request",
        tool_args=scope,
        confirm=True,
        confirmation_token=token,
    )
    assert reused_rc == 1
    assert reused["errors"][0]["code"] == "invalid_confirmation_token"


def test_execute_tool_delegates_to_authorize_action_once(monkeypatch):
    client = MiniAgentClient(
        profile="safe",
        config={"agent": {"execution_mode": "in_process"}},
    )
    authorized = {
        "request_id": "task-authorized",
        "profile": "safe",
        "status": "ok",
        "timestamp": "2026-07-11T00:00:00Z",
        "result": {"allowed": True},
        "errors": [],
    }
    authorize = MagicMock(return_value=(authorized, 0))
    claim = MagicMock(side_effect=AssertionError("execute_tool claimed twice"))
    handler = MagicMock(return_value={"status": "staged_complete"})
    monkeypatch.setattr(client, "_authorize_action_impl", authorize)
    monkeypatch.setattr(client, "_claim_confirmation_token", claim)
    monkeypatch.setattr(client, "_execute_run_ingestion", handler)

    result, rc = client.execute_tool(
        tool_name="run_ingestion",
        tool_args={"ucf_records": []},
        mode="ops",
        confirm=True,
        confirmation_token="token-one",
    )

    assert rc == 0
    assert result["status"] == "success"
    authorize.assert_called_once()
    claim.assert_not_called()
    handler.assert_called_once_with({"ucf_records": []})


@pytest.mark.parametrize("profile", ["safe", "unrestricted"])
def test_file_delete_requires_break_glass_and_exact_confirmation(
    profile,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(tmp_path / profile))
    monkeypatch.delenv("GOODQ_BREAK_GLASS", raising=False)
    client = MiniAgentClient(
        profile=profile,
        config={"agent": {"execution_mode": "in_process"}},
    )
    handler = MagicMock(return_value={"deleted": "target-one.txt"})
    monkeypatch.setattr(client, "_execute_file_delete", handler)
    requested_args = {"path": "target-one.txt"}

    blocked, blocked_rc = client.execute_tool(
        tool_name="file_delete",
        tool_args=requested_args,
    )
    assert blocked_rc == 1
    assert blocked["errors"][0]["code"] == "break_glass_required"
    assert "confirmation_token" not in blocked["result"]
    handler.assert_not_called()

    monkeypatch.setenv("GOODQ_BREAK_GLASS", "1")
    envelope, rc = client.execute_tool(
        tool_name="file_delete",
        tool_args=requested_args,
    )
    assert rc == 3
    assert envelope["status"] == "needs_confirmation"
    handler.assert_not_called()
    token = envelope["result"]["confirmation_token"]

    mismatch, mismatch_rc = client.execute_tool(
        tool_name="file_delete",
        tool_args={"path": "target-two.txt"},
        confirm=True,
        confirmation_token=token,
    )
    assert mismatch_rc == 1
    assert mismatch["errors"][0]["code"] == "token_scope_mismatch"
    handler.assert_not_called()

    result, confirm_rc = client.execute_tool(
        tool_name="file_delete",
        tool_args=requested_args,
        confirm=True,
        confirmation_token=token,
    )
    assert confirm_rc == 0
    assert result["status"] == "success"
    handler.assert_called_once_with(requested_args)


@pytest.mark.parametrize(
    ("tool_name", "requested_args", "changed_args"),
    [
        (
            "validate_ucf_frames",
            {"video_hash": "video-one", "epoch_id": "epoch-one"},
            {"video_hash": "video-one", "epoch_id": "epoch-two"},
        ),
        (
            "reject_ucf_frames",
            {"video_hash": "video-one", "epoch_id": "epoch-one", "reason": "bad frame"},
            {"video_hash": "video-one", "epoch_id": "epoch-one", "reason": "different reason"},
        ),
        (
            "supersede_ucf_frames",
            {"video_hash": "video-one", "epoch_id": "epoch-one"},
            {"video_hash": "video-two", "epoch_id": "epoch-one"},
        ),
    ],
)
def test_lifecycle_confirmation_token_rejects_changed_complete_args(
    tool_name,
    requested_args,
    changed_args,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(tmp_path / tool_name))
    client = MiniAgentClient(profile="safe")
    envelope, rc = client.validate_action(
        prompt="Request lifecycle mutation",
        tool_name=tool_name,
        tool_args=requested_args,
    )
    assert rc == 3

    mismatch, mismatch_rc = client.validate_action(
        prompt="Attempt changed lifecycle mutation",
        tool_name=tool_name,
        tool_args=changed_args,
        confirm=True,
        confirmation_token=envelope["result"]["confirmation_token"],
    )

    assert mismatch_rc == 1
    assert mismatch["errors"][0]["code"] == "token_scope_mismatch"


def test_unrestricted_promotion_still_requires_local_confirmation(tmp_path, monkeypatch):
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(tmp_path / "unrestricted"))
    client = MiniAgentClient(profile="unrestricted")
    scope = {"video_hash": "video-one", "epoch_id": "epoch-one"}

    envelope, rc = client.validate_action(
        prompt="Promote exact scope",
        tool_name="promote_ucf_to_memory",
        tool_args=scope,
    )

    assert rc == 3
    assert envelope["status"] == "needs_confirmation"
    assert envelope["result"]["confirmation_token"]


@pytest.mark.parametrize(
    ("tool_name", "tool_args"),
    [
        ("run_ingestion", {"input_dir": "incoming", "epoch": "epoch-one"}),
        ("file_delete", {"path": "target.txt"}),
        ("promote_ucf_to_memory", {"video_hash": "video-one", "epoch_id": "epoch-one"}),
        ("reconcile_ucf_qdrant", {"video_hash": "video-one", "epoch_id": "epoch-one"}),
        ("validate_ucf_frames", {"video_hash": "video-one", "epoch_id": "epoch-one"}),
        (
            "reject_ucf_frames",
            {"video_hash": "video-one", "epoch_id": "epoch-one", "reason": "bad frame"},
        ),
        ("supersede_ucf_frames", {"video_hash": "video-one", "epoch_id": "epoch-one"}),
    ],
)
def test_local_confirmation_rejects_confirm_true_without_token(
    tool_name,
    tool_args,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(tmp_path / tool_name))
    monkeypatch.setenv("GOODQ_BREAK_GLASS", "1")
    client = MiniAgentClient(profile="safe")

    envelope, rc = client.validate_action(
        prompt="Attempt confirmation without token",
        tool_name=tool_name,
        tool_args=tool_args,
        confirm=True,
    )

    assert rc == 1
    assert envelope["errors"][0]["code"] == "invalid_confirmation_token"


def test_confirmation_token_issuance_store_failure_is_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(tmp_path / "issuance-failure"))
    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(
        client,
        "_save_tokens",
        MagicMock(side_effect=OSError("simulated issuance persistence failure")),
    )

    envelope, rc = client.validate_action(
        prompt="Ingest exact scope",
        tool_name="run_ingestion",
        tool_args={"input_dir": "incoming", "epoch": "epoch-one"},
    )

    assert rc == 1
    assert envelope["status"] == "error"
    assert envelope["errors"][0]["code"] == "confirmation_token_store_error"
    assert "confirmation_token" not in envelope["result"]


def test_assets_dir_monkeypatch():
    """Verify that ASSETS_DIR was successfully redirected to our local folder."""
    expected_path = Path(__file__).resolve().parent.parent.parent / "agents" / "stack"
    assert goodq_mini_agent.paths.ASSETS_DIR.resolve() == expected_path.resolve()


def test_fresh_agent_home_bootstraps_packaged_validation_scripts(tmp_path, monkeypatch):
    agent_home = tmp_path / "fresh-agent-home"
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(agent_home))
    client = MiniAgentClient(
        profile="safe",
        config={"agent": {"execution_mode": "in_process"}},
    )

    envelope, rc = client.validate_action(
        prompt="Search memory for scene context",
        mode="research",
        tool_name="qdrant_query",
        tool_args={
            "collection": "goodq_text",
            "query_vector": [0.1] * 384,
            "top_k": 5,
        },
    )

    assert rc == 0, envelope
    assert (agent_home / "scripts" / "validate_contract.py").is_file()


def test_validate_action_approved_tool():
    """Verify that qdrant_query (read-only) passes without blocking."""
    client = MiniAgentClient(profile="safe")
    envelope, rc = client.validate_action(
        prompt="Search memory for scene context",
        mode="research",
        tool_name="qdrant_query",
        tool_args={
            "collection": "goodq_text",
            "query_vector": [0.1] * 384,
            "top_k": 5
        }
    )
    
    assert rc == 0
    assert envelope["status"] == "ok"
    assert not envelope["errors"]

def test_validate_action_requires_confirmation():
    """Verify that home_assistant_call_service triggers a confirmation requirement (rc=3)."""
    client = MiniAgentClient(profile="safe")
    envelope, rc = client.validate_action(
        prompt="Turn off the living room lights",
        mode="ops",
        tool_name="home_assistant_call_service",
        tool_args={
            "domain": "light",
            "service": "turn_off",
            "data": {"entity_id": "light.living_room"}
        }
    )
    
    assert rc == 3 or envelope["status"] == "needs_confirmation"
    assert "mutability_requires_confirmation" in envelope["errors"][0]["code"]
    assert "confirmation_token" in envelope["result"]

def test_validate_action_unapproved_tool():
    """Verify that undeclared tools are strictly rejected by the policy engine."""
    client = MiniAgentClient(profile="safe")
    envelope, rc = client.validate_action(
        prompt="Delete the entire project directory",
        mode="research",
        tool_name="destroy_filesystem",
        tool_args={"path": "/"}
    )
    
    assert rc != 0
    assert envelope["status"] == "error"
    any_contract_err = any(
        "undeclared_tool" in str(reason)
        for err in envelope["errors"]
        for reason in err.get("details", {}).get("block_reasons", [])
    )
    assert any_contract_err

@patch("lib.llm_client.LLMClient")
def test_execute_llm_chat_local(mock_llm_class):
    """Verify that execution of llm_chat_local passes checks and queries LLMClient."""
    mock_instance = MagicMock()
    mock_instance.chat.return_value = {
        "choices": [{"message": {"content": "Hello from unit test LLM!"}}]
    }
    mock_llm_class.return_value = mock_instance

    client = MiniAgentClient(profile="safe")
    # Replace the client's internal llm_client with the mock instance
    client.llm_client = mock_instance

    res, rc = client.execute_tool(
        tool_name="llm_chat_local",
        tool_args={
            "messages": [{"role": "user", "content": "hello"}],
            "temperature": 0.5
        }
    )

    assert rc == 0
    assert res["status"] == "success"
    assert res["output"]["content"] == "Hello from unit test LLM!"
    mock_instance.chat.assert_called_once()

@patch("faiss.read_index")
@patch("os.path.exists")
def test_execute_faiss_search_mocked(mock_exists, mock_read_index):
    """Verify that faiss_search acquires the FaissLock and performs a query."""
    mock_exists.return_value = True
    
    mock_idx = MagicMock()
    # Mock search response: distances D and indices I
    import numpy as np
    mock_idx.search.return_value = (np.array([[0.85]]), np.array([[42]]))
    mock_read_index.return_value = mock_idx

    client = MiniAgentClient(profile="safe")
    res, rc = client.execute_tool(
        tool_name="faiss_search",
        tool_args={
            "index_path": "fake_index.index",
            "query_vector": [0.1] * 384,
            "top_k": 1
        }
    )

    assert rc == 0
    assert res["status"] == "success"
    assert len(res["output"]["matches"]) == 1
    assert res["output"]["matches"][0]["id"] == 42
    assert res["output"]["matches"][0]["score"] == pytest.approx(0.85)

def test_execute_tool_requires_confirmation_flow():
    """Verify the full flow: request blocked -> request confirmed -> execute tool succeeds."""
    client = MiniAgentClient(profile="safe")
    
    # 1. First execution request should be blocked requiring confirmation (rc=3)
    envelope, rc = client.execute_tool(
        tool_name="home_assistant_call_service",
        tool_args={
            "domain": "light",
            "service": "turn_off",
            "data": {"entity_id": "light.living_room"}
        }
    )
    
    assert rc == 3
    assert envelope["status"] == "needs_confirmation"
    token = envelope["result"]["confirmation_token"]
    assert token
    
    # 2. Resubmit with the correct confirmation token and confirm=True
    res, rc_confirm = client.execute_tool(
        tool_name="home_assistant_call_service",
        tool_args={
            "domain": "light",
            "service": "turn_off",
            "data": {"entity_id": "light.living_room"}
        },
        confirm=True,
        confirmation_token=token
    )
    
    assert rc_confirm == 0
    assert res["status"] == "success"
    assert res["output"]["ok"] is True


def test_import_no_goodq_mini_agent():
    """Verify that importing and initializing MiniAgentClient succeeds even when goodq_mini_agent is uninstalled."""
    import sys
    import importlib

    # Mask the package in sys.modules
    sys.modules["goodq_mini_agent"] = None
    sys.modules["goodq_mini_agent.paths"] = None
    sys.modules["goodq_mini_agent.stack_runner"] = None

    import agents.mini_agent_client
    importlib.reload(agents.mini_agent_client)

    try:
        client = agents.mini_agent_client.MiniAgentClient()
        assert client.agent_available is False
        assert client.last_error_type in ("ImportError", "TypeError", "ModuleNotFoundError")
        assert client.last_error_message is not None
    finally:
        # Restore sys.modules and reload to original state
        sys.modules.pop("goodq_mini_agent", None)
        sys.modules.pop("goodq_mini_agent.paths", None)
        sys.modules.pop("goodq_mini_agent.stack_runner", None)
        importlib.invalidate_caches()
        importlib.reload(agents.mini_agent_client)


def test_fallback_policy_deterministic_gating():
    """Verify that fallback policy deterministically allows read-only and denies mutating tools when agent is offline."""
    client = MiniAgentClient(profile="safe")
    client.agent_available = False  # Force offline fallback state

    # 1. Allow read-only action
    envelope, rc = client.validate_action(
        prompt="Search memory for scene context",
        mode="research",
        tool_name="qdrant_query",
        tool_args={"query_vector": [0.1] * 384}
    )
    assert rc == 0
    assert envelope["status"] == "ok"
    assert envelope["result"]["allowed"] is True
    assert envelope["result"]["offline_fallback_active"] is True

    # 2. Deny mutating action
    envelope_mut, rc_mut = client.validate_action(
        prompt="Turn off light",
        mode="ops",
        tool_name="home_assistant_call_service",
        tool_args={"service": "turn_off"}
    )
    assert rc_mut == 1
    assert envelope_mut["status"] == "error"
    assert envelope_mut["result"]["allowed"] is False
    assert envelope_mut["errors"][0]["code"] == "agent_offline_mutation_blocked"


def test_traceback_sanitized_in_envelope():
    """Verify that execution exceptions are logged and not returned in the user-facing envelope."""
    client = MiniAgentClient(profile="safe")
    assert client.agent_available is True

    # Mock stack runner to crash
    with patch.object(client._runner, "run_task", side_effect=RuntimeError("Internal sensitive path L:\\secret crash")):
        envelope, rc = client.validate_action(
            prompt="Turn off light",
            mode="ops",
            tool_name="home_assistant_call_service"
        )

    assert rc == 1
    assert envelope["status"] == "error"
    assert envelope["result"]["allowed"] is False
    # Check that tracebacks/sensitive error text is not leaked
    envelope_str = str(envelope)
    assert "sensitive path" not in envelope_str.lower()
    assert "RuntimeError" not in envelope_str


def test_subprocess_execution_mode():
    """Verify that subprocess execution mode executes actions safely through CLI."""
    client = MiniAgentClient(profile="safe")
    client.execution_mode = "subprocess"

    envelope, rc = client.validate_action(
        prompt="Search memory for scene context",
        mode="research",
        tool_name="qdrant_query",
        tool_args={
            "collection": "goodq_text",
            "query_vector": [0.1] * 384,
            "top_k": 5
        }
    )
    assert rc == 0
    assert envelope["status"] == "ok"
    assert envelope["result"]["stack"]["final"]["allowed"] is True


# ---------------------------------------------------------------------------
# H1 / S1 — staged → validated → promoted lifecycle gate tests
# ---------------------------------------------------------------------------

def _make_ucf_db_with_staged_frame(tmp_path):
    """Helper: create a minimal UCF DB with one staged frame and return its path."""
    import sys
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[2]
    import importlib.util
    ledger_path = repo_root / "scripts" / "ucf" / "ucf_ledger.py"
    spec = importlib.util.spec_from_file_location("ucf_ledger_helper", str(ledger_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    db_path = tmp_path / "ucf_ledger.db"
    client = mod.UCFLedgerClient(str(db_path))
    client.init_schema()
    client.register_media(
        video_hash="vh_test_001",
        file_path="test.mp4",
        duration=10.0,
        fps=30.0,
        width=1920,
        height=1080,
    )
    client.log_frame(
        video_hash="vh_test_001",
        epoch_id="epoch_test",
        run_id="run_test",
        t_start=0.0,
        t_end=1.0,
        modality="video",
        worker_name="image_embed_clip",
        model_tag="openai/clip-vit-large-patch14",
        payload={"label": "test_frame"},
        promotion_status="staged",
    )
    client.close()
    return db_path


def test_promote_ucf_blocked_when_frames_staged(tmp_path, monkeypatch):
    """H1: promote_ucf_to_memory must return 'blocked' when in-scope frames are still staged.

    This verifies that the staged-state pre-check gate prevents promotion of
    unvalidated frames. The only way to unblock is to run validate_ucf_frames first.
    """
    db_path = _make_ucf_db_with_staged_frame(tmp_path)
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))

    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)

    # Obtain confirmation token (promotion is HITL-gated)
    envelope, rc = client.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args={"video_hash": "vh_test_001", "epoch_id": "epoch_test"},
    )
    assert rc == 3
    assert envelope["status"] == "needs_confirmation"
    token = envelope["result"]["confirmation_token"]

    # Confirm — but frames are still staged, so the pre-check must block
    result, rc2 = client.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args={"video_hash": "vh_test_001", "epoch_id": "epoch_test"},
        confirm=True,
        confirmation_token=token,
    )
    assert rc2 == 0  # execution succeeded (no exception)
    assert result["status"] == "success"
    output = result["output"]
    assert output["status"] == "blocked"
    assert output["reason"] == "promotion_blocked_unvalidated_frames"
    assert output["staged_count"] == 1


def test_promote_ucf_succeeds_when_frames_validated(tmp_path, monkeypatch):
    """H1: promote_ucf_to_memory must succeed when all in-scope frames are validated.

    This verifies the corrected SQL path: only 'validated' rows are promoted
    to 'promoted'. Staged rows are neither touched nor allowed through.
    """
    import sqlite3

    db_path = _make_ucf_db_with_staged_frame(tmp_path)
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))

    # Manually advance the frame to 'validated' (simulating validate_ucf_frames)
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE context_frames SET promotion_status = 'validated'")
    conn.commit()
    conn.close()

    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)
    _allow_verified_promotion_delivery(client, monkeypatch)

    # Request confirmation token
    envelope, rc = client.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args={"video_hash": "vh_test_001", "epoch_id": "epoch_test"},
    )
    assert rc == 3
    token = envelope["result"]["confirmation_token"]

    # Confirm — all frames are validated, so promotion must succeed
    result, rc2 = client.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args={"video_hash": "vh_test_001", "epoch_id": "epoch_test"},
        confirm=True,
        confirmation_token=token,
    )
    assert rc2 == 0
    assert result["status"] == "success"
    output = result["output"]
    assert output["status"] == "promoted_complete"
    assert output["promoted_count"] == 1

    # Verify the DB row is now 'promoted'
    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT promotion_status FROM context_frames LIMIT 1").fetchone()
    conn.close()
    assert row[0] == "promoted"


def test_promote_ucf_records_scoped_transition_with_frame_evidence(tmp_path, monkeypatch):
    import sqlite3

    db_path = _make_ucf_db_with_staged_frame(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE context_frames SET promotion_status = 'validated'")
    frame_id = conn.execute("SELECT frame_id FROM context_frames").fetchone()[0]
    conn.commit()
    conn.close()

    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)
    _allow_verified_promotion_delivery(client, monkeypatch)

    result, rc = _confirm_tool(
        client,
        "promote_ucf_to_memory",
        {"video_hash": "vh_test_001", "epoch_id": "epoch_test"},
    )

    assert rc == 0
    assert result["output"]["promoted_count"] == 1
    conn = sqlite3.connect(str(db_path))
    transition = conn.execute(
        "SELECT frame_ids, video_hash, epoch_id, old_status, new_status, "
        "tool_name, scope, evidence FROM ucf_status_transitions"
    ).fetchone()
    conn.close()
    assert transition is not None
    assert json.loads(transition[0]) == [frame_id]
    assert transition[1:6] == (
        "vh_test_001",
        "epoch_test",
        "validated",
        "promoted",
        "promote_ucf_to_memory",
    )
    assert transition[6] == "video_hash=vh_test_001,epoch_id=epoch_test"
    assert json.loads(transition[7]) == {"affected_count": 1}


def test_promote_ucf_audit_failure_rolls_back_without_dematerializing(
    tmp_path, monkeypatch
):
    import sqlite3

    db_path = _make_ucf_db_with_staged_frame(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE context_frames SET promotion_status = 'validated'")
    conn.execute(
        "CREATE TRIGGER force_promotion_transition_failure "
        "BEFORE INSERT ON ucf_status_transitions "
        "BEGIN SELECT RAISE(ABORT, 'forced promotion transition failure'); END"
    )
    conn.commit()
    conn.close()

    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)
    dematerialized = []
    monkeypatch.setattr(
        client,
        "_dematerialize_active_views",
        lambda **kwargs: dematerialized.append(kwargs),
    )
    _allow_verified_promotion_delivery(client, monkeypatch)

    result, rc = _confirm_tool(
        client,
        "promote_ucf_to_memory",
        {"video_hash": "vh_test_001", "epoch_id": "epoch_test"},
    )

    assert rc == 1
    assert result["status"] == "fatal_error"
    conn = sqlite3.connect(str(db_path))
    status = conn.execute("SELECT promotion_status FROM context_frames").fetchone()[0]
    transition_count = conn.execute(
        "SELECT COUNT(*) FROM ucf_status_transitions"
    ).fetchone()[0]
    outbox_table_exists = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master "
        "WHERE type = 'table' AND name = 'ucf_qdrant_sync_outbox'"
    ).fetchone()[0]
    outbox_count = (
        conn.execute("SELECT COUNT(*) FROM ucf_qdrant_sync_outbox").fetchone()[0]
        if outbox_table_exists
        else 0
    )
    conn.close()
    assert status == "validated"
    assert transition_count == 0
    assert outbox_count == 0
    assert dematerialized == []


def test_promote_ucf_staged_gate_and_transition_share_write_lock(
    tmp_path, monkeypatch
):
    import sqlite3
    from types import SimpleNamespace

    import agents.mini_agent_client as mini_agent_module

    db_path = _make_ucf_db_with_staged_frame(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE context_frames SET promotion_status = 'validated'")
    conn.commit()
    conn.close()

    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)
    _allow_verified_promotion_delivery(client, monkeypatch)
    envelope, rc = client.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args={"video_hash": "vh_test_001", "epoch_id": "epoch_test"},
    )
    assert rc == 3

    real_ledger_module = mini_agent_module._load_ucf_ledger()

    class SchemaReadyLedger:
        insert_status_transition = staticmethod(
            real_ledger_module.UCFLedgerClient.insert_status_transition
        )

        def __init__(self, _db_path):
            pass

        def init_schema(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(
        mini_agent_module,
        "_load_ucf_ledger",
        lambda: SimpleNamespace(UCFLedgerClient=SchemaReadyLedger),
    )

    real_connect = sqlite3.connect
    injection_results = []

    class StagedCountCursor:
        def __init__(self, cursor):
            self._cursor = cursor

        def fetchone(self):
            row = self._cursor.fetchone()
            writer = real_connect(str(db_path), timeout=0.05)
            try:
                writer.execute(
                    """
                    INSERT INTO context_frames (
                        video_hash, ucf_schema_version, epoch_id, run_id,
                        t_start, t_end, modality, worker_name, model_tag,
                        payload, payload_hash, promotion_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "vh_test_001",
                        "ucf.v0.1",
                        "epoch_test",
                        "run_race",
                        2.0,
                        3.0,
                        "video",
                        "image_embed_clip",
                        "openai/clip-vit-large-patch14",
                        json.dumps({"label": "racing_staged_frame"}),
                        "racing-staged-frame",
                        "staged",
                    ),
                )
                writer.commit()
                injection_results.append("inserted")
            except sqlite3.OperationalError as exc:
                writer.rollback()
                assert "locked" in str(exc).lower()
                injection_results.append("blocked")
            finally:
                writer.close()
            return row

        def __getattr__(self, name):
            return getattr(self._cursor, name)

    class PromotionConnection:
        def __init__(self, connection):
            self._connection = connection

        def execute(self, query, params=()):
            cursor = self._connection.execute(query, params)
            if (
                "SELECT count(*) FROM context_frames" in query
                and "promotion_status = 'staged'" in query
            ):
                return StagedCountCursor(cursor)
            return cursor

        def __getattr__(self, name):
            return getattr(self._connection, name)

    def connect_with_race_probe(database, *args, **kwargs):
        connection = real_connect(database, *args, **kwargs)
        if Path(database).resolve() == db_path.resolve():
            return PromotionConnection(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", connect_with_race_probe)
    result, confirm_rc = client.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args={"video_hash": "vh_test_001", "epoch_id": "epoch_test"},
        confirm=True,
        confirmation_token=envelope["result"]["confirmation_token"],
    )

    assert confirm_rc == 0
    assert result["output"]["promoted_count"] == 1
    assert injection_results == ["blocked"]
    conn = real_connect(str(db_path))
    staged_count = conn.execute(
        "SELECT COUNT(*) FROM context_frames WHERE promotion_status = 'staged'"
    ).fetchone()[0]
    conn.close()
    assert staged_count == 0


def test_promote_ucf_pre_materialization_failure_rolls_back_status_and_transition(
    tmp_path, monkeypatch
):
    import sqlite3

    db_path = _make_ucf_db_with_staged_frame(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE context_frames SET promotion_status = 'validated'")
    conn.commit()
    conn.close()

    client = MiniAgentClient(config={"paths": {"db_dir": str(tmp_path)}})
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)
    dematerialized = []
    monkeypatch.setattr(
        client,
        "_dematerialize_active_views",
        lambda **kwargs: dematerialized.append(kwargs),
    )
    _allow_verified_promotion_delivery(client, monkeypatch)

    envelope, rc = client.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args={"video_hash": "vh_test_001", "epoch_id": "epoch_test"},
    )
    token = envelope["result"]["confirmation_token"]
    result, confirm_rc = client.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args={"video_hash": "vh_test_001", "epoch_id": "epoch_test"},
        confirm=True,
        confirmation_token=token,
    )

    assert rc == 3
    assert confirm_rc == 1
    assert result["status"] == "fatal_error"
    conn = sqlite3.connect(str(db_path))
    status = conn.execute("SELECT promotion_status FROM context_frames").fetchone()[0]
    transition_count = conn.execute(
        "SELECT COUNT(*) FROM ucf_status_transitions"
    ).fetchone()[0]
    conn.close()
    assert status == "validated"
    assert transition_count == 0
    assert dematerialized == []


def test_promote_ucf_post_write_failure_rolls_back_and_compensates(
    tmp_path, monkeypatch
):
    import sqlite3

    import lib.knowledge_graph as knowledge_graph_module

    db_path = _make_ucf_db_with_staged_frame(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE context_frames SET promotion_status = 'validated'")
    conn.commit()
    conn.close()

    memory_db = tmp_path / "memory.db"
    client = MiniAgentClient(
        config={
            "paths": {
                "db_path": str(memory_db),
                "knowledge_graph_db": str(tmp_path / "knowledge_graph.db"),
                "processing": str(tmp_path / "processing"),
            }
        }
    )
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)
    dematerialized = []
    monkeypatch.setattr(
        client,
        "_dematerialize_active_views",
        lambda **kwargs: dematerialized.append(kwargs),
    )
    _allow_verified_promotion_delivery(client, monkeypatch)

    class FailingKnowledgeGraph:
        def __init__(self, _path):
            raise RuntimeError("forced post-write materialization failure")

    monkeypatch.setattr(
        knowledge_graph_module, "KnowledgeGraph", FailingKnowledgeGraph
    )

    result, rc = _confirm_tool(
        client,
        "promote_ucf_to_memory",
        {"video_hash": "vh_test_001", "epoch_id": "epoch_test"},
    )

    assert rc == 1
    assert result["status"] == "fatal_error"
    assert memory_db.exists()
    conn = sqlite3.connect(str(db_path))
    status = conn.execute("SELECT promotion_status FROM context_frames").fetchone()[0]
    transition_count = conn.execute(
        "SELECT COUNT(*) FROM ucf_status_transitions"
    ).fetchone()[0]
    outbox_table_exists = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master "
        "WHERE type = 'table' AND name = 'ucf_qdrant_sync_outbox'"
    ).fetchone()[0]
    outbox_count = (
        conn.execute("SELECT COUNT(*) FROM ucf_qdrant_sync_outbox").fetchone()[0]
        if outbox_table_exists
        else 0
    )
    conn.close()
    assert status == "validated"
    assert transition_count == 0
    assert outbox_count == 0
    assert dematerialized == [{"video_hash": "vh_test_001"}]


def test_validate_ucf_frames_transitions_staged_to_validated(tmp_path, monkeypatch):
    """S1: validate_ucf_frames must transition staged frames to validated status.

    This is the write step in the lifecycle. After this call, frames are ready
    for promote_ucf_to_memory.
    """
    import sqlite3

    db_path = _make_ucf_db_with_staged_frame(tmp_path)
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))

    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)

    # Request confirmation token for validate_ucf_frames
    envelope, rc = client.execute_tool(
        tool_name="validate_ucf_frames",
        tool_args={"video_hash": "vh_test_001", "epoch_id": "epoch_test"},
    )
    assert rc == 3
    assert envelope["status"] == "needs_confirmation"
    token = envelope["result"]["confirmation_token"]

    # Confirm — staged frame must become validated
    result, rc2 = client.execute_tool(
        tool_name="validate_ucf_frames",
        tool_args={"video_hash": "vh_test_001", "epoch_id": "epoch_test"},
        confirm=True,
        confirmation_token=token,
    )
    assert rc2 == 0
    assert result["status"] == "success"
    output = result["output"]
    assert output["status"] == "validated_complete"
    assert output["validated_count"] == 1

    # Verify the DB row is now 'validated'
    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT promotion_status FROM context_frames LIMIT 1").fetchone()
    conn.close()
    assert row[0] == "validated"

    # Idempotency: calling again must update 0 rows (frame is already validated)
    envelope2, _ = client.execute_tool(
        tool_name="validate_ucf_frames",
        tool_args={"video_hash": "vh_test_001", "epoch_id": "epoch_test"},
    )
    token2 = envelope2["result"]["confirmation_token"]
    result2, _ = client.execute_tool(
        tool_name="validate_ucf_frames",
        tool_args={"video_hash": "vh_test_001", "epoch_id": "epoch_test"},
        confirm=True,
        confirmation_token=token2,
    )
    assert result2["output"]["validated_count"] == 0


# ---------------------------------------------------------------------------
# Phase 0.8 — Terminal Lifecycle State Tests (reject, supersede)
# ---------------------------------------------------------------------------

def _make_ucf_db_with_status(tmp_path, promotion_status: str, video_hash: str = "vh_test_001"):
    """Helper: create a minimal UCF DB with one frame in the given promotion_status."""
    import sys
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[2]
    import importlib.util
    ledger_path = repo_root / "scripts" / "ucf" / "ucf_ledger.py"
    spec = importlib.util.spec_from_file_location("ucf_ledger_helper2", str(ledger_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    db_path = tmp_path / "ucf_ledger.db"
    client = mod.UCFLedgerClient(str(db_path))
    client.init_schema()
    client.register_media(
        video_hash=video_hash,
        file_path="test.mp4",
        duration=10.0,
        fps=30.0,
        width=1920,
        height=1080,
    )
    client.log_frame(
        video_hash=video_hash,
        epoch_id="epoch_test",
        run_id="run_test",
        t_start=0.0,
        t_end=1.0,
        modality="video",
        worker_name="image_embed_clip",
        model_tag="openai/clip-vit-large-patch14",
        payload={"label": "test_frame"},
        promotion_status="staged",
    )
    # Apply the desired starting status if not staged
    import sqlite3
    if promotion_status != "staged":
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "UPDATE context_frames SET promotion_status = ? WHERE video_hash = ?",
            (promotion_status, video_hash)
        )
        conn.commit()
        conn.close()
    client.close()
    return db_path


def _confirm_tool(client, tool_name, tool_args):
    """Helper: request token then confirm in one call. Returns (result, rc)."""
    envelope, rc = client.execute_tool(tool_name=tool_name, tool_args=tool_args)
    assert rc == 3, f"Expected needs_confirmation (3), got {rc}"
    token = envelope["result"]["confirmation_token"]
    return client.execute_tool(
        tool_name=tool_name,
        tool_args=tool_args,
        confirm=True,
        confirmation_token=token,
    )


def test_promote_materializes_only_the_exact_epoch(tmp_path, monkeypatch):
    """A scoped promotion must not materialize promoted frames from another epoch."""
    import sqlite3

    db_path = _make_ucf_db_with_status(tmp_path, "promoted")
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "UPDATE context_frames SET epoch_id = 'epoch_old', run_id = 'run_old'"
    )
    old_frame_id = conn.execute(
        "SELECT frame_id FROM context_frames WHERE epoch_id = 'epoch_old'"
    ).fetchone()[0]
    cursor = conn.execute(
        """
        INSERT INTO context_frames (
            video_hash, ucf_schema_version, epoch_id, run_id, t_start, t_end,
            modality, worker_name, model_tag, payload, payload_hash,
            promotion_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "vh_test_001",
            "ucf.v0.1",
            "epoch_target",
            "run_target",
            2.0,
            3.0,
            "video",
            "image_embed_clip",
            "openai/clip-vit-large-patch14",
            "{}",
            "target-hash",
            "validated",
        ),
    )
    target_frame_id = cursor.lastrowid
    conn.commit()
    conn.close()

    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)
    _allow_verified_promotion_delivery(client, monkeypatch)

    result, rc = _confirm_tool(
        client,
        "promote_ucf_to_memory",
        {"video_hash": "vh_test_001", "epoch_id": "epoch_target"},
    )

    assert rc == 0
    promoted_frame_ids = result["output"]["materialization_report"]["scope"][
        "promoted_frame_ids"
    ]
    assert promoted_frame_ids == [target_frame_id]
    assert old_frame_id not in promoted_frame_ids


def test_reject_ucf_frames_transitions_staged_to_rejected(tmp_path, monkeypatch):
    """Phase 0.8: reject_ucf_frames must transition staged frames to rejected.

    Rejected is a terminal state — frames that are rejected cannot be promoted.
    """
    import sqlite3

    db_path = _make_ucf_db_with_status(tmp_path, "staged")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)

    result, rc = _confirm_tool(
        client, "reject_ucf_frames",
        {"video_hash": "vh_test_001", "epoch_id": "epoch_test", "reason": "bad quality frame"},
    )
    assert rc == 0
    assert result["status"] == "success"
    output = result["output"]
    assert output["status"] == "rejected_complete"
    assert output["rejected_count"] == 1

    # Verify DB row is 'rejected'
    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT promotion_status FROM context_frames LIMIT 1").fetchone()
    conn.close()
    assert row[0] == "rejected"


def test_reject_ucf_frames_transitions_validated_to_rejected(tmp_path, monkeypatch):
    """Phase 0.8: reject_ucf_frames must also transition validated frames to rejected."""
    import sqlite3

    db_path = _make_ucf_db_with_status(tmp_path, "validated")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)

    result, rc = _confirm_tool(
        client, "reject_ucf_frames",
        {"video_hash": "vh_test_001", "epoch_id": "epoch_test", "reason": "validation failed"},
    )
    assert rc == 0
    assert result["output"]["rejected_count"] == 1

    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT promotion_status FROM context_frames LIMIT 1").fetchone()
    conn.close()
    assert row[0] == "rejected"


def test_reject_invalid_transition_from_promoted(tmp_path, monkeypatch):
    """Phase 0.8: reject_ucf_frames cannot reject already-promoted frames (0 rows)."""
    import sqlite3

    db_path = _make_ucf_db_with_status(tmp_path, "promoted")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)

    result, rc = _confirm_tool(
        client, "reject_ucf_frames",
        {"video_hash": "vh_test_001", "epoch_id": "epoch_test", "reason": "trying to reject promoted"},
    )
    assert rc == 0
    assert result["output"]["status"] == "blocked"
    assert result["output"]["reason"] == "cannot_reject_promoted_frames"
    assert "Cannot reject" in result["output"]["message"]

    # DB row must still be 'promoted'
    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT promotion_status FROM context_frames LIMIT 1").fetchone()
    conn.close()
    assert row[0] == "promoted"


def test_idempotency_reject_already_rejected(tmp_path, monkeypatch):
    """Phase 0.8: calling reject_ucf_frames on already-rejected frames returns 0."""
    db_path = _make_ucf_db_with_status(tmp_path, "rejected")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)

    result, rc = _confirm_tool(
        client, "reject_ucf_frames",
        {"video_hash": "vh_test_001", "epoch_id": "epoch_test", "reason": "duplicate call"},
    )
    assert rc == 0
    assert result["output"]["rejected_count"] == 0  # idempotent


def test_supersede_ucf_frames_transitions_promoted_to_superseded(tmp_path, monkeypatch):
    """Phase 0.8: supersede_ucf_frames transitions promoted frames to superseded.

    This is the re-ingest supersession path: old epoch promoted frames are marked
    superseded before the new epoch is validated and promoted.
    """
    import sqlite3

    db_path = _make_ucf_db_with_status(tmp_path, "promoted")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)

    result, rc = _confirm_tool(
        client, "supersede_ucf_frames",
        {"video_hash": "vh_test_001", "epoch_id": "epoch_test"},
    )
    assert rc == 0
    assert result["status"] == "success"
    output = result["output"]
    assert output["status"] == "superseded_complete"
    assert output["superseded_count"] == 1

    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT promotion_status FROM context_frames LIMIT 1").fetchone()
    conn.close()
    assert row[0] == "superseded"


def test_supersede_ucf_frames_transitions_validated_to_superseded(tmp_path, monkeypatch):
    """Phase 0.8: supersede_ucf_frames also transitions validated frames to superseded."""
    import sqlite3

    db_path = _make_ucf_db_with_status(tmp_path, "validated")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)

    result, rc = _confirm_tool(
        client, "supersede_ucf_frames",
        {"video_hash": "vh_test_001", "epoch_id": "epoch_test"},
    )
    assert rc == 0
    assert result["output"]["superseded_count"] == 1

    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT promotion_status FROM context_frames LIMIT 1").fetchone()
    conn.close()
    assert row[0] == "superseded"


def test_supersede_invalid_transition_from_staged(tmp_path, monkeypatch):
    """Phase 0.8: supersede_ucf_frames cannot supersede staged frames (0 rows)."""
    import sqlite3

    db_path = _make_ucf_db_with_status(tmp_path, "staged")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)

    result, rc = _confirm_tool(
        client, "supersede_ucf_frames",
        {"video_hash": "vh_test_001", "epoch_id": "epoch_test"},
    )
    assert rc == 0
    # Staged is not in IN('promoted','validated'), so 0 rows updated
    assert result["output"]["superseded_count"] == 0

    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT promotion_status FROM context_frames LIMIT 1").fetchone()
    conn.close()
    assert row[0] == "staged"


def test_idempotency_supersede_already_superseded(tmp_path, monkeypatch):
    """Phase 0.8: calling supersede_ucf_frames on already-superseded frames returns 0."""
    db_path = _make_ucf_db_with_status(tmp_path, "superseded")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)

    result, rc = _confirm_tool(
        client, "supersede_ucf_frames",
        {"video_hash": "vh_test_001", "epoch_id": "epoch_test"},
    )
    assert rc == 0
    assert result["output"]["superseded_count"] == 0


def test_promotion_excludes_rejected_frames(tmp_path, monkeypatch):
    """Phase 0.8: promote_ucf_to_memory must promote only validated frames.

    Rejected frames in scope are left alone — they are excluded by the
    promotion SQL (validates only). This test verifies that a mix of
    validated + rejected frames results in: validated → promoted, rejected stays.
    """
    import sqlite3
    from pathlib import Path
    import importlib.util

    repo_root = Path(__file__).resolve().parents[2]
    ledger_path = repo_root / "scripts" / "ucf" / "ucf_ledger.py"
    spec = importlib.util.spec_from_file_location("ucf_ledger_promo_ex", str(ledger_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    db_path = tmp_path / "ucf_ledger.db"
    lc = mod.UCFLedgerClient(str(db_path))
    lc.init_schema()
    lc.register_media(
        video_hash="vh_test_001", file_path="t.mp4", duration=10.0, fps=30.0, width=1920, height=1080
    )
    # Frame 1: validated (should be promoted)
    lc.log_frame(
        video_hash="vh_test_001", epoch_id="epoch_test", run_id="run_test",
        t_start=0.0, t_end=1.0, modality="video", worker_name="image_embed_clip",
        model_tag="openai/clip-vit-large-patch14", payload={"label": "good"},
        promotion_status="staged",
    )
    # Frame 2: will be rejected (should not be promoted)
    lc.log_frame(
        video_hash="vh_test_001", epoch_id="epoch_test", run_id="run_test",
        t_start=1.0, t_end=2.0, modality="video", worker_name="image_embed_clip",
        model_tag="openai/clip-vit-large-patch14", payload={"label": "bad"},
        promotion_status="staged",
    )
    lc.close()

    # Manually set frame status: frame 1 → validated, frame 2 → rejected
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE context_frames SET promotion_status = 'validated' WHERE t_start = 0.0")
    conn.execute("UPDATE context_frames SET promotion_status = 'rejected' WHERE t_start = 1.0")
    conn.commit()
    conn.close()

    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)
    _allow_verified_promotion_delivery(client, monkeypatch)

    # No staged frames → pre-check passes; only validated (1) should be promoted
    result, rc = _confirm_tool(
        client, "promote_ucf_to_memory",
        {"video_hash": "vh_test_001", "epoch_id": "epoch_test"},
    )
    assert rc == 0
    output = result["output"]
    assert output["status"] == "promoted_complete"
    assert output["promoted_count"] == 1  # exactly 1, not 2

    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT promotion_status FROM context_frames ORDER BY t_start").fetchall()
    conn.close()
    assert rows[0][0] == "promoted"   # frame 1 promoted
    assert rows[1][0] == "rejected"   # frame 2 unchanged


def test_reingest_supersession_flow(tmp_path, monkeypatch):
    """Phase 0.8: full re-ingest supersession flow end-to-end.

    1. Promote old epoch frames → promoted
    2. Supersede old epoch → superseded
    3. Add new epoch frames → staged
    4. Validate new epoch → validated
    5. Promote new epoch → promoted
    6. Assert old frames are superseded, new frames are promoted
    """
    import sqlite3
    from pathlib import Path
    import importlib.util

    repo_root = Path(__file__).resolve().parents[2]
    ledger_path = repo_root / "scripts" / "ucf" / "ucf_ledger.py"
    spec = importlib.util.spec_from_file_location("ucf_ledger_reingest", str(ledger_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    db_path = tmp_path / "ucf_ledger.db"
    lc = mod.UCFLedgerClient(str(db_path))
    lc.init_schema()
    lc.register_media(
        video_hash="vh_vid_001", file_path="v.mp4", duration=10.0, fps=30.0, width=1920, height=1080
    )
    # Old epoch frame (starts as staged)
    lc.log_frame(
        video_hash="vh_vid_001", epoch_id="epoch_old", run_id="run_old",
        t_start=0.0, t_end=1.0, modality="video", worker_name="image_embed_clip",
        model_tag="clip-v1", payload={"label": "old"}, promotion_status="staged",
    )
    lc.close()

    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)
    _allow_verified_promotion_delivery(client, monkeypatch)

    # Step 1: validate old epoch
    r, rc = _confirm_tool(client, "validate_ucf_frames", {"video_hash": "vh_vid_001", "epoch_id": "epoch_old"})
    assert rc == 0
    assert r["output"]["validated_count"] == 1

    # Step 2: promote old epoch
    r, rc = _confirm_tool(client, "promote_ucf_to_memory", {"video_hash": "vh_vid_001", "epoch_id": "epoch_old"})
    assert rc == 0
    assert r["output"]["promoted_count"] == 1

    # Step 3: supersede old epoch
    r, rc = _confirm_tool(client, "supersede_ucf_frames", {"video_hash": "vh_vid_001", "epoch_id": "epoch_old"})
    assert rc == 0
    assert r["output"]["superseded_count"] == 1

    # Step 4: insert new epoch frame (staged)
    lc2 = mod.UCFLedgerClient(str(db_path))
    lc2.init_schema()
    lc2.log_frame(
        video_hash="vh_vid_001", epoch_id="epoch_new", run_id="run_new",
        t_start=0.0, t_end=1.0, modality="video", worker_name="image_embed_clip",
        model_tag="clip-v2", payload={"label": "new"}, promotion_status="staged",
    )
    lc2.close()

    # Step 5: validate new epoch
    r, rc = _confirm_tool(client, "validate_ucf_frames", {"video_hash": "vh_vid_001", "epoch_id": "epoch_new"})
    assert rc == 0
    assert r["output"]["validated_count"] == 1

    # Step 6: promote new epoch
    r, rc = _confirm_tool(client, "promote_ucf_to_memory", {"video_hash": "vh_vid_001", "epoch_id": "epoch_new"})
    assert rc == 0
    assert r["output"]["promoted_count"] == 1

    # Final assertion: old frame is superseded, new frame is promoted
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT epoch_id, promotion_status FROM context_frames ORDER BY epoch_id"
    ).fetchall()
    conn.close()
    status_map = {row[0]: row[1] for row in rows}
    assert status_map["epoch_new"] == "promoted"
    assert status_map["epoch_old"] == "superseded"


# ---------------------------------------------------------------------------
# Phase 0.8 — Tool Registry Completeness Matrix Test
# ---------------------------------------------------------------------------

def test_hitl_tool_registry_completeness():
    """Every locally confirmed native tool must stay registered for execution and audit.

    This test is the single source of truth for the tool registration contract.
    If a new HITL-gated tool is added without being registered in all locations,
    this test will fail immediately on the first run.

    Required locations:
    1. LOCAL_CONFIRMATION_REQUIRED_TOOLS (module-level authority)
    2. MUTATING_DENY_ON_AGENT_FAILURE
    3. Dispatch 'elif tool_name ==' chain in execute_tool()
    4. declared_mutation set used by side_effect_report in execute_tool()
    """
    import inspect
    import re
    from agents.mini_agent_client import (
        LOCAL_AUTHORIZATION_ONLY_ACTIONS,
        LOCAL_CONFIRMATION_REQUIRED_TOOLS,
        MUTATING_DENY_ON_AGENT_FAILURE,
    )

    assert LOCAL_CONFIRMATION_REQUIRED_TOOLS == EXPECTED_LOCAL_CONFIRMATION_REQUIRED_TOOLS

    for tool in LOCAL_CONFIRMATION_REQUIRED_TOOLS:
        assert tool in MUTATING_DENY_ON_AGENT_FAILURE, (
            f"HITL tool '{tool}' missing from MUTATING_DENY_ON_AGENT_FAILURE"
        )

    # Inspect source for dispatch and mutation reporting registrations.
    source = inspect.getsource(MiniAgentClient)

    for tool in LOCAL_CONFIRMATION_REQUIRED_TOOLS - LOCAL_AUTHORIZATION_ONLY_ACTIONS:
        assert f'tool_name == "{tool}"' in source or f"tool_name == '{tool}'" in source, (
            f"HITL tool '{tool}' missing from dispatch elif chain in execute_tool()"
        )

        mutated_match = re.search(
            r'declared_mutation\s*=\s*tool_name\s+in\s+\(([^)]+)\)',
            source, re.DOTALL
        )
        assert mutated_match, "declared_mutation set not found in MiniAgentClient"
        mutated_tools_str = mutated_match.group(1)
        assert tool in mutated_tools_str, (
            f"HITL tool '{tool}' missing from declared_mutation"
        )


# ---------------------------------------------------------------------------
# Phase 0.8 — Offline Fallback Denial Tests for Subprocess-Only Tools
# ---------------------------------------------------------------------------

def test_offline_fallback_denies_kg_write(monkeypatch):
    """Phase 0.8: kg_write must be denied under offline fallback policy.

    kg_write is a MUTATING tool with no native dispatch. When goodq_mini_agent
    is offline (subprocess fails), MUTATING_DENY_ON_AGENT_FAILURE must block it.
    """
    client = MiniAgentClient(profile="safe")
    with patch.object(client._runner, "run_task",
                      side_effect=RuntimeError("agent offline")):
        envelope, rc = client.validate_action(
            prompt="Write entity",
            mode="ops",
            tool_name="kg_write",
            tool_args={"entity": "test"},
        )
    assert rc == 1
    assert envelope["status"] == "error"
    errors = envelope.get("errors", [])
    assert any("kg_write" in str(e) for e in errors), (
        f"Expected kg_write to appear in error, got: {errors}"
    )


def test_offline_fallback_denies_faiss_write(monkeypatch):
    """Phase 0.8: faiss_write must be denied under offline fallback policy."""
    client = MiniAgentClient(profile="safe")
    with patch.object(client._runner, "run_task",
                      side_effect=RuntimeError("agent offline")):
        envelope, rc = client.validate_action(
            prompt="Write FAISS vector",
            mode="ops",
            tool_name="faiss_write",
            tool_args={"vector": [0.1, 0.2]},
        )
    assert rc == 1
    assert envelope["status"] == "error"
    errors = envelope.get("errors", [])
    assert any("faiss_write" in str(e) for e in errors), (
        f"Expected faiss_write to appear in error, got: {errors}"
    )


def test_offline_fallback_denies_config_write(monkeypatch):
    """Phase 0.8: config_write must be denied under offline fallback policy."""
    client = MiniAgentClient(profile="safe")
    with patch.object(client._runner, "run_task",
                      side_effect=RuntimeError("agent offline")):
        envelope, rc = client.validate_action(
            prompt="Write config",
            mode="ops",
            tool_name="config_write",
            tool_args={"key": "test_key", "value": "test_value"},
        )
    assert rc == 1
    assert envelope["status"] == "error"
    errors = envelope.get("errors", [])
    assert any("config_write" in str(e) for e in errors), (
        f"Expected config_write to appear in error, got: {errors}"
    )


def test_tool_registration_matrix_extraction():
    """Verify the registration matrix of tools in mini_agent_client.py.
    
    This test reads the source file of mini_agent_client.py directly, 
    slices out the set definitions for gated and mutating tools,
    evaluates or parses them, and asserts they are configured correctly.
    """
    client_src_path = Path(__file__).resolve().parent.parent.parent / "agents" / "mini_agent_client.py"
    assert client_src_path.exists(), f"Could not find {client_src_path}"
    
    src = client_src_path.read_text(encoding="utf-8")
    
    # Slice out MUTATING_DENY_ON_AGENT_FAILURE set
    start_str = "MUTATING_DENY_ON_AGENT_FAILURE = {"
    idx_start = src.find(start_str)
    assert idx_start != -1, "MUTATING_DENY_ON_AGENT_FAILURE not found in source code"
    idx_end = src.find("}", idx_start)
    assert idx_end != -1, "Closing bracket for MUTATING_DENY_ON_AGENT_FAILURE not found"
    
    mutating_slice = src[idx_start + len(start_str):idx_end]
    import re
    mutating_tools = set(re.findall(r'["\']([^"\']+)["\']', mutating_slice))
    
    # Assert mutating tools set contains the expected lifecycle and system tools
    expected_mutating = {
        "home_assistant_call_service",
        "qdrant_upsert",
        "faiss_write",
        "kg_write",
        "config_write",
        "file_delete",
        "file_move",
        "run_ingestion",
        "watchdog_trigger",
        "process_start",
        "process_stop",
        "promote_ucf_to_memory",
        "reconcile_ucf_qdrant",
        "validate_ucf_frames",
        "reject_ucf_frames",
        "supersede_ucf_frames"
    }
    
    for tool in expected_mutating:
        assert tool in mutating_tools, f"Expected mutating tool '{tool}' not found in MUTATING_DENY_ON_AGENT_FAILURE matrix"
        
    # Slice out the one module-level local confirmation authority set.
    start_str_native = "LOCAL_CONFIRMATION_REQUIRED_TOOLS = {"
    idx_start_native = src.find(start_str_native)
    assert idx_start_native != -1, "LOCAL_CONFIRMATION_REQUIRED_TOOLS not found in source code"
    idx_end_native = src.find("}", idx_start_native)
    assert idx_end_native != -1, "Closing bracket for LOCAL_CONFIRMATION_REQUIRED_TOOLS not found"
    
    native_slice = src[idx_start_native + len(start_str_native):idx_end_native]
    native_gated_tools = set(re.findall(r'["\']([^"\']+)["\']', native_slice))
    
    assert native_gated_tools == EXPECTED_LOCAL_CONFIRMATION_REQUIRED_TOOLS


# ---------------------------------------------------------------------------
# UCF Retrieval Bridge Tests (17)
# ---------------------------------------------------------------------------

import sqlite3
import requests
from steps.common.qdrant_client import QdrantClient, QdrantConfig

# Helper: Create a mock database with frame records
def _create_mock_db_for_test(tmp_path, promotion_status="validated", vector_key="vector-key-1", vector_collection="goodq_clip", vector_backend="qdrant"):
    db_path = tmp_path / "ucf_ledger.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
    CREATE TABLE IF NOT EXISTS media_sources (
        video_hash TEXT PRIMARY KEY,
        file_path TEXT NOT NULL,
        duration REAL NOT NULL,
        fps REAL NOT NULL,
        width INTEGER NOT NULL,
        height INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS context_frames (
        frame_id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_hash TEXT NOT NULL,
        ucf_schema_version TEXT NOT NULL,
        epoch_id TEXT NOT NULL,
        run_id TEXT NOT NULL,
        t_start REAL NOT NULL,
        t_end REAL NOT NULL,
        modality TEXT NOT NULL,
        worker_name TEXT NOT NULL,
        model_tag TEXT NOT NULL,
        confidence REAL NOT NULL DEFAULT 1.0,
        spatial_region TEXT,
        spatial_space TEXT NOT NULL DEFAULT 'normalized_yxyx_top_left',
        vector_key TEXT,
        vector_backend TEXT,
        vector_collection TEXT,
        vector_dim INTEGER,
        vector_model_tag TEXT,
        source_artifact_id TEXT,
        raw_ref TEXT,
        payload TEXT NOT NULL,
        payload_hash TEXT NOT NULL,
        promotion_status TEXT NOT NULL DEFAULT 'staged',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (video_hash) REFERENCES media_sources(video_hash)
    );
    """)
    conn.execute("INSERT OR REPLACE INTO media_sources VALUES ('vh_test_001', 'test.mp4', 10.0, 30.0, 1920, 1080, '2026-06-15')")
    
    # Log a frame
    conn.execute("""
    INSERT INTO context_frames (
        video_hash, ucf_schema_version, epoch_id, run_id, t_start, t_end,
        modality, worker_name, model_tag, confidence, spatial_region, spatial_space,
        vector_key, vector_backend, vector_collection, vector_dim, vector_model_tag,
        source_artifact_id, raw_ref, payload, payload_hash, promotion_status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        'vh_test_001', 'ucf.v0.1', 'epoch_test', 'run_test', 0.0, 1.0,
        'video', 'image_embed_clip', 'openai/clip-vit-large-patch14', 1.0,
        None, 'normalized_yxyx_top_left', vector_key, vector_backend, vector_collection,
        384, 'openai/clip-vit-large-patch14', 'scene_001', None, '{}', 'hash', promotion_status
    ))
    conn.commit()
    conn.close()
    return db_path

# Helper for HITL confirmation
def _confirm_tool_directly(client, tool_name, tool_args):
    envelope, rc = client.execute_tool(tool_name=tool_name, tool_args=tool_args)
    assert rc == 3, f"Expected needs_confirmation (3), got {rc}"
    token = envelope["result"]["confirmation_token"]
    return client.execute_tool(
        tool_name=tool_name,
        tool_args=tool_args,
        confirm=True,
        confirmation_token=token,
    )

# set_payload tests

@patch("requests.Session.put")
def test_set_payload_calls_qdrant_http_endpoint(mock_put):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_put.return_value = mock_response

    cfg = QdrantConfig(host="http://localhost:6333", collection="goodq_text", dim=384)
    client = QdrantClient(cfg)
    
    res = client.set_payload(["uuid-1", "uuid-2"], {"status": "promoted"})
    assert res is True
    mock_put.assert_called_once()
    args, kwargs = mock_put.call_args
    assert "http://localhost:6333/collections/goodq_text/points/payload?wait=true" in args[0]
    assert kwargs["json"]["payload"] == {"status": "promoted"}

@patch("requests.Session.put")
def test_set_payload_returns_false_on_http_failure(mock_put):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_put.return_value = mock_response

    cfg = QdrantConfig(host="http://localhost:6333", collection="goodq_text", dim=384)
    client = QdrantClient(cfg)

    res = client.set_payload(["uuid-1"], {"status": "promoted"})
    assert res is False

@patch("requests.Session.put")
def test_set_payload_returns_false_on_exception(mock_put):
    mock_put.side_effect = requests.exceptions.ConnectionError("Connection refused")

    cfg = QdrantConfig(host="http://localhost:6333", collection="goodq_text", dim=384)
    client = QdrantClient(cfg)

    with patch("steps.common.qdrant_client.logger.warning") as mock_warn:
        res = client.set_payload(["uuid-1"], {"status": "promoted"})
        assert res is False
        mock_warn.assert_called()

@patch("requests.Session.put")
def test_set_payload_normalizes_point_ids_before_request(mock_put):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_put.return_value = mock_response

    cfg = QdrantConfig(host="http://localhost:6333", collection="goodq_text", dim=384)
    client = QdrantClient(cfg)

    raw_points = ["my-arbitrary-string-key"]
    res = client.set_payload(raw_points, {"status": "promoted"})
    assert res is True
    
    mock_put.assert_called_once()
    args, kwargs = mock_put.call_args
    sent_points = kwargs["json"]["points"]
    assert len(sent_points) == 1
    assert sent_points[0] != "my-arbitrary-string-key"

@patch("requests.Session.put")
def test_set_payload_empty_points_noop(mock_put):
    cfg = QdrantConfig(host="http://localhost:6333", collection="goodq_text", dim=384)
    client = QdrantClient(cfg)

    res = client.set_payload([], {"status": "promoted"})
    assert res is True
    mock_put.assert_not_called()

# Lifecycle sync tests

@patch("requests.post")
def test_promote_syncs_ucf_promotion_status_to_qdrant(mock_post, tmp_path, monkeypatch):
    import uuid

    db_path = _create_mock_db_for_test(tmp_path, "validated", vector_key="vec-key-1", vector_collection="goodq_clip")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    update_response = MagicMock(status_code=200)
    point_id = str(
        uuid.uuid5(
            uuid.UUID("2058b732-6666-5424-a820-5cf54ef071c4"), "vec-key-1"
        )
    )
    preflight_response = MagicMock(status_code=200)
    preflight_response.json.return_value = {
        "result": [
            {
                "id": point_id,
                "payload": {
                    "video_hash": "vh_test_001",
                    "epoch_id": "epoch_test",
                    "ucf_promotion_status": "staged",
                },
            }
        ]
    }
    verify_response = MagicMock(status_code=200)
    verify_response.json.return_value = {
        "result": [
            {
                "id": point_id,
                "payload": {
                    "video_hash": "vh_test_001",
                    "epoch_id": "epoch_test",
                    "ucf_promotion_status": "promoted",
                },
            }
        ]
    }
    mock_post.side_effect = [preflight_response, update_response, verify_response]

    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)
    monkeypatch.setattr(client, "_fetch_vector_from_qdrant", lambda *_: None)
    monkeypatch.setattr(
        client,
        "_sync_qdrant_by_scope",
        lambda **_: {
            "status": "ok",
            "points_verified": 1,
            "failed_collections": [],
        },
    )
    monkeypatch.setattr(
        client, "_execute_validate_ucf_epoch", lambda _args: {"success": True, "errors": []}
    )

    res, rc = _confirm_tool_directly(client, "promote_ucf_to_memory", {"video_hash": "vh_test_001", "epoch_id": "epoch_test"})
    assert rc == 0
    assert res["status"] == "success"
    
    output = res["output"]
    assert output["status"] == "promoted_complete"
    assert output["promoted_count"] == 1
    
    q_sync = output["qdrant_sync"]
    assert q_sync["attempted"] is True
    assert q_sync["status"] == "ok"


@patch("requests.post")
def test_ucf_status_sync_normalizes_numeric_point_ids_as_integers(mock_post):
    update_response = MagicMock(status_code=200)
    verify_response = MagicMock(status_code=200)
    verify_response.json.return_value = {
        "result": [
            {"id": 123, "payload": {"ucf_promotion_status": "promoted"}}
        ]
    }
    mock_post.side_effect = [update_response, verify_response]
    client = MiniAgentClient(profile="safe")

    result = client._sync_ucf_status_to_qdrant(
        [("123", "goodq_text", "qdrant")], "promoted"
    )

    assert result["status"] == "ok"
    assert mock_post.call_args_list[0].kwargs["json"]["points"] == [123]
    assert mock_post.call_args_list[1].kwargs["json"]["ids"] == [123]


@patch("requests.post")
def test_row_sync_rejects_wrong_scope_before_mutation(mock_post):
    preflight_response = MagicMock(status_code=200)
    preflight_response.json.return_value = {
        "result": [
            {
                "id": "point-a",
                "payload": {
                    "video_hash": "video-b",
                    "epoch_id": "epoch_test",
                    "ucf_promotion_status": "staged",
                },
            }
        ]
    }
    mock_post.return_value = preflight_response
    client = MiniAgentClient(
        profile="safe", config={"qdrant": {"host": "http://qdrant.test"}}
    )

    result = client._sync_ucf_status_to_qdrant(
        [("point-a", "goodq_text_epoch_test", "qdrant")],
        "promoted",
        expected_video_hash="video-a",
        expected_epoch_id="epoch_test",
    )

    assert result["status"] == "warning"
    assert result["points_verified"] == 0
    assert len(mock_post.call_args_list) == 1
    assert mock_post.call_args_list[0].args[0].endswith("/points")


@patch("requests.post")
def test_promote_qdrant_sync_failure_is_pending_and_visible(mock_post, tmp_path, monkeypatch):
    db_path = _create_mock_db_for_test(tmp_path, "validated", vector_key="vec-key-1", vector_collection="goodq_clip")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.text = '{"error": "not found"}'
    mock_resp.json.return_value = {"result": {"collections": []}}
    mock_post.return_value = mock_resp

    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)
    monkeypatch.setattr(
        client,
        "_sync_qdrant_by_scope",
        lambda **_: {"status": "skipped", "failed_collections": []},
    )
    monkeypatch.setattr(
        client, "_execute_validate_ucf_epoch", lambda _args: {"success": True, "errors": []}
    )

    res, rc = _confirm_tool_directly(client, "promote_ucf_to_memory", {"video_hash": "vh_test_001", "epoch_id": "epoch_test"})
    assert rc == 1
    assert res["status"] == "error"
    assert res["errors"][0]["code"] == "promotion_committed_sync_pending"
    
    output = res["output"]
    assert output["status"] == "promotion_committed_sync_pending"
    
    q_sync = output["qdrant_sync"]
    assert q_sync["attempted"] is True
    assert q_sync["status"] == "warning"
    assert "qdrant_payload_sync_failed" in output["warnings"]
    assert output["outbox"]["delivery_state"] == "pending"


@patch("requests.get")
@patch("requests.post")
def test_scope_sync_filters_and_verifies_only_the_exact_video(
    mock_post, mock_get
):
    collection_response = MagicMock()
    collection_response.status_code = 200
    collection_response.json.return_value = {
        "result": {
            "collections": [
                {"name": "goodq_text_epoch_test"},
                {"name": "goodq_clip_epoch_test"},
                {"name": "goodq_text_other_epoch_test"},
                {"name": "goodq_text_epoch_test_other"},
            ]
        }
    }
    mock_get.return_value = collection_response
    preflight_response = MagicMock(status_code=200)
    preflight_response.json.return_value = {
        "result": {
            "points": [
                {
                    "id": "point-video-a",
                    "payload": {
                        "video_hash": "video-a",
                        "epoch_id": "epoch_test",
                        "ucf_promotion_status": "staged",
                    },
                }
            ],
            "next_page_offset": None,
        }
    }
    update_response = MagicMock()
    update_response.status_code = 200
    verified_response = MagicMock()
    verified_response.status_code = 200
    verified_response.json.return_value = {
        "result": {
            "points": [
                {
                    "id": "point-video-a",
                    "payload": {
                        "video_hash": "video-a",
                        "epoch_id": "epoch_test",
                        "ucf_promotion_status": "promoted",
                    },
                }
            ],
            "next_page_offset": None,
        }
    }
    mock_post.side_effect = [
        preflight_response,
        update_response,
        verified_response,
        preflight_response,
        update_response,
        verified_response,
    ]
    client = MiniAgentClient(
        profile="safe", config={"qdrant": {"host": "http://qdrant.test"}}
    )

    result = client._sync_qdrant_by_scope(
        epoch_id="epoch_test",
        status_val="promoted",
        video_hash="video-a",
    )

    assert result["status"] == "ok"
    assert result["points_verified"] == 2
    assert result["collections_swept"] == [
        "goodq_clip_epoch_test",
        "goodq_text_epoch_test",
    ]
    expected_scope_filter = {
        "must": [
            {"key": "video_hash", "match": {"value": "video-a"}},
        ]
    }
    expected_mutation_filter = {
        "must": [
            {"key": "video_hash", "match": {"value": "video-a"}},
            {
                "key": "ucf_promotion_status",
                "match": {"any": ["staged", "validated", "promoted"]},
            },
        ]
    }
    for index in (0, 3):
        assert mock_post.call_args_list[index].kwargs["json"]["filter"] == expected_scope_filter
    for index in (1, 2, 4, 5):
        assert mock_post.call_args_list[index].kwargs["json"]["filter"] == expected_mutation_filter


@patch("requests.get")
@patch("requests.post")
def test_scope_promotion_filter_allowlists_nonterminal_sources(mock_post, mock_get):
    collection_response = MagicMock(status_code=200)
    collection_response.json.return_value = {
        "result": {"collections": [{"name": "goodq_text_epoch_test"}]}
    }
    mock_get.return_value = collection_response
    preflight_response = MagicMock(status_code=200)
    preflight_response.json.return_value = {
        "result": {
            "points": [
                {
                    "id": "point-video-a",
                    "payload": {
                        "video_hash": "video-a",
                        "epoch_id": "epoch_test",
                        "ucf_promotion_status": "staged",
                    },
                }
            ],
            "next_page_offset": None,
        }
    }
    update_response = MagicMock(status_code=200)
    verified_response = MagicMock(status_code=200)
    verified_response.json.return_value = {
        "result": {
            "points": [
                {
                    "id": "point-video-a",
                    "payload": {
                        "video_hash": "video-a",
                        "epoch_id": "epoch_test",
                        "ucf_promotion_status": "promoted",
                    },
                }
            ],
            "next_page_offset": None,
        }
    }
    mock_post.side_effect = [preflight_response, update_response, verified_response]
    client = MiniAgentClient(
        profile="safe", config={"qdrant": {"host": "http://qdrant.test"}}
    )

    result = client._sync_qdrant_by_scope(
        epoch_id="epoch_test", status_val="promoted", video_hash="video-a"
    )

    assert result["status"] == "ok"
    update_filter = mock_post.call_args_list[1].kwargs["json"]["filter"]
    lifecycle_match = next(
        item["match"]["any"]
        for item in update_filter["must"]
        if item["key"] == "ucf_promotion_status"
    )
    assert lifecycle_match == ["staged", "validated", "promoted"]


@patch("requests.get")
@patch("requests.post")
def test_scope_sync_uses_exact_epoch_collection_for_legacy_audio_payloads(
    mock_post, mock_get
):
    collection_response = MagicMock(status_code=200)
    collection_response.json.return_value = {
        "result": {"collections": [{"name": "goodq_audio_epoch_test"}]}
    }
    mock_get.return_value = collection_response
    preflight_response = MagicMock(status_code=200)
    preflight_response.json.return_value = {
        "result": {
            "points": [
                {
                    "id": "audio-point",
                    "payload": {
                        "video_hash": "video-a",
                        "ucf_promotion_status": "staged",
                    },
                }
            ],
            "next_page_offset": None,
        }
    }
    update_response = MagicMock(status_code=200)
    verified_response = MagicMock(status_code=200)
    verified_response.json.return_value = {
        "result": {
            "points": [
                {
                    "id": "audio-point",
                    "payload": {
                        "video_hash": "video-a",
                        "ucf_promotion_status": "promoted",
                    },
                }
            ],
            "next_page_offset": None,
        }
    }
    mock_post.side_effect = [preflight_response, update_response, verified_response]
    client = MiniAgentClient(
        profile="safe", config={"qdrant": {"host": "http://qdrant.test"}}
    )

    result = client._sync_qdrant_by_scope(
        epoch_id="epoch_test", status_val="promoted", video_hash="video-a"
    )

    assert result["status"] == "ok"
    assert result["points_verified"] == 1
    exact_filter = mock_post.call_args_list[0].kwargs["json"]["filter"]
    assert [entry["key"] for entry in exact_filter["must"]] == ["video_hash"]


@patch("requests.get")
@patch("requests.post")
def test_scope_sync_ignores_configured_epoch_collection_for_another_epoch(
    mock_post, mock_get
):
    collection_response = MagicMock(status_code=200)
    collection_response.json.return_value = {
        "result": {"collections": [{"name": "goodq_audio_epoch_old"}]}
    }
    mock_get.return_value = collection_response
    client = MiniAgentClient(
        profile="safe",
        config={
            "qdrant": {
                "host": "http://qdrant.test",
                "collections": {"audio": "goodq_audio_epoch_old"},
            }
        },
    )

    result = client._sync_qdrant_by_scope(
        epoch_id="epoch_test", status_val="promoted", video_hash="video-a"
    )

    assert result["status"] == "error"
    assert result["reason"] == "no_epoch_collections"
    mock_post.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        {"video_hash": "video-a"},
        {
            "video_hash": "video-a",
            "epoch_id": "epoch-other",
            "ucf_promotion_status": "staged",
        },
    ],
    ids=["lifecycle-anonymous", "conflicting-epoch"],
)
@patch("requests.get")
@patch("requests.post")
def test_scope_sync_rejects_invalid_scope_before_mutation(
    mock_post, mock_get, payload
):
    collection_response = MagicMock(status_code=200)
    collection_response.json.return_value = {
        "result": {"collections": [{"name": "goodq_text_epoch_test"}]}
    }
    mock_get.return_value = collection_response
    preflight_response = MagicMock(status_code=200)
    preflight_response.json.return_value = {
        "result": {
            "points": [{"id": "invalid-point", "payload": payload}],
            "next_page_offset": None,
        }
    }
    mock_post.return_value = preflight_response
    client = MiniAgentClient(
        profile="safe", config={"qdrant": {"host": "http://qdrant.test"}}
    )

    result = client._sync_qdrant_by_scope(
        epoch_id="epoch_test", status_val="promoted", video_hash="video-a"
    )

    assert result["status"] == "warning"
    assert result["failed_collections"] == ["goodq_text_epoch_test"]
    assert len(mock_post.call_args_list) == 1
    assert "/points/scroll" in mock_post.call_args_list[0].args[0]


@patch("requests.get")
@patch("requests.post")
def test_scope_sync_reports_unverified_payload_as_failure(mock_post, mock_get):
    collection_response = MagicMock()
    collection_response.status_code = 200
    collection_response.json.return_value = {
        "result": {"collections": [{"name": "goodq_text_epoch_test"}]}
    }
    mock_get.return_value = collection_response
    preflight_response = MagicMock(status_code=200)
    preflight_response.json.return_value = {
        "result": {
            "points": [
                {
                    "id": "point-video-a",
                    "payload": {
                        "video_hash": "video-a",
                        "epoch_id": "epoch_test",
                        "ucf_promotion_status": "staged",
                    },
                }
            ],
            "next_page_offset": None,
        }
    }
    update_response = MagicMock()
    update_response.status_code = 200
    stale_response = MagicMock()
    stale_response.status_code = 200
    stale_response.json.return_value = {
        "result": {
            "points": [
                {
                    "id": "point-video-a",
                    "payload": {
                        "video_hash": "video-a",
                        "ucf_promotion_status": "validated",
                    },
                }
            ],
            "next_page_offset": None,
        }
    }
    mock_post.side_effect = [preflight_response, update_response, stale_response]
    client = MiniAgentClient(
        profile="safe", config={"qdrant": {"host": "http://qdrant.test"}}
    )

    result = client._sync_qdrant_by_scope(
        epoch_id="epoch_test",
        status_val="promoted",
        video_hash="video-a",
    )

    assert result["status"] == "warning"
    assert result["points_verified"] == 0
    assert result["failed_collections"] == ["goodq_text_epoch_test"]


@patch("requests.get")
def test_scope_sync_fails_when_exact_epoch_collections_are_absent(mock_get):
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "result": {"collections": [{"name": "goodq_text_other_epoch_test"}]}
    }
    mock_get.return_value = response
    client = MiniAgentClient(profile="safe")

    result = client._sync_qdrant_by_scope(
        epoch_id="epoch_test", status_val="promoted", video_hash="video-a"
    )

    assert result["status"] == "error"
    assert result["reason"] == "no_epoch_collections"
    assert result["points_verified"] == 0


@patch("requests.get")
@patch("requests.post")
def test_scope_sync_requires_nonzero_readback(mock_post, mock_get):
    collection_response = MagicMock(status_code=200)
    collection_response.json.return_value = {
        "result": {"collections": [{"name": "goodq_text_epoch_test"}]}
    }
    mock_get.return_value = collection_response
    preflight_response = MagicMock(status_code=200)
    preflight_response.json.return_value = {
        "result": {
            "points": [
                {
                    "id": "point-video-a",
                    "payload": {
                        "video_hash": "video-a",
                        "epoch_id": "epoch_test",
                        "ucf_promotion_status": "staged",
                    },
                }
            ],
            "next_page_offset": None,
        }
    }
    update_response = MagicMock(status_code=200)
    empty_response = MagicMock(status_code=200)
    empty_response.json.return_value = {
        "result": {"points": [], "next_page_offset": None}
    }
    mock_post.side_effect = [preflight_response, update_response, empty_response]
    client = MiniAgentClient(profile="safe")

    result = client._sync_qdrant_by_scope(
        epoch_id="epoch_test", status_val="promoted", video_hash="video-a"
    )

    assert result["status"] == "warning"
    assert result["reason"] == "no_scoped_points_verified"
    assert result["points_verified"] == 0


def test_pending_delivery_requires_verified_qdrant_points(tmp_path, monkeypatch):
    db_path = _create_mock_db_for_test(tmp_path, promotion_status="promoted")
    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)
    conn = sqlite3.connect(str(db_path))
    client._queue_promotion_qdrant_sync(
        conn, video_hash="vh_test_001", epoch_id="epoch_test"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(
        client,
        "_sync_ucf_status_to_qdrant",
        lambda *_args, **_kwargs: {
            "status": "skipped",
            "points_attempted": 0,
            "points_verified": 0,
            "failed_collections": [],
        },
    )
    monkeypatch.setattr(
        client,
        "_sync_qdrant_by_scope",
        lambda **_kwargs: {
            "status": "ok",
            "points_verified": 0,
            "failed_collections": [],
        },
    )

    result = client._deliver_pending_promotion_qdrant_sync(
        video_hash="vh_test_001", epoch_id="epoch_test"
    )

    assert result["status"] == "pending"
    assert result["outbox"]["delivery_state"] == "pending"


def test_pending_delivery_reports_durable_cancelled_state(tmp_path, monkeypatch):
    db_path = _create_mock_db_for_test(tmp_path, promotion_status="promoted")
    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)
    conn = sqlite3.connect(str(db_path))
    client._queue_promotion_qdrant_sync(
        conn, video_hash="vh_test_001", epoch_id="epoch_test"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(
        client,
        "_sync_ucf_status_to_qdrant",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "points_attempted": 1,
            "points_verified": 1,
            "failed_collections": [],
        },
    )
    monkeypatch.setattr(
        client,
        "_sync_qdrant_by_scope",
        lambda **_kwargs: {
            "status": "ok",
            "points_verified": 1,
            "failed_collections": [],
        },
    )
    monkeypatch.setattr(
        client,
        "_record_promotion_qdrant_attempt",
        lambda **_kwargs: {"delivery_state": "cancelled", "attempt_count": 0},
    )

    result = client._deliver_pending_promotion_qdrant_sync(
        video_hash="vh_test_001", epoch_id="epoch_test"
    )

    assert result["status"] == "cancelled"
    assert result["outbox"]["delivery_state"] == "cancelled"


def test_supersede_cancels_pending_promotion_outbox(tmp_path, monkeypatch):
    db_path = _create_mock_db_for_test(tmp_path, promotion_status="promoted")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)
    monkeypatch.setattr(
        client,
        "_sync_ucf_status_to_qdrant",
        lambda *_args, **_kwargs: {"status": "ok", "failed_collections": []},
    )
    monkeypatch.setattr(
        client,
        "_sync_qdrant_by_scope",
        lambda **_kwargs: {"status": "ok", "failed_collections": []},
    )
    monkeypatch.setattr(client, "_dematerialize_active_views", lambda **_kwargs: None)
    conn = sqlite3.connect(str(db_path))
    client._queue_promotion_qdrant_sync(
        conn, video_hash="vh_test_001", epoch_id="epoch_test"
    )
    conn.commit()
    conn.close()

    result, rc = _confirm_tool_directly(
        client,
        "supersede_ucf_frames",
        {"video_hash": "vh_test_001", "epoch_id": "epoch_test"},
    )

    assert rc == 0
    assert result["output"]["superseded_count"] == 1
    outbox = client._read_promotion_qdrant_outbox(
        video_hash="vh_test_001", epoch_id="epoch_test"
    )
    assert outbox["delivery_state"] == "cancelled"


@pytest.mark.parametrize(
    ("tool_name", "source_status", "tool_args"),
    [
        (
            "reject_ucf_frames",
            "validated",
            {
                "video_hash": "vh_test_001",
                "epoch_id": "epoch_test",
                "reason": "wrong-scope fixture",
            },
        ),
        (
            "supersede_ucf_frames",
            "promoted",
            {"video_hash": "vh_test_001", "epoch_id": "epoch_test"},
        ),
    ],
)
@patch("requests.post")
def test_terminal_tools_reject_wrong_scope_row_before_mutation(
    mock_post, tmp_path, monkeypatch, tool_name, source_status, tool_args
):
    import uuid

    vector_key = f"{tool_name}-point"
    point_id = str(
        uuid.uuid5(
            uuid.UUID("2058b732-6666-5424-a820-5cf54ef071c4"), vector_key
        )
    )
    db_path = _create_mock_db_for_test(
        tmp_path,
        source_status,
        vector_key=vector_key,
        vector_collection="goodq_clip",
    )
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    preflight_response = MagicMock(status_code=200)
    preflight_response.json.return_value = {
        "result": [
            {
                "id": point_id,
                "payload": {
                    "video_hash": "another-video",
                    "epoch_id": "epoch_test",
                    "ucf_promotion_status": source_status,
                },
            }
        ]
    }
    mock_post.return_value = preflight_response
    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)
    monkeypatch.setattr(
        client,
        "_sync_qdrant_by_scope",
        lambda **_kwargs: {"status": "ok", "failed_collections": []},
    )
    monkeypatch.setattr(client, "_dematerialize_active_views", lambda **_kwargs: None)

    result, rc = _confirm_tool_directly(client, tool_name, tool_args)

    assert rc == 0
    assert result["output"]["qdrant_sync"]["status"] == "warning"
    assert len(mock_post.call_args_list) == 1
    assert mock_post.call_args_list[0].args[0].endswith("/points")


@patch("requests.post")
def test_reject_and_supersede_sync_their_status_to_qdrant(mock_post, tmp_path, monkeypatch):
    import uuid

    db_path = _create_mock_db_for_test(tmp_path, "validated", vector_key="vec-key-reject", vector_collection="goodq_clip")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    namespace = uuid.UUID("2058b732-6666-5424-a820-5cf54ef071c4")
    reject_point_id = str(uuid.uuid5(namespace, "vec-key-reject"))
    supersede_point_id = str(uuid.uuid5(namespace, "vec-key-supersede"))
    update_response = MagicMock(status_code=200)
    reject_preflight_response = MagicMock(status_code=200)
    reject_preflight_response.json.return_value = {
        "result": [
            {
                "id": reject_point_id,
                "payload": {
                    "video_hash": "vh_test_001",
                    "epoch_id": "epoch_test",
                    "ucf_promotion_status": "validated",
                },
            }
        ]
    }
    reject_verify_response = MagicMock(status_code=200)
    reject_verify_response.json.return_value = {
        "result": [
            {
                "id": reject_point_id,
                "payload": {
                    "video_hash": "vh_test_001",
                    "epoch_id": "epoch_test",
                    "ucf_promotion_status": "rejected",
                },
            }
        ]
    }
    supersede_preflight_response = MagicMock(status_code=200)
    supersede_preflight_response.json.return_value = {
        "result": [
            {
                "id": supersede_point_id,
                "payload": {
                    "video_hash": "vh_test_001",
                    "epoch_id": "epoch_test",
                    "ucf_promotion_status": "promoted",
                },
            }
        ]
    }
    supersede_verify_response = MagicMock(status_code=200)
    supersede_verify_response.json.return_value = {
        "result": [
            {
                "id": supersede_point_id,
                "payload": {
                    "video_hash": "vh_test_001",
                    "epoch_id": "epoch_test",
                    "ucf_promotion_status": "superseded",
                },
            }
        ]
    }
    mock_post.side_effect = [
        reject_preflight_response,
        update_response,
        reject_verify_response,
        supersede_preflight_response,
        update_response,
        supersede_verify_response,
    ]

    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)
    monkeypatch.setattr(
        client,
        "_sync_qdrant_by_scope",
        lambda **_: {"status": "skipped", "failed_collections": []},
    )

    res, rc = _confirm_tool_directly(client, "reject_ucf_frames", {"video_hash": "vh_test_001", "epoch_id": "epoch_test", "reason": "bad resolution"})
    assert rc == 0
    assert res["output"]["status"] == "rejected_complete"
    assert res["output"]["qdrant_sync"]["status"] == "ok"

    db_path_2 = _create_mock_db_for_test(tmp_path / "second", "promoted", vector_key="vec-key-supersede", vector_collection="goodq_clip")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path_2)

    res2, rc2 = _confirm_tool_directly(client, "supersede_ucf_frames", {"video_hash": "vh_test_001", "epoch_id": "epoch_test"})
    assert rc2 == 0
    assert res2["output"]["status"] == "superseded_complete"
    assert res2["output"]["qdrant_sync"]["status"] == "ok"

@patch("steps.common.qdrant_client.QdrantClient.set_payload")
def test_null_vector_key_frames_use_verified_scope_readback(mock_set_payload, tmp_path, monkeypatch):
    db_path = _create_mock_db_for_test(tmp_path, "validated", vector_key=None, vector_collection="goodq_clip")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))

    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)
    _allow_verified_promotion_delivery(client, monkeypatch)

    res, rc = _confirm_tool_directly(client, "promote_ucf_to_memory", {"video_hash": "vh_test_001", "epoch_id": "epoch_test"})
    assert rc == 0
    
    output = res["output"]
    q_sync = output["qdrant_sync"]
    assert q_sync["attempted"] is False
    assert q_sync["status"] == "skipped"
    assert output["scope_sync"]["points_verified"] == 1
    assert output["outbox"]["delivery_state"] == "complete"
    mock_set_payload.assert_not_called()

# Default filter tests

@patch("steps.common.qdrant_client.build_qdrant_client")
def test_qdrant_query_default_excludes_rejected_and_superseded(mock_build, monkeypatch):
    mock_client = MagicMock()
    mock_client.query.return_value = []
    mock_build.return_value = mock_client
    
    client = MiniAgentClient(profile="safe")
    args = {
        "collection": "goodq_text",
        "query_vector": [0.1] * 384,
        "top_k": 5
    }
    res, rc = client.execute_tool(tool_name="qdrant_query", tool_args=args)
    assert rc == 0
    
    mock_client.query.assert_called_once()
    _, kwargs = mock_client.query.call_args
    p_filter = kwargs["payload_filter"]
    assert "must_not" in p_filter
    must_not_keys = [item["key"] for item in p_filter["must_not"]]
    assert "rejected" in [item["match"]["value"] for item in p_filter["must_not"]]

@patch("steps.common.qdrant_client.build_qdrant_client")
def test_qdrant_query_ucf_status_filter_promoted_overrides_default(mock_build, monkeypatch):
    mock_client = MagicMock()
    mock_client.query.return_value = []
    mock_build.return_value = mock_client

    client = MiniAgentClient(profile="safe")
    args = {
        "collection": "goodq_text",
        "query_vector": [0.1] * 384,
        "top_k": 5,
        "ucf_status_filter": "promoted"
    }
    res, rc = client.execute_tool(tool_name="qdrant_query", tool_args=args)
    assert rc == 0

    mock_client.query.assert_called_once()
    _, kwargs = mock_client.query.call_args
    p_filter = kwargs["payload_filter"]
    
    assert "must" in p_filter
    must_entries = p_filter["must"]
    promoted_match = [item for item in must_entries if item["key"] == "ucf_promotion_status" and item["match"]["value"] == "promoted"]
    assert len(promoted_match) == 1
    
    if "must_not" in p_filter:
        must_not_keys = [item["key"] for item in p_filter["must_not"]]
        assert "ucf_promotion_status" not in must_not_keys

@patch("steps.common.qdrant_client.build_qdrant_client")
def test_qdrant_query_include_terminal_disables_default_exclusion(mock_build, monkeypatch):
    mock_client = MagicMock()
    mock_client.query.return_value = []
    mock_build.return_value = mock_client

    client = MiniAgentClient(profile="safe")
    args = {
        "collection": "goodq_text",
        "query_vector": [0.1] * 384,
        "top_k": 5,
        "ucf_include_terminal": True
    }
    res, rc = client.execute_tool(tool_name="qdrant_query", tool_args=args)
    assert rc == 0

    mock_client.query.assert_called_once()
    _, kwargs = mock_client.query.call_args
    p_filter = kwargs["payload_filter"]
    
    if "must" in p_filter:
        assert "ucf_promotion_status" not in [item["key"] for item in p_filter["must"]]
    if "must_not" in p_filter:
        assert "ucf_promotion_status" not in [item["key"] for item in p_filter["must_not"]]

# Filter composition and validation tests

@patch("steps.common.qdrant_client.build_qdrant_client")
def test_qdrant_query_existing_must_is_preserved(mock_build, monkeypatch):
    mock_client = MagicMock()
    mock_client.query.return_value = []
    mock_build.return_value = mock_client

    client = MiniAgentClient(profile="safe")
    existing_filter = {
        "must": [{"key": "scene_id", "match": {"value": "scene_0042"}}]
    }
    args = {
        "collection": "goodq_text",
        "query_vector": [0.1] * 384,
        "top_k": 5,
        "ucf_status_filter": "promoted",
        "payload_filter": existing_filter
    }
    res, rc = client.execute_tool(tool_name="qdrant_query", tool_args=args)
    assert rc == 0

    mock_client.query.assert_called_once()
    _, kwargs = mock_client.query.call_args
    p_filter = kwargs["payload_filter"]
    
    must_entries = p_filter["must"]
    assert len(must_entries) == 2

@patch("steps.common.qdrant_client.build_qdrant_client")
def test_qdrant_query_existing_must_not_is_preserved(mock_build, monkeypatch):
    mock_client = MagicMock()
    mock_client.query.return_value = []
    mock_build.return_value = mock_client

    client = MiniAgentClient(profile="safe")
    existing_filter = {
        "must_not": [{"key": "is_bad", "match": {"value": True}}]
    }
    args = {
        "collection": "goodq_text",
        "query_vector": [0.1] * 384,
        "top_k": 5,
        "payload_filter": existing_filter
    }
    res, rc = client.execute_tool(tool_name="qdrant_query", tool_args=args)
    assert rc == 0

    mock_client.query.assert_called_once()
    _, kwargs = mock_client.query.call_args
    p_filter = kwargs["payload_filter"]

    must_not_entries = p_filter["must_not"]
    assert len(must_not_entries) == 3

def test_qdrant_query_invalid_ucf_status_filter_returns_error():
    client = MiniAgentClient(profile="safe")
    args = {
        "collection": "goodq_text",
        "query_vector": [0.1] * 384,
        "top_k": 5,
        "ucf_status_filter": "staged"
    }
    output = client._execute_qdrant_query(args)
    assert output["status"] == "error"
    assert output["reason"] == "invalid_ucf_status_filter"

def test_qdrant_query_invalid_ucf_status_filter_validated_also_rejected():
    client = MiniAgentClient(profile="safe")
    args = {
        "collection": "goodq_text",
        "query_vector": [0.1] * 384,
        "top_k": 5,
        "ucf_status_filter": "validated"
    }
    output = client._execute_qdrant_query(args)
    assert output["status"] == "error"
    assert output["reason"] == "invalid_ucf_status_filter"

@patch("steps.common.qdrant_client.build_qdrant_client")
def test_qdrant_query_no_double_must_not_on_repeated_calls(mock_build):
    mock_client = MagicMock()
    mock_client.query.return_value = []
    mock_build.return_value = mock_client

    client = MiniAgentClient(profile="safe")
    args = {
        "collection": "goodq_text",
        "query_vector": [0.1] * 384,
        "top_k": 5,
        "payload_filter": {}
    }
    
    client._execute_qdrant_query(args)
    _, kwargs1 = mock_client.query.call_args
    assert len(kwargs1["payload_filter"]["must_not"]) == 2

    client._execute_qdrant_query(args)
    _, kwargs2 = mock_client.query.call_args
    assert len(kwargs2["payload_filter"]["must_not"]) == 2


def test_sanitize_envelope_diverse_inputs():
    """Verify that sanitize_envelope correctly sanitizes Windows, UNC, WSL, and Linux standard paths."""
    client = MiniAgentClient(profile="safe")
    
    # Windows path
    assert client.sanitize_envelope("C:\\path\\to\\a.json") == "relative/a.json"
    assert client.sanitize_envelope("D:/another/path/file.txt") == "relative/file.txt"
    
    # UNC path
    assert client.sanitize_envelope("\\\\server\\share\\b.json") == "relative/b.json"
    
    # WSL path
    assert client.sanitize_envelope("/mnt/c/c.json") == "relative/c.json"
    
    # Linux path
    assert client.sanitize_envelope("/home/d.json") == "relative/d.json"
    assert client.sanitize_envelope("/tmp/e.log") == "relative/e.log"


def test_break_glass_gate_for_file_delete(monkeypatch):
    """Verify break-glass is necessary but does not replace local confirmation."""
    # 1. Under safe profile without break-glass
    monkeypatch.delenv("GOODQ_BREAK_GLASS", raising=False)
    client_safe = MiniAgentClient(profile="safe")
    envelope, rc = client_safe.validate_action(
        prompt="Delete file",
        mode="ops",
        tool_name="file_delete",
        tool_args={"path": "some_file.json"}
    )
    assert rc == 1
    assert envelope["status"] == "error"
    assert envelope["errors"][0]["code"] == "break_glass_required"
    
    # 2. Under safe profile with break-glass override
    monkeypatch.setenv("GOODQ_BREAK_GLASS", "1")
    envelope, rc = client_safe.validate_action(
        prompt="Delete file",
        mode="ops",
        tool_name="file_delete",
        tool_args={"path": "some_file.json"}
    )
    assert rc == 3
    assert envelope["status"] == "needs_confirmation"
    assert envelope["result"]["confirmation_token"]

    # 3. Under offline profile without break-glass
    monkeypatch.delenv("GOODQ_BREAK_GLASS", raising=False)
    client_offline = MiniAgentClient(profile="offline")
    envelope, rc = client_offline.validate_action(
        prompt="Delete file",
        mode="ops",
        tool_name="file_delete",
        tool_args={"path": "some_file.json"}
    )
    assert rc == 1
    assert envelope["status"] == "error"
    assert envelope["errors"][0]["code"] in ("offline_blocked", "break_glass_required")


def test_offline_profile_denies_mutating_operations():
    """Verify that offline profile denies mutating operations in MUTATING_DENY_ON_AGENT_FAILURE."""
    from agents.mini_agent_client import MUTATING_DENY_ON_AGENT_FAILURE
    client = MiniAgentClient(profile="offline")
    
    for tool in MUTATING_DENY_ON_AGENT_FAILURE:
        envelope, rc = client.validate_action(
            prompt=f"Run mutating tool {tool}",
            mode="ops",
            tool_name=tool,
            tool_args={"path": "dummy"}
        )
        assert rc == 1, f"Mutating tool {tool} was not blocked under offline profile!"
        assert envelope["status"] == "error"
        assert envelope["errors"][0]["code"] == "offline_blocked"


_DIGEST_A = "a" * 64
_DIGEST_B = "b" * 64
_CREATE_COLLECTION_SCOPE = {
    "action_id": "action_1234abcd",
    "epoch_id": "epoch_2026_07_12_test",
    "payload_sha256": _DIGEST_A,
}
_DELETE_COLLECTION_SCOPE = {
    "job_id": "job_1234abcd",
    "epoch_id": "epoch_2026_07_12_test",
    "collection_id": "col_20260712_120000_deadbeef",
    "expected_record_sha256": _DIGEST_B,
}


@pytest.mark.parametrize(
    ("operation", "scope"),
    [
        ("create_summary_collection", _CREATE_COLLECTION_SCOPE),
        ("delete_summary_collection", _DELETE_COLLECTION_SCOPE),
    ],
)
def test_summary_collection_actions_accept_only_exact_privacy_safe_scope(
    operation,
    scope,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(tmp_path / operation))
    client = MiniAgentClient(profile="safe")
    client.agent_available = True

    envelope, rc = client.authorize_action(
        prompt="Prepare one exact summary collection action",
        mode="ops",
        tool_name=operation,
        tool_args=dict(scope),
    )

    assert rc == 3
    assert envelope["status"] == "needs_confirmation"
    assert envelope["result"]["confirmation_token"]
    token_store = json.loads(
        (tmp_path / operation / "confirmation_tokens.json").read_text(
            encoding="utf-8"
        )
    )
    stored = next(iter(token_store.values()))
    assert stored["tool_args"] == scope


@pytest.mark.parametrize(
    ("operation", "invalid_scope"),
    [
        ("create_summary_collection", []),
        ("create_summary_collection", {}),
        (
            "create_summary_collection",
            {"action_id": "action_1234abcd", "epoch_id": "epoch_test"},
        ),
        (
            "create_summary_collection",
            {**_CREATE_COLLECTION_SCOPE, "raw_payload": "private transcript"},
        ),
        (
            "create_summary_collection",
            {**_CREATE_COLLECTION_SCOPE, 7: "non-string field name"},
        ),
        (
            "create_summary_collection",
            {**_CREATE_COLLECTION_SCOPE, "action_id": " ../action "},
        ),
        (
            "create_summary_collection",
            {**_CREATE_COLLECTION_SCOPE, "epoch_id": "epoch/test"},
        ),
        (
            "create_summary_collection",
            {**_CREATE_COLLECTION_SCOPE, "action_id": "a" * 103},
        ),
        (
            "create_summary_collection",
            {**_CREATE_COLLECTION_SCOPE, "epoch_id": "e" * 129},
        ),
        (
            "create_summary_collection",
            {**_CREATE_COLLECTION_SCOPE, "payload_sha256": "A" * 64},
        ),
        (
            "create_summary_collection",
            {**_CREATE_COLLECTION_SCOPE, "payload_sha256": "a" * 63},
        ),
        ("delete_summary_collection", []),
        ("delete_summary_collection", {}),
        (
            "delete_summary_collection",
            {
                "job_id": "job_1234abcd",
                "epoch_id": "epoch_test",
                "collection_id": "col_one",
            },
        ),
        (
            "delete_summary_collection",
            {**_DELETE_COLLECTION_SCOPE, "confirmation_token": "secret"},
        ),
        (
            "delete_summary_collection",
            {**_DELETE_COLLECTION_SCOPE, "job_id": "job\\one"},
        ),
        (
            "delete_summary_collection",
            {**_DELETE_COLLECTION_SCOPE, "job_id": "j" * 103},
        ),
        (
            "delete_summary_collection",
            {**_DELETE_COLLECTION_SCOPE, "collection_id": "../collection"},
        ),
        (
            "delete_summary_collection",
            {**_DELETE_COLLECTION_SCOPE, "collection_id": 7},
        ),
        (
            "delete_summary_collection",
            {**_DELETE_COLLECTION_SCOPE, "expected_record_sha256": "g" * 64},
        ),
        (
            "delete_summary_collection",
            {**_DELETE_COLLECTION_SCOPE, "expected_record_sha256": "b" * 65},
        ),
    ],
)
def test_summary_collection_actions_reject_invalid_scope_before_token_issue(
    operation,
    invalid_scope,
    tmp_path,
    monkeypatch,
):
    agent_home = tmp_path / f"invalid-{operation}"
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(agent_home))
    client = MiniAgentClient(profile="safe")
    client.agent_available = True

    envelope, rc = client.authorize_action(
        prompt="Reject invalid summary collection scope",
        mode="ops",
        tool_name=operation,
        tool_args=invalid_scope,
    )

    assert rc == 1
    assert envelope["errors"][0]["code"] == "invalid_tool_arguments"
    assert not (agent_home / "confirmation_tokens.json").exists()
    audit_path = Path(os.environ["GOODQ_TOOL_AUDIT_LOG"])
    rows = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
    ]
    assert rows[-1]["arguments"] == {"scope_valid": False}
    serialized = audit_path.read_text(encoding="utf-8")
    assert "private transcript" not in serialized
    assert "confirmation_token" not in serialized
    assert "raw_payload" not in serialized


@pytest.mark.parametrize(
    ("operation", "scope", "changed_scope"),
    [
        (
            "create_summary_collection",
            _CREATE_COLLECTION_SCOPE,
            {**_CREATE_COLLECTION_SCOPE, "payload_sha256": _DIGEST_B},
        ),
        (
            "delete_summary_collection",
            _DELETE_COLLECTION_SCOPE,
            {**_DELETE_COLLECTION_SCOPE, "collection_id": "col_changed"},
        ),
    ],
)
def test_summary_collection_action_tokens_are_scope_bound_and_single_use(
    operation,
    scope,
    changed_scope,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(tmp_path / operation))
    client = MiniAgentClient(profile="safe")
    client.agent_available = True
    requested, requested_rc = client.authorize_action(
        prompt="Prepare exact summary collection action",
        mode="ops",
        tool_name=operation,
        tool_args=dict(scope),
    )
    assert requested_rc == 3
    token = requested["result"]["confirmation_token"]

    mismatched, mismatch_rc = client.authorize_action(
        prompt="Reject changed summary collection scope",
        mode="ops",
        tool_name=operation,
        tool_args=changed_scope,
        confirm=True,
        confirmation_token=token,
    )
    assert mismatch_rc == 1
    assert mismatched["errors"][0]["code"] == "token_scope_mismatch"

    confirmed, confirmed_rc = client.authorize_action(
        prompt="Confirm exact summary collection scope",
        mode="ops",
        tool_name=operation,
        tool_args=dict(scope),
        confirm=True,
        confirmation_token=token,
    )
    assert confirmed_rc == 0
    assert confirmed["status"] == "ok"

    reused, reused_rc = client.authorize_action(
        prompt="Reject reused summary collection token",
        mode="ops",
        tool_name=operation,
        tool_args=dict(scope),
        confirm=True,
        confirmation_token=token,
    )
    assert reused_rc == 1
    assert reused["errors"][0]["code"] == "token_already_used"


@pytest.mark.parametrize(
    ("operation", "scope"),
    [
        ("create_summary_collection", _CREATE_COLLECTION_SCOPE),
        ("delete_summary_collection", _DELETE_COLLECTION_SCOPE),
    ],
)
def test_summary_collection_actions_reject_invalid_scope_before_token_claim(
    operation,
    scope,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(tmp_path / operation))
    client = MiniAgentClient(profile="safe")
    client.agent_available = True
    requested, requested_rc = client.authorize_action(
        prompt="Prepare summary collection action",
        mode="ops",
        tool_name=operation,
        tool_args=dict(scope),
    )
    assert requested_rc == 3
    claim = MagicMock(side_effect=AssertionError("invalid scope reached claim"))
    monkeypatch.setattr(client, "_claim_confirmation_token", claim)

    envelope, rc = client.authorize_action(
        prompt="Reject invalid claim scope",
        mode="ops",
        tool_name=operation,
        tool_args={**scope, "raw_payload": "private transcript"},
        confirm=True,
        confirmation_token=requested["result"]["confirmation_token"],
    )

    assert rc == 1
    assert envelope["errors"][0]["code"] == "invalid_tool_arguments"
    claim.assert_not_called()


@pytest.mark.parametrize(
    ("operation", "scope"),
    [
        ("create_summary_collection", _CREATE_COLLECTION_SCOPE),
        ("delete_summary_collection", _DELETE_COLLECTION_SCOPE),
    ],
)
def test_summary_collection_action_tokens_expire(
    operation,
    scope,
    tmp_path,
    monkeypatch,
):
    agent_home = tmp_path / operation
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(agent_home))
    client = MiniAgentClient(profile="safe")
    client.agent_available = True
    requested, requested_rc = client.authorize_action(
        prompt="Prepare expiring collection action",
        mode="ops",
        tool_name=operation,
        tool_args=dict(scope),
    )
    assert requested_rc == 3
    token = requested["result"]["confirmation_token"]
    token_store = agent_home / "confirmation_tokens.json"
    tokens = json.loads(token_store.read_text(encoding="utf-8"))
    tokens[token]["timestamp"] = "2020-01-01T00:00:00"
    token_store.write_text(json.dumps(tokens), encoding="utf-8")

    envelope, rc = client.authorize_action(
        prompt="Reject expired collection action",
        mode="ops",
        tool_name=operation,
        tool_args=dict(scope),
        confirm=True,
        confirmation_token=token,
    )

    assert rc == 1
    assert envelope["errors"][0]["code"] == "token_expired"


@pytest.mark.parametrize(
    ("operation", "scope"),
    [
        ("create_summary_collection", _CREATE_COLLECTION_SCOPE),
        ("delete_summary_collection", _DELETE_COLLECTION_SCOPE),
    ],
)
def test_summary_collection_action_claim_is_atomic_across_clients(
    operation,
    scope,
    tmp_path,
    monkeypatch,
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(tmp_path / operation))
    first = MiniAgentClient(profile="safe")
    second = MiniAgentClient(profile="safe")
    first.agent_available = True
    second.agent_available = True
    requested, requested_rc = first.authorize_action(
        prompt="Prepare atomic collection claim",
        mode="ops",
        tool_name=operation,
        tool_args=dict(scope),
    )
    assert requested_rc == 3
    token = requested["result"]["confirmation_token"]
    barrier = Barrier(2)

    def claim(client):
        barrier.wait(timeout=10)
        return client.authorize_action(
            prompt="Claim atomic collection authority",
            mode="ops",
            tool_name=operation,
            tool_args=dict(scope),
            confirm=True,
            confirmation_token=token,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(claim, (first, second)))

    assert sorted(rc for _envelope, rc in results) == [0, 1]
    rejected = next(envelope for envelope, rc in results if rc == 1)
    assert rejected["errors"][0]["code"] == "token_already_used"


@pytest.mark.parametrize(
    ("operation", "scope"),
    [
        ("create_summary_collection", _CREATE_COLLECTION_SCOPE),
        ("delete_summary_collection", _DELETE_COLLECTION_SCOPE),
    ],
)
def test_summary_collection_actions_are_denied_offline_without_token(
    operation,
    scope,
    tmp_path,
    monkeypatch,
):
    agent_home = tmp_path / operation
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(agent_home))
    client = MiniAgentClient(profile="offline")
    client.agent_available = True

    envelope, rc = client.authorize_action(
        prompt="Reject offline summary collection mutation",
        mode="ops",
        tool_name=operation,
        tool_args=dict(scope),
    )

    assert rc == 1
    assert envelope["errors"][0]["code"] == "offline_blocked"
    assert not (agent_home / "confirmation_tokens.json").exists()

