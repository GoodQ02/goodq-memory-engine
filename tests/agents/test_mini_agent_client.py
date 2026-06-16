import pytest
import os
from unittest.mock import MagicMock, patch
from pathlib import Path
from agents.mini_agent_client import MiniAgentClient
import goodq_mini_agent.paths

def test_assets_dir_monkeypatch():
    """Verify that ASSETS_DIR was successfully redirected to our local folder."""
    expected_path = Path(__file__).resolve().parent.parent.parent / "agents" / "stack"
    assert goodq_mini_agent.paths.ASSETS_DIR.resolve() == expected_path.resolve()

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
    # Promoted frames are not in IN('staged','validated'), so 0 rows updated
    assert result["output"]["rejected_count"] == 0

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
    """Phase 0.8: every HITL-gated native tool must appear in all 6 required locations.

    This test is the single source of truth for the tool registration contract.
    If a new HITL-gated tool is added without being registered in all locations,
    this test will fail immediately on the first run.

    Required locations:
    1. MUTATING_DENY_ON_AGENT_FAILURE (module-level set)
    2. Local NATIVELY_GATED_TOOLS in validate_action() (line ~454)
    3. HITL gate 'if tool_name in (...)' in validate_action() (line ~561)
    4. Native bypass list in validate_action() (line ~596)
    5. Dispatch 'elif tool_name ==' chain in execute_tool()
    6. side_effect_report.mutated set in execute_tool()
    """
    import inspect
    import re
    from agents.mini_agent_client import MUTATING_DENY_ON_AGENT_FAILURE

    # The canonical set of HITL-gated native tools. Update this list when
    # adding a new HITL-gated tool — the test will enforce all registrations.
    HITL_GATED_TOOLS = {
        "promote_ucf_to_memory",
        "validate_ucf_frames",
        "reject_ucf_frames",
        "supersede_ucf_frames",
    }

    # 1. All HITL tools must be in the module-level MUTATING set
    for tool in HITL_GATED_TOOLS:
        assert tool in MUTATING_DENY_ON_AGENT_FAILURE, (
            f"HITL tool '{tool}' missing from MUTATING_DENY_ON_AGENT_FAILURE"
        )

    # Inspect source for the remaining 5 locations
    source = inspect.getsource(MiniAgentClient)

    for tool in HITL_GATED_TOOLS:
        # 2. Local NATIVELY_GATED_TOOLS in validate_action
        assert f'"{tool}"' in source or f"'{tool}'" in source, (
            f"HITL tool '{tool}' not found in MiniAgentClient source"
        )

        # 3. HITL gate presence — look for tool in the HITL 'if tool_name in' block
        hitl_gate_match = re.search(
            r'# 4\. Human-in-the-Loop.*?if tool_name in \(([^)]+)\)',
            source, re.DOTALL
        )
        assert hitl_gate_match, "HITL gate block not found in MiniAgentClient"
        hitl_tools_str = hitl_gate_match.group(1)
        assert tool in hitl_tools_str, (
            f"HITL tool '{tool}' missing from HITL gate in validate_action()"
        )

        # 4. Native bypass list
        bypass_match = re.search(
            r'# 5\. Native tool validation bypass.*?if tool_name in \(([^)]+)\)',
            source, re.DOTALL
        )
        assert bypass_match, "Native bypass list not found in MiniAgentClient"
        bypass_tools_str = bypass_match.group(1)
        assert tool in bypass_tools_str, (
            f"HITL tool '{tool}' missing from native bypass list"
        )

        # 5. Dispatch chain — each tool must have an elif branch
        assert f'tool_name == "{tool}"' in source or f"tool_name == '{tool}'" in source, (
            f"HITL tool '{tool}' missing from dispatch elif chain in execute_tool()"
        )

        # 6. side_effect_report.mutated
        mutated_match = re.search(
            r'"mutated":\s*tool_name\s+in\s+\(([^)]+)\)',
            source, re.DOTALL
        )
        assert mutated_match, "side_effect_report.mutated set not found in MiniAgentClient"
        mutated_tools_str = mutated_match.group(1)
        assert tool in mutated_tools_str, (
            f"HITL tool '{tool}' missing from side_effect_report.mutated"
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
        "validate_ucf_frames",
        "reject_ucf_frames",
        "supersede_ucf_frames"
    }
    
    for tool in expected_mutating:
        assert tool in mutating_tools, f"Expected mutating tool '{tool}' not found in MUTATING_DENY_ON_AGENT_FAILURE matrix"
        
    # Slice out NATIVELY_GATED_TOOLS set
    start_str_native = "NATIVELY_GATED_TOOLS = {"
    idx_start_native = src.find(start_str_native)
    assert idx_start_native != -1, "NATIVELY_GATED_TOOLS not found in source code"
    idx_end_native = src.find("}", idx_start_native)
    assert idx_end_native != -1, "Closing bracket for NATIVELY_GATED_TOOLS not found"
    
    native_slice = src[idx_start_native + len(start_str_native):idx_end_native]
    native_gated_tools = set(re.findall(r'["\']([^"\']+)["\']', native_slice))
    
    expected_native_gated = {
        "promote_ucf_to_memory",
        "validate_ucf_frames",
        "reject_ucf_frames",
        "supersede_ucf_frames"
    }
    
    assert native_gated_tools == expected_native_gated, f"NATIVELY_GATED_TOOLS set mismatch: {native_gated_tools}"


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
    db_path = _create_mock_db_for_test(tmp_path, "validated", vector_key="vec-key-1", vector_collection="goodq_clip")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": {"collections": []}}
    mock_post.return_value = mock_resp

    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)

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
def test_promote_qdrant_sync_nonfatal_and_envelope_carries_warning(mock_post, tmp_path, monkeypatch):
    db_path = _create_mock_db_for_test(tmp_path, "validated", vector_key="vec-key-1", vector_collection="goodq_clip")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.text = '{"error": "not found"}'
    mock_resp.json.return_value = {"result": {"collections": []}}
    mock_post.return_value = mock_resp

    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)

    res, rc = _confirm_tool_directly(client, "promote_ucf_to_memory", {"video_hash": "vh_test_001", "epoch_id": "epoch_test"})
    assert rc == 0
    assert res["status"] == "success"
    
    output = res["output"]
    assert output["status"] == "promoted_complete"
    
    q_sync = output["qdrant_sync"]
    assert q_sync["attempted"] is True
    assert q_sync["status"] == "warning"
    assert "warnings" in res
    assert "qdrant_payload_sync_failed" in res["warnings"]

@patch("requests.post")
def test_reject_and_supersede_sync_their_status_to_qdrant(mock_post, tmp_path, monkeypatch):
    db_path = _create_mock_db_for_test(tmp_path, "validated", vector_key="vec-key-reject", vector_collection="goodq_clip")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": {"collections": []}}
    mock_post.return_value = mock_resp

    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)

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
def test_null_vector_key_frames_skipped_and_qdrant_sync_is_skipped(mock_set_payload, tmp_path, monkeypatch):
    db_path = _create_mock_db_for_test(tmp_path, "validated", vector_key=None, vector_collection="goodq_clip")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))

    client = MiniAgentClient(profile="safe")
    monkeypatch.setattr(client, "_get_ucf_db_path", lambda: db_path)

    res, rc = _confirm_tool_directly(client, "promote_ucf_to_memory", {"video_hash": "vh_test_001", "epoch_id": "epoch_test"})
    assert rc == 0
    
    q_sync = res["output"]["qdrant_sync"]
    assert q_sync["attempted"] is False
    assert q_sync["status"] == "skipped"
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
