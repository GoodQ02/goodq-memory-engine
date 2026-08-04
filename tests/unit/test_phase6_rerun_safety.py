from __future__ import annotations

from pathlib import Path

from cli import run_ingestion
from steps.common import tool_paths
from steps.video import scene_frame_extractor


def test_step_timeout_defaults_to_builtin_when_omitted() -> None:
    assert run_ingestion._resolve_step_timeout_value(None) == run_ingestion.DEFAULT_STEP_TIMEOUT
    assert run_ingestion._resolve_step_timeout_value(45) == 45
    assert run_ingestion._resolve_step_timeout_value(0) is None


def test_merge_prior_phase6_manifest_state_preserves_existing_success() -> None:
    prior = {
        "phase6_complete": True,
        "phase6_status": "complete",
        "phase6_vector_commit": {"qdrant_ok": True},
        "embedding_stats": {"clip_scenes": 12},
        "scenes": [
            {
                "scene_id": "scene_0009",
                "index": 9,
                "frame_paths": ["frames/scene_0009_frame_00.jpg"],
                "representative_frame": "frames/scene_0009_frame_00.jpg",
                "clip_id": "clip_scene_video_9",
            }
        ],
    }
    new = {
        "video_id": "video_123",
        "scenes": [
            {
                "scene_id": "scene_0009",
                "index": 9,
                "start": 10.0,
                "end": 12.0,
            }
        ],
    }

    merged = run_ingestion._merge_prior_phase6_manifest_state(new, prior)

    assert merged["phase6_complete"] is True
    assert merged["phase6_status"] == "complete"
    assert merged["phase6_vector_commit"]["qdrant_ok"] is True
    assert merged["scenes"][0]["frame_paths"] == ["frames/scene_0009_frame_00.jpg"]
    assert merged["scenes"][0]["clip_id"] == "clip_scene_video_9"


def test_resolve_ffmpeg_accepts_directory_override(monkeypatch, tmp_path: Path) -> None:
    ffmpeg_dir = tmp_path / "ffmpeg_bin"
    ffmpeg_dir.mkdir()
    ffmpeg_exe = ffmpeg_dir / ("ffmpeg.exe" if tool_paths.os.name == "nt" else "ffmpeg")
    ffmpeg_exe.write_text("stub", encoding="utf-8")

    cfg = {"config": {"tools": {"ffmpeg_exe": f'"{ffmpeg_dir}"'}}}

    monkeypatch.setattr(tool_paths.shutil, "which", lambda *_args, **_kwargs: None)

    assert tool_paths.resolve_ffmpeg(cfg) == str(ffmpeg_exe)


def test_resolve_ffmpeg_uses_the_installed_bundled_runtime_before_imageio(monkeypatch, tmp_path: Path) -> None:
    bundled = tmp_path / ("ffmpeg.exe" if tool_paths.os.name == "nt" else "ffmpeg")
    bundled.write_text("stub", encoding="utf-8")

    monkeypatch.setattr(tool_paths.shutil, "which", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "steps.common.tool_resolver.ToolResolver.resolve_tool",
        lambda _name: {"found": True, "path": str(bundled)},
    )

    assert tool_paths.resolve_ffmpeg({}) == str(bundled)


def test_extract_frame_at_timestamp_reuses_existing_frame(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / "scene_0009_frame_00.jpg"
    output_path.write_bytes(b"existing-frame")

    def _unexpected_run(*_args, **_kwargs):
        raise AssertionError("subprocess.run should not be invoked for reusable frames")

    monkeypatch.setattr(scene_frame_extractor.subprocess, "run", _unexpected_run)

    ok = scene_frame_extractor.extract_frame_at_timestamp(
        video_path=str(tmp_path / "video.mp4"),
        timestamp=1.23,
        output_path=str(output_path),
        ffmpeg_exe="ffmpeg",
    )

    assert ok is True
    assert output_path.read_bytes() == b"existing-frame"
