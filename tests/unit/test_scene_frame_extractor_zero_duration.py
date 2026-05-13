from __future__ import annotations

from pathlib import Path

from steps.video.scene_frame_extractor import extract_frames_uniform


def test_extract_frames_uniform_zero_duration_falls_back_to_single_timestamp(
    monkeypatch, tmp_path: Path
):
    captured = {}

    def _fake_extract(video_path, timestamp, output_path, ffmpeg_exe, width=224, height=224):
        captured["timestamp"] = timestamp
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"frame")
        return True

    monkeypatch.setattr(
        "steps.video.scene_frame_extractor.extract_frame_at_timestamp",
        _fake_extract,
    )

    frames = extract_frames_uniform(
        video_path="demo.mp4",
        start=0.0,
        end=0.0,
        num_frames=3,
        output_dir=str(tmp_path),
        scene_id=0,
        ffmpeg_exe="ffmpeg",
    )

    assert len(frames) == 1
    assert frames[0]["timestamp"] == 0.0
    assert frames[0]["extraction_method"] == "uniform"
    assert captured["timestamp"] == 0.0
