"""Regression coverage for the public CI reproducibility boundary."""

from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
MINI_AGENT_RELEASE = (
    "goodq-mini-agent @ https://github.com/GoodQ02/goodq-mini-agent/releases/"
    "download/v0.1.1/goodq_mini_agent-0.1.1-py3-none-any.whl"
    "#sha256=0f73ea4a3ee3b934c6d77c89c2810edcd6ceab1a13a5534bb59b54afe3f4506e"
)


def test_ci_creates_the_declared_baseline_lock_environment() -> None:
    """Public CI must execute the frozen baseline it documents as reproducible."""
    workflow = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    setup_steps = workflow["jobs"]["bootstrap-baseline"]["steps"]
    setup_miniconda = next(step for step in setup_steps if step.get("name") == "Setup Miniconda")

    assert setup_miniconda["with"]["environment-file"] == "environment-baseline-lock.yml"

    receipt = next(step for step in setup_steps if step.get("name") == "Runtime version receipt")
    assert "fastapi" in receipt["run"]
    assert "pydantic" in receipt["run"]
    assert "goodq-mini-agent" in receipt["run"]
    assert "pip check" in receipt["run"]


def test_ci_lock_pins_the_public_mini_agent_release() -> None:
    """Staging tests must use the same audited policy package as production CI."""
    environment = (REPO_ROOT / "environment-baseline-lock.yml").read_text(encoding="utf-8")
    requirements = (REPO_ROOT / "requirements-baseline-lock.txt").read_text(encoding="utf-8")

    assert MINI_AGENT_RELEASE in environment
    assert MINI_AGENT_RELEASE in requirements


def test_ci_runs_native_lifecycle_separately_without_dropping_coverage() -> None:
    workflow = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    steps = workflow["jobs"]["bootstrap-baseline"]["steps"]
    native = next(step for step in steps if step.get("name") == "Windows startup lifecycle tests")
    unit = next(step for step in steps if step.get("name") == "Unit test suite")
    gate = next(step for step in steps if step.get("name") == "Installer semantic compatibility")
    assert steps.index(gate) < steps.index(native) < steps.index(unit)
    assert "pytest tests/unit/test_dev_startup.py" in native["run"]
    assert "--ignore=tests/unit/test_dev_startup.py" in unit["run"]
    assert not native.get("continue-on-error") and not native.get("if")