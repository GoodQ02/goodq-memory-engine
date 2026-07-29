from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Prevent OpenMP duplicate initialization crash on Windows when running full suite
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

REPO_ROOT = Path(__file__).resolve().parents[1]
repo_root_str = str(REPO_ROOT)
if repo_root_str not in sys.path:
    sys.path.insert(0, repo_root_str)


def pytest_addoption(parser):
    group = parser.getgroup("goodq-runtime")
    group.addoption(
        "--goodq-test-profile",
        choices=("isolated", "live", "golden"),
        default=os.environ.get("GOODQ_TEST_PROFILE", "isolated"),
        help=(
            "Runtime evidence profile. isolated never probes required services; "
            "live and golden fail when required evidence is unavailable."
        ),
    )


def pytest_collection_modifyitems(config, items):
    """Keep isolated runs from entering any test that requires live services."""
    if config.getoption("--goodq-test-profile") != "isolated":
        return
    isolated_skip = pytest.mark.skip(
        reason="live_runtime test is disabled by the isolated GoodQ test profile"
    )
    for item in items:
        if "live_runtime" in item.keywords:
            item.add_marker(isolated_skip)


@pytest.fixture(scope="session")
def goodq_test_profile(request):
    return request.config.getoption("--goodq-test-profile")


@pytest.fixture(autouse=True)
def isolate_goodq_agent_state(tmp_path, monkeypatch):
    """Keep MiniAgent tokens/audits out of operator-owned repository paths."""
    monkeypatch.setenv(
        "GOODQ_MINI_AGENT_HOME",
        str(tmp_path / "goodq-mini-agent"),
    )
    monkeypatch.setenv(
        "GOODQ_TOOL_AUDIT_LOG",
        str(tmp_path / "goodq-tool-audit" / "tool-audit.jsonl"),
    )


@pytest.fixture(autouse=True)
def isolate_goodq_identity_state(tmp_path, monkeypatch):
    """Keep identity path from touching operator-owned filesystem paths."""
    monkeypatch.setenv(
        "GOODQ_IDENTITY_PATH",
        str(tmp_path / "goodq-identity"),
    )
