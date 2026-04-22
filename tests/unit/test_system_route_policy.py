from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path


def _load_route_module(module_name: str):
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    module_path = repo_root / "api" / "routes" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"tests.{module_name}_route_policy", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


system_module = _load_route_module("system")


def test_ingest_route_declares_guarded_future_facade() -> None:
    request = system_module.IngestRequest(file_path="C:/tmp/example.mp4")

    response = asyncio.run(system_module.start_ingest(request))

    assert response.status == "disabled"
    assert response.allowed is False
    assert response.route == "/api/system/ingest"
    assert response.mode == "future_controlled_facade"
    assert response.job_id == "disabled"
    assert response.policy.confirmation_gated is True
    assert response.policy.policy_driven is True
    assert response.policy.budgeted is True
    assert response.policy.checkpointed is True
    assert response.policy.auditable is True
    assert "cli.watchdog" in response.canonical_runtime_path
    assert any("cli.watchdog" in item for item in response.operator_surfaces)
    assert any("cli.run_ingestion" in item for item in response.operator_surfaces)
    assert any("import_inbox" in item for item in response.operator_surfaces)
    assert any("confirmation token" in item for item in response.required_capabilities)
    assert any("checkpointed" in item for item in response.required_capabilities)


def test_reindex_route_declares_operator_only_policy() -> None:
    response = asyncio.run(system_module.rebuild_indexes())

    assert response.status == "disabled"
    assert response.allowed is False
    assert response.route == "/api/system/reindex"
    assert response.mode == "operator_only"
    assert "operator-only" in response.message
    assert "No supported public API facade exists" in response.canonical_runtime_path
    assert response.policy.explicit is True
    assert response.policy.confirmation_gated is True
    assert response.policy.policy_driven is True
    assert any("maintenance workflow" in item for item in response.operator_surfaces)
    assert any("maintenance" in item for item in response.required_capabilities)


def test_reload_route_declares_operator_only_policy() -> None:
    response = asyncio.run(system_module.reload_config())

    assert response.status == "disabled"
    assert response.allowed is False
    assert response.route == "/api/system/reload"
    assert response.mode == "operator_only"
    assert "operator-only" in response.message
    assert "No supported public API facade exists" in response.canonical_runtime_path
    assert response.policy.explicit is True
    assert response.policy.auditable is True
    assert any("maintenance workflow" in item for item in response.operator_surfaces)
    assert any("maintenance" in item for item in response.required_capabilities)
