from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from cli import golden_witness
from cli import run_ingestion


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


def test_prepare_witness_run_scopes_every_mutable_path_to_witness_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A prepared receipt must not point a later runner at canonical storage."""
    input_path = tmp_path / "known-input.mp4"
    input_path.write_bytes(b"known witness input")
    artifact_root = tmp_path / "witness"
    monkeypatch.setattr(
        golden_witness,
        "_probe_stream_metadata",
        lambda _path: {"format_name": "mov", "duration_seconds": 1.0},
    )

    receipt = golden_witness.prepare_witness_run(artifact_root, input_path)

    root = artifact_root.resolve()
    for path in receipt["mutable_paths"].values():
        Path(path).resolve().relative_to(root)
    assert receipt["runner"]["module"] == "cli.run_ingestion"
    assert receipt["promotion_enabled"] is False
    assert artifact_root.exists() is False


def test_seal_prepared_receipt_writes_a_validated_runtime_snapshot_and_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sealing must be the first and only approved mutation before execution."""
    input_path = tmp_path / "known-input.mp4"
    input_path.write_bytes(b"known witness input")
    artifact_root = tmp_path / "witness"
    monkeypatch.setattr(
        golden_witness,
        "_probe_stream_metadata",
        lambda _path: {"format_name": "mov", "duration_seconds": 1.0},
    )
    prepared = golden_witness.prepare_witness_run(artifact_root, input_path)

    receipt_path = golden_witness.seal_prepared_receipt(prepared)

    assert receipt_path == artifact_root / "prepared-receipt.json"
    sealed = json.loads(receipt_path.read_text(encoding="utf-8"))
    config_path = artifact_root / "config" / "witness-config.json"
    assert sealed["status"] == "sealed"
    assert sealed["runtime_config_path"] == str(config_path)
    runtime_cfg = run_ingestion.load_isolated_runtime_cfg_snapshot(config_path)
    assert runtime_cfg["witness"]["promotion_enabled"] is False
    assert runtime_cfg["witness"]["allow_sqlite_embeddings"] is True
    assert runtime_cfg["witness"]["allow_turboquant_active_retrieval"] is False
    assert runtime_cfg["ingestion_isolation"] is True
    assert runtime_cfg["memory"]["routing"] == {
        "quantization_enabled": False,
        "quantization_shadow_mode": True,
    }
    assert runtime_cfg["qdrant"]["host"] == "http://127.0.0.1:6333"
    assert set(runtime_cfg["qdrant"]["collections"]) == {"clip", "dino", "text", "audio"}
    assert all("witness" in name for name in runtime_cfg["qdrant"]["collections"].values())
    assert runtime_cfg["phase6"]["clip_collection"] == runtime_cfg["qdrant"]["collections"]["clip"]
    assert runtime_cfg["phase6"]["dino_collection"] == runtime_cfg["qdrant"]["collections"]["dino"]
    assert sorted(path.relative_to(artifact_root).as_posix() for path in artifact_root.rglob("*") if path.is_file()) == [
        "config/witness-config.json",
        "prepared-receipt.json",
    ]
