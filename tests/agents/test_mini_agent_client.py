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

