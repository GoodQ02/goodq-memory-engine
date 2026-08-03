"""Regression coverage for the public CI reproducibility boundary."""

from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_ci_creates_the_declared_baseline_lock_environment() -> None:
    """Public CI must execute the frozen baseline it documents as reproducible."""
    workflow = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    setup_steps = workflow["jobs"]["bootstrap-baseline"]["steps"]
    setup_miniconda = next(step for step in setup_steps if step.get("name") == "Setup Miniconda")

    assert setup_miniconda["with"]["environment-file"] == "environment-baseline-lock.yml"

    receipt = next(step for step in setup_steps if step.get("name") == "Runtime version receipt")
    assert "fastapi" in receipt["run"]
    assert "pydantic" in receipt["run"]
    assert "pip check" in receipt["run"]
