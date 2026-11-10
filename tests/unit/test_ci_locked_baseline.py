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


def test_ci_visual_runtime_matches_the_installer_cpu_torch_pins() -> None:
    """The actual CI environment must support the pinned CLIP model's bin weights."""
    workflow = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    setup = next(
        step
        for step in workflow["jobs"]["bootstrap-baseline"]["steps"]
        if step.get("name") == "Setup Miniconda"
    )
    environment = yaml.safe_load(
        (REPO_ROOT / setup["with"]["environment-file"]).read_text(encoding="utf-8")
    )
    dependencies = environment["dependencies"]
    pip_requirements = set(next(item["pip"] for item in dependencies if isinstance(item, dict)))
    installer_requirements = set(
        (REPO_ROOT / "requirements-baseline-lock.txt").read_text(encoding="utf-8").splitlines()
    )
    cpu_torch_requirements = {
        "--extra-index-url https://download.pytorch.org/whl/cpu",
        "torch==2.6.0+cpu",
        "torchvision==0.21.0+cpu",
        "torchaudio==2.6.0+cpu",
    }

    assert cpu_torch_requirements <= installer_requirements
    assert cpu_torch_requirements <= pip_requirements, (
        "CI must install the same native-loader-compatible CPU Torch family as the installer"
    )
    assert not any(
        isinstance(item, str)
        and item.split("=", 1)[0] in {"pytorch", "torchvision", "torchaudio", "cpuonly"}
        for item in dependencies
    ), "Do not combine the old Conda Torch family with the supported pip CPU wheels"


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