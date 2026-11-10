from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

from steps.video_scene_detect.step import video_scene_detect


def test_fallback_single_scene_uses_duration_probe(monkeypatch, tmp_path: Path):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"v")

    monkeypatch.setattr(
        "steps.video_scene_detect.step._detect_with_scenedetect",
        lambda *args, **kwargs: {"scenes": [], "duration": 0.0},
    )
    monkeypatch.setattr(
        "steps.video_scene_detect.step._probe_video_duration",
        lambda _path: 12.345,
    )

    result = video_scene_detect({"source_path": str(source)}, {})
    assert result["scene_meta"]["status"] == "fallback_single_scene"
    assert result["scenes"]
    assert result["scenes"][0]["start"] == 0.0
    assert result["scenes"][0]["end"] == 12.345
    assert result["scenes"][0]["duration"] == 12.345


def test_native_scene_caller_releases_opencv_capture_without_false_error(monkeypatch, tmp_path, capsys):
    """Installed VideoStreamCv2 exposes capture, not a release method."""
    source = tmp_path / "video.mp4"
    source.write_bytes(b"pixel decoding is intercepted for this caller regression")
    released = []
    video = SimpleNamespace(frame_rate=30.0, duration=12.0,
                            capture=SimpleNamespace(release=lambda: released.append(True)))
    start = SimpleNamespace(get_seconds=lambda: 0.0)
    end = SimpleNamespace(get_seconds=lambda: 12.0)
    manager = SimpleNamespace(add_detector=lambda _: None, detect_scenes=lambda _: None,
                              get_scene_list=lambda: [(start, end)])
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False)))
    monkeypatch.setitem(sys.modules, "scenedetect", SimpleNamespace(
        open_video=lambda _: video, SceneManager=lambda **_: manager,
        StatsManager=lambda: SimpleNamespace(get_metrics=lambda _: {})))
    monkeypatch.setitem(sys.modules, "scenedetect.detectors", SimpleNamespace(ContentDetector=lambda **_: object()))

    result = video_scene_detect({"source_path": str(source)}, {})

    assert result["scene_meta"]["status"] == "ok"
    assert result["scenes"][0]["end"] == 12.0
    assert released == [True]
    assert "[ERROR]" not in capsys.readouterr().out
