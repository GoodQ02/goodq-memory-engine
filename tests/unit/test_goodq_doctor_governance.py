from __future__ import annotations

import json
import shutil
import socket
import subprocess
from pathlib import Path

import pytest

from cli import goodq_doctor as doctor


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def governance_repo(tmp_path: Path) -> Path:
    """Copy the real producer's frozen projections, without invoking capture."""
    paths = [
        "docs/SYSTEM_SNAPSHOT.md",
        "docs/AGENT_CAPABILITIES.md",
        "docs/goodq4all_agent_status.md",
        "docs/agent/current_state.json",
        "docs/agent/CURRENT_STATE.md",
        "docs/GOODQ_RAG_CONTEXT_PACK.md",
    ]
    projected = json.loads((REPO_ROOT / paths[3]).read_text(encoding="utf-8"))
    paths.append(projected["generated_from"])
    for relative in paths:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / relative, destination)
    return tmp_path


def _snapshot_path(root: Path) -> Path:
    return root / "docs/agent/current_state.json"


def _read_snapshot(root: Path) -> dict:
    return json.loads(_snapshot_path(root).read_text(encoding="utf-8"))


def _write_snapshot(root: Path, value: object) -> None:
    _snapshot_path(root).write_text(json.dumps(value), encoding="utf-8")


def test_governance_accepts_current_evidence_despite_retired_status_redirect(governance_repo):
    expected = _read_snapshot(governance_repo)
    items, info = doctor._governance_checks(governance_repo)

    assert doctor._max_severity(items) == doctor.PASS
    assert info["current_state"]["evidence_id"] == expected["evidence_id"]
    assert info["current_state"]["captured_at_utc"] == expected["captured_at_utc"]
    assert any(expected["captured_at_utc"] in item.message for item in items)
    assert any("snapshot" in item.message.lower() for item in items)


def test_legacy_checkmark_cannot_replace_missing_current_evidence(governance_repo):
    _snapshot_path(governance_repo).unlink()
    (governance_repo / "docs/goodq4all_agent_status.md").write_text(
        "MODE: Operational\n| Phase 6b Harmonization | \u2705 | ready |\n",
        encoding="utf-8",
    )

    items, info = doctor._governance_checks(governance_repo)

    assert doctor._max_severity(items) == doctor.FAIL
    assert "current_state" not in info


@pytest.mark.parametrize("malformed", ["{broken", "[]", "null", '{"schema_version": 999}'])
def test_malformed_current_evidence_is_visible_failure(governance_repo, malformed):
    _snapshot_path(governance_repo).write_text(malformed, encoding="utf-8")

    items, info = doctor._governance_checks(governance_repo)

    assert doctor._max_severity(items) == doctor.FAIL
    assert "current_state" not in info


def test_edited_projection_cannot_claim_validated_governance(governance_repo):
    projected = _read_snapshot(governance_repo)
    projected["lifecycle"]["state"] = "invented_live_readiness"
    _write_snapshot(governance_repo, projected)

    items, info = doctor._governance_checks(governance_repo)

    assert doctor._max_severity(items) == doctor.FAIL
    assert "current_state" not in info


@pytest.mark.parametrize("missing", [False, True])
def test_missing_or_edited_source_receipt_cannot_validate_snapshot(governance_repo, missing):
    evidence_path = governance_repo / _read_snapshot(governance_repo)["generated_from"]
    if missing:
        evidence_path.unlink()
    else:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["completion"]["processed_media"] = 999
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    items, info = doctor._governance_checks(governance_repo)

    assert doctor._max_severity(items) == doctor.FAIL
    assert "current_state" not in info


def test_source_receipt_cannot_escape_its_governed_directory(governance_repo):
    projected = _read_snapshot(governance_repo)
    original = governance_repo / projected["generated_from"]
    shutil.copyfile(original, governance_repo / "outside.json")
    projected["generated_from"] = "outside.json"
    _write_snapshot(governance_repo, projected)

    items, info = doctor._governance_checks(governance_repo)

    assert doctor._max_severity(items) == doctor.FAIL
    assert "current_state" not in info


def test_unreadable_snapshot_fails_visibly(governance_repo, monkeypatch):
    read_text = Path.read_text

    def denied(path, *args, **kwargs):
        if path == _snapshot_path(governance_repo):
            raise PermissionError("test-owned denied snapshot")
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", denied)
    items, info = doctor._governance_checks(governance_repo)

    assert doctor._max_severity(items) == doctor.FAIL
    assert "current_state" not in info


def test_governance_verification_is_passive_and_preserves_source_bytes(governance_repo, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("governance must not probe services or launch processes")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(doctor, "probe_wsl_audio_runtime", forbidden)
    before = {p.relative_to(governance_repo): p.read_bytes() for p in governance_repo.rglob("*") if p.is_file()}

    items, _ = doctor._governance_checks(governance_repo)

    assert doctor._max_severity(items) == doctor.PASS
    after = {p.relative_to(governance_repo): p.read_bytes() for p in governance_repo.rglob("*") if p.is_file()}
    assert after == before


def test_promoted_snapshot_and_legacy_checkmark_do_not_prove_live_phase6_readiness(governance_repo):
    gov = {"current_state": _read_snapshot(governance_repo), "phase6b_status": "\u2705 operational"}

    items = doctor._phase6_checks(REPO_ROOT, {"phase6": {"enabled": True}}, gov)

    assert doctor._max_severity(items) == doctor.WARN
    assert any("live" in item.message.lower() and "readiness" in item.message.lower() for item in items)


def test_disabled_phase6_does_not_require_live_readiness_evidence():
    items = doctor._phase6_checks(REPO_ROOT, {"phase6": {"enabled": False}}, {})

    assert doctor._max_severity(items) == doctor.PASS
