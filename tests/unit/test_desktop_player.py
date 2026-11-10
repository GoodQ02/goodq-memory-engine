from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routes import media
from api.utils.loaders import DataLoader
from api.utils.desktop_player import DesktopPlayer, DesktopPlayerError, fit_window
from api.utils import desktop_player


class FakePlayer:
    def __init__(self):
        self.calls = []

    def status(self):
        return {"available": True, "state": "idle", "playback_id": None}

    def play(self, path, start, video_id, scene_id, window):
        self.calls.append((path, start, video_id, scene_id, window))
        return {"available": True, "state": "starting", "playback_id": "test-play"}

    def done(self, playback_id):
        self.calls.append(("done", playback_id))
        return {"available": True, "state": "stopped", "playback_id": playback_id}


@pytest.fixture
def desktop_client(tmp_path, monkeypatch):
    root = tmp_path / "data"
    source = root / "original.mp4"
    source.parent.mkdir()
    source.write_bytes(b"verified fixture bytes")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    folder = root / "processing" / "fixture"
    folder.mkdir(parents=True)
    record = {"video_id": digest, "video_hash": digest, "video_path": str(source),
              "segments": [{"scene_id": 0, "start": 36.57, "end": 40}]}
    for name in ("temporal_index.json", "scene_manifest.json"):
        (folder / name).write_text(json.dumps(record))
    player = FakePlayer()
    monkeypatch.setattr(media, "_data_loader", DataLoader(str(root), processing_root=str(root / "processing"), source_roots=[root]))
    monkeypatch.setattr(media, "get_desktop_player", lambda: player, raising=False)
    client = TestClient(app, base_url="http://127.0.0.1:30000", client=("127.0.0.1", 50000))
    return client, source, folder, player


def play(client, **overrides):
    body = {"video_id": "fixture", "scene_id": "0", **overrides}
    return client.post("/api/media/desktop-player/play", json=body,
                       headers={"Origin": "http://127.0.0.1:30000"})


def test_desktop_dispatch_uses_verified_source_and_persisted_scene_start(desktop_client):
    client, source, _, player = desktop_client
    response = play(client, window={"x": 20, "y": 30, "width": 440, "height": 300})
    assert response.status_code == 200
    assert response.json()["state"] == "starting"
    assert player.calls == [(source.resolve(), 36.57, "fixture", "0",
                             {"x": 20, "y": 30, "width": 440, "height": 300})]


@pytest.mark.parametrize("change", ["missing", "changed", "scene", "invalid_start"])
def test_desktop_invalid_source_or_scene_never_launches(desktop_client, change):
    client, source, folder, player = desktop_client
    body = {}
    if change == "missing":
        source.unlink()
    elif change == "changed":
        source.write_bytes(b"different")
    elif change == "scene":
        body["scene_id"] = "unknown"
    else:
        path = folder / "temporal_index.json"
        record = json.loads(path.read_text())
        record["segments"][0]["start"] = -1
        path.write_text(json.dumps(record))
    response = play(client, **body)
    assert response.status_code in (404, 422)
    assert player.calls == []


@pytest.mark.parametrize("extra", [{"path": "C:/untrusted.mp4"}, {"start": 1},
                                  {"window": {"x": 1, "y": 1, "width": 9000, "height": 300}}])
def test_desktop_rejects_client_media_arguments_and_invalid_geometry(desktop_client, extra):
    client, _, _, player = desktop_client
    assert play(client, **extra).status_code == 422
    assert player.calls == []


@pytest.mark.parametrize("origin", [None, "null", "https://other.invalid", "http://127.0.0.1:30001"])
def test_desktop_requires_same_origin(desktop_client, origin):
    client, _, _, player = desktop_client
    headers = {} if origin is None else {"Origin": origin}
    response = client.post("/api/media/desktop-player/play", json={"video_id": "fixture", "scene_id": "0"}, headers=headers)
    assert response.status_code == 403
    assert player.calls == []


def test_desktop_done_carries_exact_playback_identity(desktop_client):
    client, _, _, player = desktop_client
    response = client.post("/api/media/desktop-player/done", json={"playback_id": "test-play"},
                           headers={"Origin": "http://127.0.0.1:30000"})
    assert response.status_code == 200
    assert player.calls == [("done", "test-play")]


def test_desktop_status_is_passive(desktop_client):
    client, _, _, player = desktop_client
    assert client.get("/api/media/desktop-player/status").json()["available"] is True
    assert player.calls == []


def test_desktop_duplicate_scene_is_rejected(desktop_client):
    client, _, folder, player = desktop_client
    path = folder / "temporal_index.json"
    record = json.loads(path.read_text())
    record["segments"].append({"scene_id": "0", "start": 0})
    path.write_text(json.dumps(record))
    assert play(client).json()["detail"] == "Scene not found or ambiguous"
    assert player.calls == []


def test_desktop_backend_failure_is_reported_through_dispatch(desktop_client, monkeypatch):
    client, _, _, player = desktop_client
    def fail(*args):
        raise DesktopPlayerError("VLC did not become ready")
    monkeypatch.setattr(player, "play", fail)
    response = play(client)
    assert response.status_code == 503
    assert response.json()["detail"] == "VLC did not become ready"


def test_desktop_remote_play_never_launches(desktop_client):
    _, _, _, player = desktop_client
    client = TestClient(app, base_url="http://127.0.0.1:30000", client=("192.0.2.3", 50000))
    assert play(client).status_code == 403
    assert player.calls == []


class FakeNative:
    pid = 12345

    def __init__(self):
        self.running = True
        self.closed = 0
        self.minimized = 0
        self.plays = []
        self.shown = []
        self.rect = {"x": 12, "y": 34, "width": 500, "height": 350}
        self.data = {"state": "stopped"}
        self.read_error = None

    def alive(self):
        return self.running

    def play(self, path, start, token):
        self.plays.append((path, start, token))

    def read(self):
        if self.read_error:
            raise self.read_error
        return self.data

    def video(self, token, state="playing", frames=10, time=37, length=100):
        self.data = {"state": state, "time": time, "length": length,
                     "information": {"category": {"meta": {"title": f"GoodQ-{token}"}}},
                     "stats": {"decodedvideo": frames, "displayedpictures": frames}}

    def stop(self):
        self.data = {"state": "stopped"}

    def show(self, geometry):
        self.shown.append(geometry)

    def geometry(self):
        return self.rect

    def minimize(self):
        self.minimized += 1

    def close(self):
        self.running = False
        self.closed += 1


@pytest.fixture
def controller():
    children = []
    now = [0]
    def factory(_):
        child = FakeNative()
        children.append(child)
        return child
    player = DesktopPlayer(factory=factory, resolver=lambda: Path("vlc.exe"),
                           clock=lambda: now[0], idle_seconds=5, background=False)
    yield player, children, now
    player.close()


def accept(player, scene="scene"):
    return player.play(Path("fixture.mp4"), 36.57, "fixture", scene,
                       {"x": 1, "y": 2, "width": 440, "height": 300})["playback_id"]


def test_controller_status_never_starts_process(controller):
    player, children, _ = controller
    assert player.status()["state"] == "idle"
    assert children == []


def test_controller_waits_for_matching_video_frames(controller):
    player, children, now = controller
    token = accept(player)
    child = children[0]
    child.video("old-play", frames=999)
    player.tick()
    assert player.status()["state"] == "starting"
    child.video(token, frames=0)
    player.tick()
    assert player.status()["playing"] is False
    child.video(token, frames=12, time=0)
    player.tick()
    assert player.status()["state"] == "starting"
    child.video(token, frames=12)
    player.tick()
    assert player.status()["state"] == "playing"
    assert player.status()["displayed_video_frames"] == 12
    child.video(token, state="paused", frames=12)
    player.tick()
    now[0] = 999
    player.tick()
    assert player.status()["state"] == "paused"
    assert child.closed == 0


def test_controller_audio_only_or_unmatched_input_times_out(controller):
    player, children, now = controller
    token = accept(player)
    children[0].video(token, frames=0)
    now[0] = 16
    player.tick()
    assert player.status()["state"] == "error"
    assert player.status()["playing"] is False
    assert children[0].closed == 1


def test_controller_confirmed_video_can_seek_before_scene_without_start_timeout(controller):
    player, children, now = controller
    token = accept(player)
    child = children[0]
    child.video(token, time=37)
    player.tick()
    assert player.status()["state"] == "playing"
    child.video(token, time=3)
    now[0] = 30
    player.tick()
    assert player.status()["state"] == "playing"
    assert player.status()["time_seconds"] == 3
    assert child.closed == 0
    next_token = accept(player, "other")
    child.video(next_token, time=0)
    player.tick()
    assert player.status()["state"] == "starting"


def test_controller_reuses_own_window_and_preserves_user_geometry(controller):
    player, children, _ = controller
    old_token = accept(player)
    child = children[0]
    child.rect = {"x": 77, "y": 88, "width": 700, "height": 420}
    new_token = accept(player, "other")
    assert len(children) == 1
    assert old_token != new_token
    assert child.shown == [{"x": 1, "y": 2, "width": 440, "height": 300}, None]
    with pytest.raises(DesktopPlayerError, match="replaced"):
        player.done(old_token)
    assert child.minimized == 0
    player.done(new_token)
    assert child.minimized == 1
    assert player.status()["state"] == "stopped"


def test_controller_manual_exit_then_new_play_launches_fresh_owned_child(controller):
    player, children, _ = controller
    accept(player)
    player.tick()
    children[0].running = False
    player.tick()
    assert player.status()["state"] == "closed"
    accept(player)
    assert len(children) == 2
    assert children[1].shown == [children[0].rect]


def test_controller_stopped_minimizes_then_closes_only_after_idle_limit(controller):
    player, children, now = controller
    token = accept(player)
    child = children[0]
    child.video(token, time=99)
    player.tick()
    child.data = {"state": "stopped"}
    player.tick()
    assert player.status()["state"] == "stopped"
    assert child.minimized == 1
    now[0] = 4
    player.tick()
    assert child.running
    now[0] = 5
    player.tick()
    assert player.status()["state"] == "closed"
    assert not child.running


def test_controller_taskbar_resume_cancels_idle_expiry(controller):
    player, children, now = controller
    token = accept(player)
    child = children[0]
    player.done(token)
    now[0] = 4
    child.video(token)
    player.tick()
    now[0] = 10
    player.tick()
    assert child.closed == 0
    assert player.status()["state"] == "playing"


def test_controller_control_disconnect_is_visible_and_closes_owned_child(controller):
    player, children, _ = controller
    accept(player)
    children[0].read_error = OSError("disconnected")
    player.tick()
    assert player.status()["state"] == "error"
    assert "unavailable" in player.status()["error"]
    assert children[0].closed == 1


def test_controller_rejects_scene_start_outside_actual_duration(controller):
    player, children, _ = controller
    token = accept(player)
    children[0].video(token, length=20)
    player.tick()
    assert player.status()["state"] == "error"
    assert "timestamp" in player.status()["error"]
    assert children[0].closed == 1


def test_controller_missing_vlc_is_visible():
    player = DesktopPlayer(resolver=lambda: None, background=False)
    try:
        assert player.status()["available"] is False
        with pytest.raises(DesktopPlayerError, match="not installed"):
            accept(player)
    finally:
        player.close()


@pytest.mark.parametrize("geometry,area,expected", [
    ({"x": 32000, "y": -32000, "width": 440, "height": 300}, (0, 40, 1920, 1080),
     {"x": 1480, "y": 40, "width": 440, "height": 300}),
    ({"x": -1200, "y": 100, "width": 240, "height": 180}, (-1920, 0, 0, 1080),
     {"x": -1200, "y": 100, "width": 320, "height": 240}),
])
def test_first_window_fits_selected_monitor_workarea(geometry, area, expected):
    assert fit_window(geometry, area) == expected


def test_native_launch_isolates_windows_qt_settings_with_supported_portable_directory(tmp_path, monkeypatch):
    executable = tmp_path / "runtime" / "vlc.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"unmodified VLC executable fixture")
    launched = {}

    class Child:
        pid = 777
        exit_code = None

        def poll(self):
            return self.exit_code

        def wait(self, timeout):
            self.exit_code = 0

    def start(arguments, **kwargs):
        launched.update(arguments=arguments, **kwargs)
        return Child()

    monkeypatch.setenv("PATH", "existing-user-path")
    monkeypatch.setattr(desktop_player.subprocess, "Popen", start)
    monkeypatch.setattr(desktop_player.ctypes, "WinDLL", lambda *args, **kwargs: object())
    monkeypatch.setattr(desktop_player.NativeVLC, "_configure_window_api", lambda self: None)
    monkeypatch.setattr(desktop_player.NativeVLC, "read", lambda self: {"state": "stopped"})
    monkeypatch.setattr(desktop_player.NativeVLC, "_window", lambda self: None)
    native = desktop_player.NativeVLC(executable)
    try:
        copied_executable = Path(launched["arguments"][0])
        assert copied_executable != executable
        assert copied_executable.read_bytes() == executable.read_bytes()
        assert (copied_executable.parent / "portable").is_dir()
        assert Path(launched["cwd"]) == copied_executable.parent
        assert launched["env"]["PATH"].split(desktop_player.os.pathsep)[0] == str(executable.parent)
        assert desktop_player.os.environ["PATH"] == "existing-user-path"
    finally:
        native.close()
    assert not copied_executable.exists()
    assert executable.read_bytes() == b"unmodified VLC executable fixture"
