"""Behavior contracts for the Dev On/Off operator dashboard."""

from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _dashboard(*args: str) -> str:
    completed = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(REPO_ROOT / "scripts" / "dev_mode_dashboard.ps1"),
            *args,
            "-NoColor",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
    )
    return completed.stdout


def test_start_renders_the_fixed_build_mode_signal_path():
    output = _dashboard("-Mode", "dev-on", "-Event", "start")

    assert "DEV ON / BUILD MODE" in output
    assert "[CONFIG]" in output
    assert "[WSL AUDIO]" in output
    assert "[vLLM]" in output
    assert "[QDRANT]" in output
    assert "[API]" in output


def test_blocked_node_names_the_node_and_actionable_reason():
    output = _dashboard(
        "-Mode",
        "dev-on",
        "-Event",
        "node",
        "-Node",
        "vLLM",
        "-State",
        "blocked",
        "-Message",
        "endpoint did not respond",
    )

    assert "[BLOCKED] vLLM" in output
    assert "endpoint did not respond" in output


def test_dev_off_final_calls_out_retained_qdrant():
    output = _dashboard(
        "-Mode",
        "dev-off",
        "-Event",
        "final",
        "-State",
        "ready",
        "-Message",
        "Qdrant retained on loopback",
    )

    assert "OPEN DESKTOP — GPU SERVICES RELEASED" in output
    assert "Qdrant retained on loopback" in output
