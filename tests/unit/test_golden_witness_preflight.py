from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from cli import golden_witness


def test_preflight_records_supplied_input_identity_without_creating_witness_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A preflight must not mutate the candidate root or lose input provenance."""
    input_path = tmp_path / "known-input.mp4"
    input_path.write_bytes(b"known witness input")
    artifact_root = tmp_path / "witness"
    monkeypatch.setattr(
        golden_witness,
        "_probe_stream_metadata",
        lambda _path: {"format_name": "mov", "duration_seconds": 1.0},
    )

    receipt = golden_witness.preflight_witness(artifact_root, input_path)

    assert receipt["status"] == "ready"
    assert receipt["input"]["sha256"] == hashlib.sha256(input_path.read_bytes()).hexdigest()
    assert receipt["config"]["ingestion_isolation"] is True
    assert receipt["config"]["promotion_enabled"] is False
    assert artifact_root.exists() is False


def test_build_config_rejects_model_cache_inside_witness_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cache path under the evidence root could make a read-only preflight unsafe."""
    artifact_root = tmp_path / "witness"
    monkeypatch.setattr(
        golden_witness,
        "resolve_models_root",
        lambda: artifact_root / "models",
    )

    with pytest.raises(
        golden_witness.WitnessAuthorityError,
        match="model cache.*inside witness root",
    ):
        golden_witness.build_witness_config(artifact_root, tmp_path / "input.mp4")
