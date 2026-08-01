from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer

from cli import run_ingestion


def _isolated_paths(root: Path) -> dict[str, str]:
    data = root / "data"
    epoch = data / "epochs" / "witness"
    return {
        "data_root": str(data),
        "db_dir": str(epoch),
        "db_path": str(epoch / "memory.db"),
        "knowledge_graph_db": str(epoch / "knowledge_graph.db"),
        "processing": str(epoch / "processing"),
        "log_dir": str(epoch / "logs"),
        "output_directory": str(epoch / "output"),
        "faiss_dir": str(epoch / "faiss"),
        "faiss_audio_path": str(epoch / "faiss" / "audio.index"),
        "faiss_index_path": str(epoch / "faiss" / "text.index"),
        "faiss_clip_path": str(epoch / "faiss" / "clip.index"),
        "faiss_dino_path": str(epoch / "faiss" / "dino.index"),
        "clip_id_map_db": str(epoch / "faiss" / "clip-id-map.sqlite"),
        "dino_id_map_db": str(epoch / "faiss" / "dino-id-map.sqlite"),
        "clap_id_map_db": str(epoch / "faiss" / "clap-id-map.sqlite"),
        "qdrant_storage": str(data / "qdrant"),
        "watchdog_state_file": str(epoch / "logs" / "watchdog_state.json"),
        "watchdog_lock_file": str(epoch / "logs" / "watchdog.lock"),
        "import_inbox": str(data / "import_inbox"),
        "ingest_requests": str(data / "ingest_requests"),
        "processed": str(data / "processed"),
        "failed": str(data / "failed"),
    }


def _isolated_snapshot(root: Path, models_cache: Path) -> dict[str, object]:
    return {
        "witness": {
            "ingestion_isolation": True,
            "promotion_enabled": False,
            "artifact_root": str(root),
        },
        "paths": {**_isolated_paths(root), "models_cache": str(models_cache)},
        "qdrant": {"host": "http://127.0.0.1:6334"},
    }


def test_isolated_runner_snapshot_accepts_only_witness_owned_mutable_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "witness"
    snapshot_path = root / "config" / "witness-config.json"
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text(
        json.dumps(_isolated_snapshot(root, tmp_path / "shared-model-cache")),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_ingestion, "load_configs", lambda _overrides: {})

    cfg = run_ingestion.load_isolated_runtime_cfg_snapshot(snapshot_path)

    assert cfg["witness"]["ingestion_isolation"] is True
    assert Path(cfg["paths"]["db_path"]).resolve().is_relative_to(root.resolve())
    assert Path(cfg["paths"]["models_cache"]).resolve().is_relative_to(root.resolve()) is False


def test_isolated_runner_snapshot_rejects_a_canonical_mutable_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "witness"
    snapshot = _isolated_snapshot(root, tmp_path / "shared-model-cache")
    snapshot["paths"]["db_path"] = str(tmp_path / "canonical" / "memory.db")
    snapshot_path = root / "config" / "witness-config.json"
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    monkeypatch.setattr(run_ingestion, "load_configs", lambda _overrides: {})

    with pytest.raises(typer.BadParameter, match="escapes witness root"):
        run_ingestion.load_isolated_runtime_cfg_snapshot(snapshot_path)
