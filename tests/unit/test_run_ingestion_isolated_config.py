from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer

from cli import run_ingestion


def _isolated_paths(root: Path) -> dict[str, str]:
    data = root / "data"
    epoch = data / "epochs" / "epoch_witness_r24"
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
        "epoch_id": "epoch_witness_r24",
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
                "clip": "goodq_clip_epoch_witness_r24",
                "dino": "goodq_dino_epoch_witness_r24",
                "text": "goodq_text_epoch_witness_r24",
                "audio": "goodq_audio_epoch_witness_r24",
            },
        },
    }


def _write_snapshot(root: Path, snapshot: dict) -> Path:
    path = root / "config" / "witness-config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    return path


@pytest.mark.parametrize("marker", [None, False, {}, {"artifact_root": "incomplete"}, "malformed"])
@pytest.mark.parametrize("caller", ["direct", "ambient"])
def test_witness_metadata_cannot_fall_through_to_canonical_intake(tmp_path, monkeypatch, marker, caller):
    cfg = {"ingestion_isolation": True, "witness": marker}
    monkeypatch.setattr(run_ingestion, "load_configs", lambda _: cfg)
    monkeypatch.setattr(run_ingestion, "_ensure_dir", lambda *_: pytest.fail("witness reached writes"))
    with pytest.raises(typer.BadParameter, match="fresh process"):
        run_ingestion.run_with_config(
            **({"cfg": cfg} if caller == "direct" else {}),
            input_dir=tmp_path, output=tmp_path / "out.json", workspace=tmp_path / "workspace",
        )
    assert not (tmp_path / "workspace").exists()


@pytest.mark.parametrize("caller", ["direct", "ambient"])
def test_inherited_witness_marker_requires_explicit_snapshot(tmp_path, monkeypatch, caller):
    cfg = {"ingestion_isolation": True}
    monkeypatch.setenv("GOODQ_WITNESS_CONFIG", str(tmp_path / "witness.json"))
    monkeypatch.setattr(run_ingestion, "load_configs", lambda _: cfg)
    with pytest.raises(typer.BadParameter, match="fresh process"):
        run_ingestion.run_with_config(
            **({"cfg": cfg} if caller == "direct" else {}),
            input_dir=tmp_path, output=tmp_path / "out.json", workspace=tmp_path / "workspace",
        )
    assert not (tmp_path / "workspace").exists()


@pytest.mark.parametrize("marker", [None, False, {}, "missing"])
def test_explicit_snapshot_cannot_inherit_missing_witness_metadata(tmp_path, monkeypatch, marker):
    root = tmp_path / "witness"
    valid = _isolated_snapshot(root, tmp_path / "models")
    snapshot = dict(valid)
    if marker == "missing":
        snapshot.pop("witness")
    else:
        snapshot["witness"] = marker
    monkeypatch.setattr(run_ingestion, "load_configs", lambda _: valid)
    with pytest.raises(typer.BadParameter, match="witness"):
        run_ingestion.run_with_config(
            config=_write_snapshot(root, snapshot), input_dir=tmp_path,
            output=root / "results.json", workspace=root / "workspace",
        )
    assert not (root / "workspace").exists()


@pytest.mark.parametrize("mutation,match", [
    ("db_epoch", "db_dir.*epoch"),
    ("identity_kg", "identity_search.kg_db_path.*knowledge_graph_db"),
    ("epoch_format", "witness epoch_id"),
])
def test_isolated_loader_rejects_split_store_identity(tmp_path, monkeypatch, mutation, match):
    root = tmp_path / "witness"
    snapshot = _isolated_snapshot(root, tmp_path / "models")
    if mutation == "db_epoch":
        snapshot["paths"]["db_dir"] = str(root / "data" / "epochs" / "another_epoch")
    elif mutation == "identity_kg":
        snapshot["identity_search"] = {"kg_db_path": str(root / "other-knowledge-graph.db")}
    else:
        snapshot["epoch_id"] = "legacy_witness_epoch"
        snapshot["qdrant"]["collections"] = {
            key: f"goodq_{key}_legacy_witness_epoch" for key in ("clip", "dino", "text", "audio")
        }
    monkeypatch.setattr(run_ingestion, "load_configs", lambda _: {})
    with pytest.raises(typer.BadParameter, match=match):
        run_ingestion.load_isolated_runtime_cfg_snapshot(_write_snapshot(root, snapshot))


@pytest.mark.parametrize("caller", ["direct_cfg", "unbound_snapshot", "stale_singleton"])
def test_isolated_production_caller_requires_fresh_bound_process(tmp_path, monkeypatch, caller):
    from cli import golden_witness
    from cli.witness_environment import build_witness_environment

    root = tmp_path / "witness"
    snapshot = _isolated_snapshot(root, tmp_path / "models")
    snapshot["host"] = {"data_root": snapshot["paths"]["data_root"]}
    snapshot["identity_search"] = {"roster_path": str(root / "identity" / "roster.yaml")}
    snapshot_path = _write_snapshot(root, snapshot)
    monkeypatch.setenv("GOODQ_TEMP_ROOT", str(tmp_path / "operator-processing"))
    if caller == "stale_singleton":
        for key, value in build_witness_environment(snapshot_path, {}).items():
            monkeypatch.setenv(key, value)
    monkeypatch.setattr(run_ingestion, "load_configs", lambda _: {})
    monkeypatch.setattr(run_ingestion, "_select_ingest_videos", lambda *_: (tmp_path, []))

    def must_not_admit(*_args, **_kwargs):
        pytest.fail("unbound isolated caller reached store admission")

    monkeypatch.setattr(golden_witness, "admit_witness_run", must_not_admit)
    args = {"cfg": snapshot} if caller == "direct_cfg" else {"config": snapshot_path}
    with pytest.raises(typer.BadParameter, match="fresh process"):
        run_ingestion.run_with_config(
            input_dir=tmp_path, output=root / "results.json", workspace=root / "workspace", **args,
        )
    assert not (root / "workspace").exists()
    assert not (tmp_path / "operator-processing").exists()


@pytest.mark.parametrize("section,key", [
    ("paths", "reports_dir"), ("paths", "csv_path"), ("paths", "nas_path"),
    ("host", "data_root"), ("identity_search", "kg_db_path"),
    ("identity_search", "roster_path"),
])
def test_isolated_loader_rejects_inherited_mutable_targets(tmp_path, monkeypatch, section, key):
    root = tmp_path / "witness"
    snapshot = _isolated_snapshot(root, tmp_path / "models")
    monkeypatch.setattr(run_ingestion, "load_configs", lambda _: {
        section: {key: str(tmp_path / "canonical" / key)},
    })
    with pytest.raises(typer.BadParameter, match="escapes witness root"):
        run_ingestion.load_isolated_runtime_cfg_snapshot(_write_snapshot(root, snapshot))


@pytest.mark.parametrize("mutation", ["missing_epoch", "wrong_epoch", "wrong_alias"])
def test_isolated_loader_rejects_inherited_or_mismatched_epoch(tmp_path, monkeypatch, mutation):
    root = tmp_path / "witness"
    snapshot = _isolated_snapshot(root, tmp_path / "models")
    if mutation == "missing_epoch":
        snapshot.pop("epoch_id")
    elif mutation == "wrong_epoch":
        snapshot["epoch_id"] = "canonical_epoch"
    else:
        snapshot["phase6"] = {"clip_collection": "goodq_clip_another_witness"}
    monkeypatch.setattr(run_ingestion, "load_configs", lambda _: {"epoch_id": "canonical_epoch"})
    with pytest.raises(typer.BadParameter, match="epoch|phase6"):
        run_ingestion.load_isolated_runtime_cfg_snapshot(_write_snapshot(root, snapshot))


def test_isolated_loader_does_not_mutate_ambient_configuration(tmp_path, monkeypatch):
    root = tmp_path / "witness"
    snapshot = _isolated_snapshot(root, tmp_path / "models")
    base = {"paths": {"models_cache": "shared-models"}}
    monkeypatch.setattr(run_ingestion, "load_configs", lambda _: base)
    run_ingestion.load_isolated_runtime_cfg_snapshot(_write_snapshot(root, snapshot))
    assert base == {"paths": {"models_cache": "shared-models"}}


@pytest.mark.parametrize("escaped", ["output", "workspace"])
def test_isolated_production_caller_rejects_overrides_before_writes(tmp_path, monkeypatch, escaped):
    root = tmp_path / "witness"
    snapshot = _isolated_snapshot(root, tmp_path / "models")
    monkeypatch.setattr(run_ingestion, "load_configs", lambda _: {})
    monkeypatch.setattr(run_ingestion, "_select_ingest_videos", lambda *_: (tmp_path, []))
    def must_not_write(*_args, **_kwargs):
        pytest.fail("isolated caller reached writes before validating CLI overrides")
    monkeypatch.setattr(run_ingestion, "_ensure_dir", must_not_write)
    args = {"output": root / "results.json", "workspace": root / "workspace"}
    args[escaped] = tmp_path / "canonical" / escaped
    with pytest.raises(typer.BadParameter, match="escapes witness root"):
        run_ingestion.run_with_config(config=_write_snapshot(root, snapshot), input_dir=tmp_path, **args)


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
            "clip": "goodq_clip_epoch_witness_r24",
            "dino": "goodq_dino_epoch_witness_r24",
            "text": "goodq_text_epoch_witness_r24",
            "audio": "goodq_audio_epoch_witness_r24",
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
