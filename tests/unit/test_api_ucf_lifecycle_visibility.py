from __future__ import annotations

import hashlib
from contextlib import closing
import json
from pathlib import Path
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def governed_library(tmp_path, monkeypatch):
    from api.routes import media, scenes, system, timeline
    from api.utils import loaders

    data = tmp_path / "epoch-fixture"
    directory = data / "processing" / "sample"
    (directory / "video/frames").mkdir(parents=True)
    (directory / "audio/chunks").mkdir(parents=True)
    source = data / "sample.mp4"
    source.write_bytes(b"retained source fixture")
    video_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    frame = directory / "video/frames/frame_0000.jpg"
    frame.write_bytes(b"retained frame fixture")
    audio = directory / "audio/chunks/scene_0000.wav"
    audio.write_bytes(b"retained audio fixture")
    temporal = {
        "video_id": video_hash, "video_hash": video_hash, "video_path": str(source),
        "total_scenes": 1, "total_duration": 1,
        "segments": [{"scene_id": 0, "segment_id": 0, "start": 0, "end": 1,
                      "frame_paths": [str(frame)], "representative_frame": str(frame)}],
    }
    (directory / "temporal_index.json").write_text(json.dumps(temporal), encoding="utf-8")
    (directory / "video/scene_manifest.json").write_text(json.dumps({
        **{k: temporal[k] for k in ("video_id", "video_hash", "video_path")},
        "scenes": [{"scene_id": 0, "index": 0, "audio": {"path": str(audio)}}],
    }), encoding="utf-8")
    ledger = data / "ucf/ucf_ledger.db"
    ledger.parent.mkdir()
    with closing(sqlite3.connect(ledger)) as conn, conn:
        conn.execute("CREATE TABLE context_frames (video_hash TEXT, epoch_id TEXT, promotion_status TEXT)")
    cfg = {"epoch_id": "epoch-fixture", "paths": {
        "data_root": str(data), "processing": str(directory.parent), "db_dir": str(data),
    }}
    for key in ("_DEFAULT_PROCESSING_ROOT", "_DEFAULT_PROCESSED_ROOT", "_DEFAULT_UCF_SCOPE"):
        monkeypatch.setattr(loaders, key, None, raising=False)
    monkeypatch.setattr(loaders, "_DEFAULT_MEDIA_ROOTS", ())
    loaders.configure_from_cfg(cfg)
    app = FastAPI()
    for module in (system, scenes, timeline, media):
        monkeypatch.setattr(module, "_data_loader", None)
        app.include_router(module.router)

    def statuses(values, *, epoch="epoch-fixture", source_hash=None):
        with closing(sqlite3.connect(ledger)) as conn, conn:
            conn.execute("DELETE FROM context_frames")
            conn.executemany("INSERT INTO context_frames VALUES (?,?,?)", [
                (source_hash or video_hash, epoch, value) for value in values
            ])

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, statuses, ledger, cfg, data, loaders


ROUTES = (
    "/api/videos/sample/scenes",
    "/api/videos/sample/scenes/0",
    "/api/videos/sample/timeline",
    "/api/videos/sample/timeline/full",
    "/api/media/video/sample/source",
    "/api/media/video/sample/scene/0/audio",
    "/api/media/audio/sample/0.wav",
    "/api/media/video/sample/scene/0/frame/0",
    "/api/media/video/sample/frame/frame_0000.jpg",
)


@pytest.mark.parametrize("statuses,visible", [
    (["superseded"], False), (["rejected"], False),
    (["superseded", "rejected"], False),
    (["promoted"], True), (["validated"], True), (["staged"], True),
    (["superseded", "promoted"], True), ([], True),
])
def test_real_routes_respect_lifecycle_without_removing_retained_files(governed_library, statuses, visible):
    client, set_status, ledger, _, data, _ = governed_library
    set_status(statuses)
    before = {p.relative_to(data): p.read_bytes() for p in data.rglob("*") if p.is_file()}
    listing = client.get("/api/system/videos")
    assert listing.status_code == 200
    assert len(listing.json()) == int(visible)
    for path in ROUTES:
        assert client.get(path).status_code == (200 if visible else 404), path
    assert before == {p.relative_to(data): p.read_bytes() for p in data.rglob("*") if p.is_file()}


@pytest.mark.parametrize("other_scope", ["epoch", "video"])
def test_terminal_frame_in_other_scope_does_not_hide_legacy_video(governed_library, other_scope):
    client, set_status, _, _, _, _ = governed_library
    set_status(["superseded"], **({"epoch": "another-epoch"} if other_scope == "epoch" else {"source_hash": "another-video"}))
    assert len(client.get("/api/system/videos").json()) == 1
    assert client.get("/api/videos/sample/scenes").status_code == 200


def test_existing_loader_observes_lifecycle_transition(governed_library):
    client, set_status, _, _, _, _ = governed_library
    set_status(["promoted"])
    assert len(client.get("/api/system/videos").json()) == 1
    assert client.get("/api/videos/sample/scenes").status_code == 200
    set_status(["superseded"])
    assert client.get("/api/system/videos").json() == []
    assert client.get("/api/videos/sample/scenes").status_code == 404


@pytest.mark.parametrize("path", ["/api/media/video/sample/frame/frame_0000.jpg", "/api/media/audio/sample/0.wav"])
def test_terminal_media_paths_cannot_bypass_lifecycle(governed_library, path):
    client, set_status, _, _, _, _ = governed_library
    set_status(["superseded"])
    assert client.get(path).status_code == 404


@pytest.mark.parametrize("failure", ["missing", "corrupt", "unreadable"])
def test_configured_governed_ledger_failure_is_observable_and_does_not_create_db(governed_library, monkeypatch, caplog, failure):
    client, _, ledger, _, data, loaders = governed_library
    if failure == "missing":
        ledger.unlink()
    elif failure == "corrupt":
        ledger.write_bytes(b"not a sqlite database")
    else:
        def denied(*args, **kwargs):
            raise sqlite3.OperationalError("fixture ledger access denied")
        monkeypatch.setattr(sqlite3, "connect", denied)
    before = {p.relative_to(data): p.read_bytes() for p in data.rglob("*") if p.is_file()}
    for path in ("/api/system/videos", *ROUTES):
        response = client.get(path)
        assert response.status_code == 500, path
    assert "UCF lifecycle" in caplog.text
    assert before == {p.relative_to(data): p.read_bytes() for p in data.rglob("*") if p.is_file()}


def test_unconfigured_legacy_no_ledger_preserves_existing_visibility(governed_library):
    client, _, ledger, cfg, _, loaders = governed_library
    ledger.unlink()
    loaders.configure_from_cfg({"paths": {"processing": cfg["paths"]["processing"]}})
    assert len(client.get("/api/system/videos").json()) == 1
    assert client.get("/api/videos/sample/scenes").status_code == 200
    assert not ledger.exists()


def test_ordinary_config_without_witness_epoch_excludes_terminal_scope(governed_library):
    client, set_status, _, cfg, _, loaders = governed_library
    set_status(["superseded"])
    loaders.configure_from_cfg({"paths": cfg["paths"]})
    assert client.get("/api/system/videos").json() == []
    assert client.get("/api/videos/sample/scenes").status_code == 404


def test_pristine_governed_root_without_ledger_remains_empty(governed_library, tmp_path):
    client, _, _, _, _, loaders = governed_library
    pristine = tmp_path / "pristine-epoch"
    loaders.configure_from_cfg({"epoch_id": "pristine-epoch", "paths": {
        "processing": str(pristine / "processing"), "db_dir": str(pristine),
    }})
    assert client.get("/api/system/videos").json() == []
    assert client.get("/api/videos/absent/scenes").status_code == 404
    assert client.get("/api/media/video/absent/source").status_code == 404
    assert not pristine.exists()
