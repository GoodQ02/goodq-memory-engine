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
        "ingestion_isolation": True,
        "witness": {
            "ingestion_isolation": True,
            "promotion_enabled": False,
            "artifact_root": str(root),
        },
        "paths": {**_isolated_paths(root), "models_cache": str(models_cache)},
        "qdrant": {
            "host": "http://127.0.0.1:6334",
            "collections": {
                "clip": "goodq_clip_epoch_r24_witness",
                "dino": "goodq_dino_epoch_r24_witness",
                "text": "goodq_text_epoch_r24_witness",
                "audio": "goodq_audio_epoch_r24_witness",
            },
        },
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


def test_isolated_runner_snapshot_requires_the_runtime_isolation_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "witness"
    snapshot = _isolated_snapshot(root, tmp_path / "shared-model-cache")
    snapshot.pop("ingestion_isolation")
    snapshot_path = root / "config" / "witness-config.json"
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    monkeypatch.setattr(run_ingestion, "load_configs", lambda _overrides: {})

    with pytest.raises(typer.BadParameter, match="ingestion_isolation=true"):
        run_ingestion.load_isolated_runtime_cfg_snapshot(snapshot_path)


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


def test_isolated_runner_snapshot_allows_existing_qdrant_only_for_fresh_witness_collections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "witness"
    snapshot = _isolated_snapshot(root, tmp_path / "shared-model-cache")
    snapshot["qdrant"] = {
        "host": "http://127.0.0.1:6333",
        "collections": {
            "clip": "goodq_clip_epoch_r24_witness",
            "dino": "goodq_dino_epoch_r24_witness",
            "text": "goodq_text_epoch_r24_witness",
            "audio": "goodq_audio_epoch_r24_witness",
        },
    }
    snapshot_path = root / "config" / "witness-config.json"
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    monkeypatch.setattr(run_ingestion, "load_configs", lambda _overrides: {})

    cfg = run_ingestion.load_isolated_runtime_cfg_snapshot(snapshot_path)

    assert cfg["qdrant"]["host"] == "http://127.0.0.1:6333"


def test_isolated_runner_snapshot_rejects_default_qdrant_collections_on_existing_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "witness"
    snapshot = _isolated_snapshot(root, tmp_path / "shared-model-cache")
    snapshot["qdrant"] = {
        "host": "http://127.0.0.1:6333",
        "collections": {
            "clip": "goodq_clip_default",
            "dino": "goodq_dino_default",
            "text": "goodq_text_default",
            "audio": "goodq_audio_default",
        },
    }
    snapshot_path = root / "config" / "witness-config.json"
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    monkeypatch.setattr(run_ingestion, "load_configs", lambda _overrides: {})

    with pytest.raises(typer.BadParameter, match="fresh witness collections"):
        run_ingestion.load_isolated_runtime_cfg_snapshot(snapshot_path)


def test_isolated_runner_snapshot_rejects_missing_collections_on_any_loopback_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "witness"
    snapshot = _isolated_snapshot(root, tmp_path / "shared-model-cache")
    snapshot["qdrant"] = {"host": "http://127.0.0.1:6334"}
    snapshot_path = root / "config" / "witness-config.json"
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    monkeypatch.setattr(run_ingestion, "load_configs", lambda _overrides: {})

    with pytest.raises(typer.BadParameter, match="fresh witness collections"):
        run_ingestion.load_isolated_runtime_cfg_snapshot(snapshot_path)


def test_isolated_runner_snapshot_rejects_an_escaped_faiss_index_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "witness"
    snapshot = _isolated_snapshot(root, tmp_path / "shared-model-cache")
    snapshot["paths"]["faiss_index_path"] = str(tmp_path / "canonical" / "text.index")
    snapshot_path = root / "config" / "witness-config.json"
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    monkeypatch.setattr(run_ingestion, "load_configs", lambda _overrides: {})

    with pytest.raises(typer.BadParameter, match="escapes witness root"):
        run_ingestion.load_isolated_runtime_cfg_snapshot(snapshot_path)


def test_isolated_scene_start_does_not_read_legacy_scene_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _unexpected_legacy_read(*_args, **_kwargs):
        raise AssertionError("isolated scene startup must not read legacy memory.db metadata")

    monkeypatch.setattr(run_ingestion, "get_scene_meta", _unexpected_legacy_read)
    monkeypatch.setattr(run_ingestion, "scene_has_materialized", _unexpected_legacy_read)

    existing_meta, materialized = run_ingestion._resolve_existing_scene_state(
        {"ingestion_isolation": True},
        "scene-1",
    )

    assert existing_meta == {}
    assert materialized == {"keyframe": False, "audio": False}
