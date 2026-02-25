from __future__ import annotations

from pathlib import Path

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
