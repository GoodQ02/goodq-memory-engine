from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cli import run_ingestion


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_control_agent_activation_defaults_off(monkeypatch):
    monkeypatch.delenv("GOODQ_CONTROL_AGENT_ENABLED", raising=False)

    assert run_ingestion._control_agent_activation_requested(
        {}, cli_enabled=False
    ) is False
    assert run_ingestion._control_agent_activation_requested(
        {"control_agent": {"enabled": False}}, cli_enabled=False
    ) is False
    assert run_ingestion._control_agent_activation_requested(
        {"control_agent": {"enabled": "true"}}, cli_enabled=object()
    ) is False


@pytest.mark.parametrize(
    ("config", "cli_enabled", "env_enabled"),
    [
        ({}, True, False),
        ({"control_agent": {"enabled": True}}, False, False),
        ({}, False, True),
    ],
)
def test_control_agent_activation_requires_one_explicit_source(
    config,
    cli_enabled,
    env_enabled,
    monkeypatch,
):
    if env_enabled:
        monkeypatch.setenv("GOODQ_CONTROL_AGENT_ENABLED", "1")
    else:
        monkeypatch.delenv("GOODQ_CONTROL_AGENT_ENABLED", raising=False)

    assert run_ingestion._control_agent_activation_requested(
        config,
        cli_enabled=cli_enabled,
    ) is True


@pytest.mark.parametrize(
    ("activation_requested", "auto_healing_requested", "dry_run", "expected"),
    [
        (False, False, True, False),
        (False, True, False, False),
        (True, False, False, False),
        (True, True, True, False),
        (True, True, False, True),
    ],
)
def test_control_agent_mutation_requires_all_three_explicit_gates(
    activation_requested,
    auto_healing_requested,
    dry_run,
    expected,
):
    assert run_ingestion._control_agent_mutation_requested(
        activation_requested=activation_requested,
        auto_healing_requested=auto_healing_requested,
        dry_run=dry_run,
    ) is expected


def test_non_boolean_option_wrappers_are_not_explicit_mutation_approval():
    assert run_ingestion._control_agent_mutation_requested(
        activation_requested=True,
        auto_healing_requested=object(),
        dry_run=False,
    ) is False


def test_runtime_gate_does_not_build_llm_when_default_disabled(monkeypatch):
    monkeypatch.delenv("GOODQ_CONTROL_AGENT_ENABLED", raising=False)
    monkeypatch.setattr(run_ingestion, "CONTROL_AGENT_AVAILABLE", True)
    monkeypatch.setattr(run_ingestion, "_GLOBAL_LLM_CLIENT", None)
    monkeypatch.setattr(run_ingestion, "_CURRENT_RUN_CONTEXT", None)

    import steps.common.config_loader as config_loader
    import steps.common.llm_model_factory as llm_model_factory

    build_models = MagicMock(return_value={"local": object()})
    monkeypatch.setattr(
        config_loader,
        "load_configs",
        lambda *_args, **_kwargs: {"control_agent": {"enabled": False}},
    )
    monkeypatch.setattr(llm_model_factory, "build_llm_models", build_models)

    assert run_ingestion._control_agent_runtime_enabled() is False
    build_models.assert_not_called()
    assert run_ingestion._GLOBAL_LLM_CLIENT is None


def test_cached_llm_does_not_bypass_default_disabled_gate(monkeypatch):
    monkeypatch.delenv("GOODQ_CONTROL_AGENT_ENABLED", raising=False)
    monkeypatch.setattr(run_ingestion, "CONTROL_AGENT_AVAILABLE", True)
    cached_client = object()
    monkeypatch.setattr(run_ingestion, "_GLOBAL_LLM_CLIENT", cached_client)
    monkeypatch.setattr(run_ingestion, "_CURRENT_RUN_CONTEXT", None)

    import steps.common.config_loader as config_loader

    monkeypatch.setattr(
        config_loader,
        "load_configs",
        lambda *_args, **_kwargs: {"control_agent": {"enabled": False}},
    )

    assert run_ingestion._control_agent_runtime_enabled() is False
    assert run_ingestion._GLOBAL_LLM_CLIENT is cached_client


def test_control_agent_constructor_defaults_diagnostic_only(monkeypatch):
    captured = {}

    class FakeControlAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(run_ingestion, "ControlAgent", FakeControlAgent)
    monkeypatch.setattr(run_ingestion, "_GLOBAL_LLM_CLIENT", object())
    monkeypatch.setattr(run_ingestion, "ENABLE_AUTO_HEALING", False)

    run_ingestion._get_control_agent()

    assert captured["dry_run"] is True
    assert captured["enable_mutation"] is False


def test_control_agent_constructor_requires_explicit_non_dry_mutation(
    monkeypatch,
    tmp_path,
):
    captured = {}

    class FakeControlAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    cfg_path = tmp_path / "resolved.json"
    cfg_path.write_text(
        json.dumps({"control_agent": {"dry_run": False}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_ingestion, "ControlAgent", FakeControlAgent)
    monkeypatch.setattr(run_ingestion, "_GLOBAL_LLM_CLIENT", object())
    monkeypatch.setattr(run_ingestion, "ENABLE_AUTO_HEALING", True)

    run_ingestion._get_control_agent(cfg_path)

    assert captured["dry_run"] is False
    assert captured["enable_mutation"] is True


def test_canonical_control_doc_keeps_governor_preflight_only():
    text = (REPO_ROOT / "docs" / "agent" / "CONTROL_AGENT.md").read_text(
        encoding="utf-8"
    )

    assert "governor MCP is a separate preflight-only advisor" in text
    assert "it does not execute tools" in text
    assert "or substitute for MiniAgent approval/audit evidence" in text
