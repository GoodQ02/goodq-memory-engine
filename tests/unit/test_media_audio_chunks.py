from __future__ import annotations

import io
import asyncio
import hashlib
import json
import os
from pathlib import Path
import wave
import threading
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from api.main import app
from api.routes import media, scenes
from api.utils import loaders


@pytest.fixture
def audio_media_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data_root = tmp_path / "data"
    monkeypatch.setattr(loaders, "_DEFAULT_PROCESSING_ROOT", data_root / "processing")
    monkeypatch.setattr(loaders, "_DEFAULT_MEDIA_ROOTS", (), raising=False)
    monkeypatch.setattr(loaders, "_DEFAULT_PROCESSED_ROOT", data_root / "processed", raising=False)
    monkeypatch.setattr(media, "_data_loader", None)
    monkeypatch.setattr(scenes, "_data_loader", None)
    return TestClient(app, client=("127.0.0.1", 50000)), data_root


def _write_wave(path: Path, sample: bytes = b"\x00\x00") -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(sample * 16)
    contents = buffer.getvalue()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)
    return contents


@pytest.mark.parametrize("root_name", ["processing", "completed"])
@pytest.mark.parametrize("chunk_id", [0, 12])
@pytest.mark.parametrize("filename_format", ["scene_{:04d}.wav", "segment_{}.wav"])
def test_audio_media_route_serves_generated_and_legacy_chunks(
    audio_media_client, root_name: str, chunk_id: int, filename_format: str,
) -> None:
    client, data_root = audio_media_client
    path = data_root / root_name / "video_fixture" / "audio" / "chunks" / filename_format.format(chunk_id)
    contents = _write_wave(path)

    response = client.get(f"/api/media/audio/video_fixture/{chunk_id}.wav")

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == contents


@pytest.mark.parametrize("filename", ["scene_0000.wav", "segment_0.wav"])
def test_audio_media_route_prefers_processing_for_each_filename(
    audio_media_client, filename: str,
) -> None:
    client, data_root = audio_media_client
    relative = Path("video_fixture/audio/chunks") / filename
    processing_bytes = _write_wave(data_root / "processing" / relative, b"\x01\x00")
    _write_wave(data_root / "completed" / relative, b"\x02\x00")

    response = client.get("/api/media/audio/video_fixture/0.wav")

    assert response.status_code == 200
    assert response.content == processing_bytes


def test_audio_media_route_preserves_existing_segment_lookup_precedence(audio_media_client) -> None:
    client, data_root = audio_media_client
    relative = Path("video_fixture/audio/chunks")
    legacy_bytes = _write_wave(data_root / "completed" / relative / "segment_0.wav", b"\x01\x00")
    _write_wave(data_root / "processing" / relative / "scene_0000.wav", b"\x02\x00")

    response = client.get("/api/media/audio/video_fixture/0.wav")

    assert response.status_code == 200
    assert response.content == legacy_bytes


def test_audio_media_route_missing_chunk_remains_404_without_creating_paths(audio_media_client) -> None:
    client, data_root = audio_media_client

    response = client.get("/api/media/audio/video_fixture/0.wav")

    assert response.status_code == 404
    assert response.json() == {"detail": "Audio chunk not found"}
    assert not data_root.exists()


def _write_scene_metadata(root: Path, manifest: object) -> Path:
    video_dir = root / "video_fixture"
    video_dir.mkdir(parents=True, exist_ok=True)
    (video_dir / "temporal_index.json").write_text(json.dumps({
        "segments": [
            {"scene_id": "scene-hash-12", "start": 30.0, "end": 35.0},
            {"scene_id": "scene-hash-3", "start": 5.0, "end": 8.0},
        ],
    }), encoding="utf-8")
    manifest_path = video_dir / "video" / "scene_manifest.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


@pytest.mark.parametrize("root_name", ["processing", "completed"])
def test_scene_list_and_detail_link_exact_original_audio_and_ranges(audio_media_client, root_name):
    client, data_root = audio_media_client
    root = data_root / root_name
    _write_scene_metadata(root, {"scenes": [
        {"scene_id": "scene-hash-3", "audio": {"path": "old/machine/scene_0003.wav"}},
        {"scene_id": "scene-hash-12", "index": 12,
         "audio": {"path": r"Z:\old\processing\video_fixture\audio\chunks\scene_0012.wav"}},
    ]})
    audio_dir = root / "video_fixture/audio/chunks"
    expected = _write_wave(audio_dir / "scene_0012.wav", b"\x01\x00")
    other_scene = _write_wave(audio_dir / "scene_0003.wav", b"\x02\x00")
    legacy = _write_wave(audio_dir / "segment_12.wav", b"\x03\x00")

    listing = client.get("/api/videos/video_fixture/scenes")
    assert listing.status_code == 200
    selected = listing.json()[0]
    assert selected["original_audio_available"] is True
    endpoint = selected["original_audio_endpoint"]
    assert endpoint == "/api/media/video/video_fixture/scene/scene-hash-12/audio"
    detail = client.get("/api/videos/video_fixture/scenes/scene-hash-12")
    assert detail.status_code == 200
    assert detail.json()["original_audio_endpoint"] == endpoint
    response = client.get(endpoint)
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == expected
    partial = client.get(endpoint, headers={"Range": "bytes=4-15"})
    assert partial.status_code == 206
    assert partial.headers["content-range"] == f"bytes 4-15/{len(expected)}"
    assert partial.content == expected[4:16]
    assert client.get(listing.json()[1]["original_audio_endpoint"]).content == other_scene
    assert client.get("/api/media/audio/video_fixture/12.wav").content == legacy
    assert str(data_root) not in listing.text


@pytest.mark.parametrize("failure", [
    "no_manifest", "malformed_manifest", "wrong_scene", "missing_file",
    "legacy_only", "conflicting_path", "invalid_index", "duplicate_scene",
    "duplicate_filename", "conflicting_id",
])
def test_scene_original_audio_unavailable_is_truthful(audio_media_client, failure):
    client, data_root = audio_media_client
    entry = {"scene_id": "scene-hash-12", "index": 12}
    manifest = {"scenes": [entry]}
    if failure == "wrong_scene":
        entry["scene_id"] = "unrelated-scene"
    elif failure == "conflicting_path":
        entry["audio"] = {"path": "scene_0003.wav"}
    elif failure == "invalid_index":
        entry["index"] = -1
    elif failure == "duplicate_scene":
        manifest["scenes"].append(dict(entry, index=3))
    elif failure == "duplicate_filename":
        manifest["scenes"].append(dict(entry, scene_id="scene-hash-3"))
    elif failure == "conflicting_id":
        entry["id"] = "unrelated-scene"
    manifest_path = _write_scene_metadata(data_root / "processing", manifest)
    if failure == "no_manifest":
        manifest_path.unlink()
    elif failure == "malformed_manifest":
        manifest_path.write_text("not JSON", encoding="utf-8")
    if failure not in ("missing_file", "legacy_only"):
        _write_wave(data_root / "processing/video_fixture/audio/chunks/scene_0012.wav")
    _write_wave(data_root / "processing/video_fixture/audio/chunks/segment_12.wav")

    response = client.get("/api/videos/video_fixture/scenes/scene-hash-12")
    assert response.status_code == 200
    assert response.json()["original_audio_available"] is False
    assert response.json()["original_audio_endpoint"] is None
    assert client.get("/api/media/video/video_fixture/scene/scene-hash-12/audio").status_code == 404


def test_scene_audio_unknown_dataset_does_not_create_paths(audio_media_client):
    client, data_root = audio_media_client
    assert client.get("/api/media/video/video_fixture/scene/scene-hash-12/audio").status_code == 404
    assert not data_root.exists()


def test_completed_manifest_does_not_use_stale_processing_audio(audio_media_client):
    client, data_root = audio_media_client
    _write_scene_metadata(data_root / "completed", {
        "scenes": [{"scene_id": "scene-hash-12", "index": 12}],
    })
    expected = _write_wave(data_root / "completed/video_fixture/audio/chunks/scene_0012.wav", b"\x01\x00")
    _write_wave(data_root / "processing/video_fixture/audio/chunks/scene_0012.wav", b"\x02\x00")
    detail = client.get("/api/videos/video_fixture/scenes/scene-hash-12").json()
    assert client.get(detail["original_audio_endpoint"]).content == expected


@pytest.mark.parametrize("missing", ["manifest", "audio"])
def test_scene_audio_does_not_borrow_other_artifact_root(audio_media_client, missing):
    client, data_root = audio_media_client
    root = data_root / ("completed" if missing == "manifest" else "processing")
    _write_scene_metadata(root, {"scenes": [{"scene_id": 0, "index": 12}]})
    temporal_path = data_root / "processing/video_fixture/temporal_index.json"
    temporal_path.parent.mkdir(parents=True, exist_ok=True)
    temporal_path.write_text(json.dumps({"segments": [
        {"scene_id": 0, "start": 30, "end": 35},
    ]}), encoding="utf-8")
    _write_wave(data_root / "completed/video_fixture/audio/chunks/scene_0012.wav")

    detail = client.get("/api/videos/video_fixture/scenes/0")
    assert detail.status_code == 200
    assert detail.json()["original_audio_available"] is False
    assert detail.json()["original_audio_endpoint"] is None
    assert client.get("/api/media/video/video_fixture/scene/0/audio").status_code == 404


def test_numeric_scene_id_and_similar_result_use_same_audio_projection(audio_media_client, monkeypatch):
    client, data_root = audio_media_client
    _write_scene_metadata(data_root / "processing", {
        "scenes": [{"id": 0, "index": 12}],
    })
    temporal_path = data_root / "processing/video_fixture/temporal_index.json"
    temporal_path.write_text(json.dumps({"segments": [
        {"scene_id": 0, "start": 30, "end": 35},
        {"scene_id": 1, "start": 0, "end": 1},
    ]}), encoding="utf-8")
    expected = _write_wave(data_root / "processing/video_fixture/audio/chunks/scene_0012.wav")

    class Engine:
        def search_similar_scene(self, **kwargs):
            return [{"payload": {"scene_id": 0, "video_id": "video_fixture"}}]

    monkeypatch.setattr(scenes, "get_search_engine", lambda: Engine())
    detail = client.get("/api/videos/video_fixture/scenes/0").json()
    similar = client.get("/api/videos/video_fixture/scenes/1/similar")
    assert similar.status_code == 200
    assert similar.json()[0]["original_audio_endpoint"] == detail["original_audio_endpoint"]
    assert detail["original_audio_available"] is True
    assert client.get(detail["original_audio_endpoint"]).content == expected


@pytest.mark.parametrize("result_video_id", ["foreign-video", "source-video-hash"])
def test_similar_numeric_scene_keeps_its_video_identity(audio_media_client, monkeypatch, result_video_id):
    client, data_root = audio_media_client
    _write_scene_metadata(data_root / "processing", {
        "scenes": [{"scene_id": 0, "index": 12}],
    })
    temporal_path = data_root / "processing/video_fixture/temporal_index.json"
    temporal_path.write_text(json.dumps({
        "video_id": "source-video-hash", "video_hash": "source-video-hash",
        "segments": [{"scene_id": 0, "start": 30, "end": 35},
                     {"scene_id": 1, "start": 0, "end": 1}],
    }), encoding="utf-8")
    _write_wave(data_root / "processing/video_fixture/audio/chunks/scene_0012.wav")

    class Engine:
        def search_similar_scene(self, **kwargs):
            return [{"payload": {"scene_id": 0, "video_id": result_video_id},
                     "scene_context": {"scene_id": 0, "video_id": result_video_id,
                                       "start": 40, "end": 45}}]

    monkeypatch.setattr(scenes, "get_search_engine", lambda: Engine())
    response = client.get("/api/videos/video_fixture/scenes/1/similar")
    assert response.status_code == 200
    result = response.json()[0]
    if result_video_id == "foreign-video":
        assert result["video_id"] == "foreign-video"
        assert result["start"] == 40
        assert result["original_audio_available"] is False
        assert result["original_audio_endpoint"] is None
    else:
        assert result["video_id"] == "video_fixture"
        assert result["start"] == 30
        assert result["original_audio_available"] is True
        assert result["original_audio_endpoint"] == "/api/media/video/video_fixture/scene/0/audio"


def test_recorded_audio_path_cannot_serve_outside_selected_dataset(audio_media_client):
    client, data_root = audio_media_client
    outside = data_root.parent / "outside/scene_0012.wav"
    _write_wave(outside)
    _write_scene_metadata(data_root / "processing", {
        "scenes": [{"scene_id": "scene-hash-12", "audio": {"path": str(outside)}}],
    })
    response = client.get("/api/videos/video_fixture/scenes/scene-hash-12")
    assert response.status_code == 200
    assert response.json()["original_audio_available"] is False
    assert client.get("/api/media/video/video_fixture/scene/scene-hash-12/audio").status_code == 404
    escaped_video_id = quote(r"..\..\outside", safe="")
    assert client.get(f"/api/media/video/{escaped_video_id}/scene/scene-hash-12/audio").status_code == 404


def _write_video_source_metadata(data_root, source, contents, root_name="processing"):
    identity = hashlib.sha256(contents).hexdigest()
    manifest_path = _write_scene_metadata(data_root / root_name, {
        "video_id": identity, "video_hash": identity, "video_path": str(source),
        "scenes": [{"scene_id": "scene-hash-12", "index": 12}],
    })
    temporal_path = manifest_path.parent.parent / "temporal_index.json"
    temporal = json.loads(temporal_path.read_text(encoding="utf-8"))
    temporal.update(video_id=identity, video_hash=identity, video_path=str(source))
    temporal_path.write_text(json.dumps(temporal), encoding="utf-8")
    return manifest_path, temporal_path, identity


@pytest.mark.parametrize("root_name", ["processing", "completed"])
def test_original_video_list_detail_link_source_bytes_and_ranges(audio_media_client, root_name):
    client, data_root = audio_media_client
    source = data_root / "originals/source.mp4"
    source.parent.mkdir(parents=True)
    contents = b"source video bytes with known content identity"
    source.write_bytes(contents)
    _write_video_source_metadata(data_root, source, contents, root_name)

    listing = client.get("/api/videos/video_fixture/scenes")
    assert listing.status_code == 200
    selected = listing.json()[0]
    assert selected["original_video_available"] is True
    endpoint = selected["original_video_endpoint"]
    assert endpoint == "/api/media/video/video_fixture/source"
    assert selected["start"] == 30.0
    detail = client.get("/api/videos/video_fixture/scenes/scene-hash-12")
    assert detail.json()["original_video_endpoint"] == endpoint
    response = client.get(endpoint)
    assert response.status_code == 200
    assert response.headers["content-type"] == "video/mp4"
    assert response.content == contents
    partial = client.get(endpoint, headers={"Range": "bytes=4-15"})
    assert partial.status_code == 206
    assert partial.headers["content-range"] == f"bytes 4-15/{len(contents)}"
    assert partial.content == contents[4:16]
    assert str(source) not in listing.text


@pytest.mark.parametrize("failure", [
    "missing", "wrong_bytes", "missing_hash", "conflicting_hash", "conflicting_path",
    "malformed_manifest", "missing_manifest", "outside_root", "unsupported_extension",
    "unc_path", "url_path", "relative_path", "invalid_hash_type",
])
def test_original_video_unavailable_is_truthful(audio_media_client, failure):
    client, data_root = audio_media_client
    source = data_root / "originals/source.mp4"
    if failure == "outside_root":
        source = data_root.parent / "outside/source.mp4"
    if failure == "unsupported_extension":
        source = source.with_suffix(".txt")
    source.parent.mkdir(parents=True)
    contents = b"source video expected bytes"
    source.write_bytes(contents)
    manifest_path, temporal_path, _ = _write_video_source_metadata(data_root, source, contents)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    temporal = json.loads(temporal_path.read_text(encoding="utf-8"))
    if failure == "missing":
        source.unlink()
    elif failure == "wrong_bytes":
        source.write_bytes(b"different video")
    elif failure == "missing_hash":
        for record in (manifest, temporal):
            record.pop("video_hash")
            record["video_id"] = "legacy-storage-name"
    elif failure == "conflicting_hash":
        manifest["video_hash"] = "f" * 64
    elif failure == "invalid_hash_type":
        manifest["video_hash"] = True
    elif failure == "conflicting_path":
        manifest["video_path"] = str(source.with_name("different.mp4"))
    elif failure in ("unc_path", "url_path", "relative_path"):
        locator = {"unc_path": r"\\server\media\source.mp4",
                   "url_path": "https://example.invalid/source.mp4",
                   "relative_path": "originals/source.mp4"}[failure]
        manifest["video_path"] = temporal["video_path"] = locator
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    temporal_path.write_text(json.dumps(temporal), encoding="utf-8")
    if failure == "malformed_manifest":
        manifest_path.write_text("not JSON", encoding="utf-8")
    elif failure == "missing_manifest":
        manifest_path.unlink()

    detail = client.get("/api/videos/video_fixture/scenes/scene-hash-12")
    assert detail.status_code == 200
    assert detail.json()["original_video_available"] is False
    assert detail.json()["original_video_endpoint"] is None
    response = client.get("/api/media/video/video_fixture/source")
    assert response.status_code == 404
    assert response.json() == {"detail": "Original video not found"}


def test_original_video_finds_verified_processed_collision_only(audio_media_client):
    client, data_root = audio_media_client
    source = data_root / "removed-temp/source.mp4"
    contents = b"correct original"
    _write_video_source_metadata(data_root, source, contents)
    processed = data_root / "processed"
    processed.mkdir()
    (processed / "PROCESSED_source.mp4").write_bytes(b"wrong original")
    (processed / "PROCESSED_source_1.mp4").write_bytes(contents)
    (processed / "PROCESSED_source_unrelated.mp4").write_bytes(contents)

    detail = client.get("/api/videos/video_fixture/scenes/scene-hash-12").json()
    assert detail["original_video_available"] is True
    assert client.get(detail["original_video_endpoint"]).content == contents
    (processed / "PROCESSED_source_1.mp4").unlink()
    assert client.get("/api/media/video/video_fixture/source").status_code == 404


def test_original_video_active_artifact_root_never_borrows_manifest(audio_media_client):
    client, data_root = audio_media_client
    source = data_root / "source.mp4"
    source.parent.mkdir(parents=True)
    contents = b"known original"
    source.write_bytes(contents)
    _, completed_temporal, _ = _write_video_source_metadata(data_root, source, contents, "completed")
    active_temporal = data_root / "processing/video_fixture/temporal_index.json"
    active_temporal.parent.mkdir(parents=True)
    active_temporal.write_bytes(completed_temporal.read_bytes())

    detail = client.get("/api/videos/video_fixture/scenes/scene-hash-12").json()
    assert detail["original_video_available"] is False
    assert client.get("/api/media/video/video_fixture/source").status_code == 404


def test_original_video_verification_cache_invalidates_changed_file(audio_media_client, monkeypatch):
    client, data_root = audio_media_client
    source = data_root / "source.mp4"
    source.parent.mkdir(parents=True)
    contents = b"expected original"
    source.write_bytes(contents)
    _write_video_source_metadata(data_root, source, contents)
    read_count = 0
    original_open = Path.open

    def counted_open(path, *args, **kwargs):
        nonlocal read_count
        if path == source and args and args[0] == "rb":
            read_count += 1
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", counted_open)
    listing = client.get("/api/videos/video_fixture/scenes").json()
    assert listing[0]["original_video_available"] is True
    endpoint = listing[0]["original_video_endpoint"]
    assert client.get(endpoint, headers={"Range": "bytes=0-3"}).status_code == 206
    assert client.get(endpoint, headers={"Range": "bytes=4-7"}).status_code == 206
    assert read_count == 1
    original_stat = source.stat()
    source.write_bytes(b"X" * len(contents))
    os.utime(source, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns + 10_000_000))
    assert client.get(endpoint).status_code == 404
    assert client.get("/api/videos/video_fixture/scenes").json()[0]["original_video_available"] is False


@pytest.mark.parametrize("foreign", [False, True])
def test_original_video_similar_numeric_scene_respects_source_identity(audio_media_client, monkeypatch, foreign):
    client, data_root = audio_media_client
    source = data_root / "source.mp4"
    source.parent.mkdir(parents=True)
    contents = b"known original"
    source.write_bytes(contents)
    _, temporal_path, identity = _write_video_source_metadata(data_root, source, contents)
    temporal = json.loads(temporal_path.read_text(encoding="utf-8"))
    temporal["segments"] = [{"scene_id": 0, "start": 30, "end": 35},
                            {"scene_id": 1, "start": 0, "end": 1}]
    temporal_path.write_text(json.dumps(temporal), encoding="utf-8")

    class Engine:
        def search_similar_scene(self, **kwargs):
            return [{"payload": {"scene_id": 0, "video_id": "foreign" if foreign else identity}}]

    monkeypatch.setattr(scenes, "get_search_engine", lambda: Engine())
    response = client.get("/api/videos/video_fixture/scenes/1/similar")
    assert response.status_code == 200
    result = response.json()[0]
    assert result["original_video_available"] is (not foreign)
    assert result["original_video_endpoint"] == (None if foreign else "/api/media/video/video_fixture/source")


def test_original_video_unknown_or_path_shaped_dataset_is_unavailable(audio_media_client):
    client, data_root = audio_media_client
    assert client.get("/api/media/video/unknown/source").status_code == 404
    escaped_video_id = quote(r"..\..\outside", safe="")
    assert client.get(f"/api/media/video/{escaped_video_id}/source").status_code == 404
    assert not data_root.exists()


def test_original_video_explicit_configured_root_can_be_outside_epoch(audio_media_client, monkeypatch):
    client, data_root = audio_media_client
    approved = data_root.parent / "approved-imports"
    source = approved / "original.mp4"
    approved.mkdir()
    contents = b"approved external source"
    source.write_bytes(contents)
    _write_video_source_metadata(data_root, source, contents)
    monkeypatch.setattr(loaders, "_DEFAULT_MEDIA_ROOTS", (approved,))

    detail = client.get("/api/videos/video_fixture/scenes/scene-hash-12").json()
    assert detail["original_video_available"] is True
    assert client.get(detail["original_video_endpoint"]).content == contents


def test_original_video_changing_during_verification_is_unavailable_then_recovers(audio_media_client, monkeypatch):
    client, data_root = audio_media_client
    source = data_root / "source.mp4"
    source.parent.mkdir(parents=True)
    contents = b"source changes during verification"
    source.write_bytes(contents)
    _write_video_source_metadata(data_root, source, contents)
    original_open = Path.open
    changed = False

    class ChangingReader:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.handle.close()

        def read(self, size):
            nonlocal changed
            result = self.handle.read(size)
            if result and not changed:
                changed = True
                before = source.stat()
                os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns + 10_000_000))
            return result

    def changing_open(path, *args, **kwargs):
        handle = original_open(path, *args, **kwargs)
        if path == source and args and args[0] == "rb":
            return ChangingReader(handle)
        return handle

    monkeypatch.setattr(Path, "open", changing_open)
    first = client.get("/api/videos/video_fixture/scenes/scene-hash-12").json()
    assert first["original_video_available"] is False
    assert first["original_video_endpoint"] is None
    assert changed is True
    recovered = client.get("/api/videos/video_fixture/scenes/scene-hash-12").json()
    assert recovered["original_video_available"] is True
    assert client.get(recovered["original_video_endpoint"]).content == contents


@pytest.mark.parametrize("route", [
    "/api/media/video/video_fixture/source",
    "/api/videos/video_fixture/scenes",
    "/api/videos/video_fixture/scenes/scene-hash-12",
    "/api/videos/video_fixture/scenes/scene-hash-12/similar",
])
def test_original_video_verification_keeps_event_loop_responsive(audio_media_client, monkeypatch, route):
    _, data_root = audio_media_client
    source = data_root / "source.mp4"
    source.parent.mkdir(parents=True)
    contents = b"bounded original-video response fixture"
    source.write_bytes(contents)
    _write_video_source_metadata(data_root, source, contents)

    class Engine:
        def search_similar_scene(self, **kwargs):
            return [{"payload": {"scene_id": "scene-hash-12", "video_id": "video_fixture"}}]

    monkeypatch.setattr(scenes, "get_search_engine", lambda: Engine())
    resolve_original = loaders.DataLoader.get_original_video_path
    observed = []

    async def dispatch():
        loop = asyncio.get_running_loop()

        def blocking_verification(loader, video_id):
            heartbeat = threading.Event()
            loop.call_soon_threadsafe(heartbeat.set)
            # A cold large-source hash can take seconds. The loop must keep
            # servicing work while this synchronous resolver is still running.
            observed.append(heartbeat.wait(timeout=1))
            return resolve_original(loader, video_id)

        monkeypatch.setattr(loaders.DataLoader, "get_original_video_path", blocking_verification)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:30000") as client:
            response = await client.get(route)
        assert response.status_code == 200

    asyncio.run(dispatch())
    assert observed == [True], "Original verification blocked the API event loop"
