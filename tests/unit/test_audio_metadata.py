from __future__ import annotations

import json
import os
import subprocess
import wave
from pathlib import Path
from unittest.mock import patch

import pytest

from steps.audio_metadata import step
from steps.common.tool_resolver import ToolResolver


@pytest.fixture(autouse=True)
def preserve_process_environment():
    # Production caller imports may resolve host policy into this process.
    # Keep that real behavior scoped to this test rather than leaking to peers.
    with patch.dict(os.environ, dict(os.environ)):
        yield


def _empty_wav(path: Path) -> Path:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\0\0" * 160)
    return path


def test_tagged_video_date_survives_extraction_dispatch_and_time_hint_projection(tmp_path, monkeypatch):
    from cli import run_ingestion, step_runner
    from steps.video.cross_modal_harmonizer import _resolve_scene_metadata_time_hints

    ffmpeg = ToolResolver.resolve_tool("ffmpeg")
    ffprobe = ToolResolver.resolve_tool("ffprobe")
    if not ffmpeg.get("found") or not ffprobe.get("found"):
        pytest.skip("existing local FFmpeg and ffprobe are required for the extraction witness")
    source = tmp_path / "tagged-source.mp4"
    generated = subprocess.run([
        ffmpeg["path"], "-nostdin", "-v", "error", "-f", "lavfi", "-i",
        "color=c=black:s=16x16:r=1:d=1", "-f", "lavfi", "-i",
        "anullsrc=r=16000:cl=mono", "-t", "1", "-c:v", "mpeg4",
        "-c:a", "aac", "-metadata", "date=2001-12-16", str(source),
    ], check=False, capture_output=True, timeout=15)
    assert generated.returncode == 0, generated.stderr
    monkeypatch.setattr(run_ingestion, "_observer", lambda: None)
    chunk = run_ingestion._extract_audio_chunk(
        ffmpeg["path"], source, {"index": 0, "start": 0, "end": 1}, tmp_path / "chunks",
        scene_id="fixture-scene", video_id="fixture-video",
    )
    for media in (source, chunk):
        probe = subprocess.run([
            ffprobe["path"], "-v", "error", "-show_entries", "format_tags", "-of", "json", str(media),
        ], check=True, capture_output=True, text=True, timeout=10)
        assert json.loads(probe.stdout)["format"]["tags"]["date"] == "2001-12-16"

    payload = step_runner.run_step("audio_metadata", {"source_path": str(chunk)}, {})
    run_ingestion._promote_metadata_time_hints(payload)
    hints = _resolve_scene_metadata_time_hints(payload)
    assert hints["normalized"] == ["2001-12-16"]
    assert hints["raw"]["date"] == "2001-12-16"
    assert payload["audio_meta"]["created_utc"][:10] != "2001-12-16"
    assert payload["audio_meta"]["tag_reader"]["source"] == "container_tags"


def test_untagged_wav_file_times_do_not_become_recording_dates(tmp_path):
    from cli.step_runner import run_step
    from cli.run_ingestion import _promote_metadata_time_hints
    from steps.video.cross_modal_harmonizer import _resolve_scene_metadata_time_hints

    payload = run_step("audio_metadata", {"source_path": str(_empty_wav(tmp_path / "untagged.wav"))}, {})
    _promote_metadata_time_hints(payload)
    assert payload["audio_meta"]["created_utc"]
    assert payload["audio_meta"]["modified_utc"]
    assert "tag_time_hints" not in payload["audio_meta"]
    assert _resolve_scene_metadata_time_hints(payload) == {}


@pytest.mark.parametrize("failure", ["missing", "exit", "timeout", "malformed"])
def test_wav_tag_probe_failure_is_visible_without_inventing_dates(tmp_path, monkeypatch, failure):
    from cli.step_runner import run_step

    path = _empty_wav(tmp_path / "source.wav")
    monkeypatch.setattr(step, "_mutagen_tags", lambda _: {})
    monkeypatch.setattr(step, "_probe_audio", lambda _: {"sample_rate": 16000})
    monkeypatch.setattr(ToolResolver, "resolve_tool", lambda _: {
        "found": failure != "missing", "path": "ffprobe",
    })

    def failed_probe(command, **kwargs):
        assert kwargs["timeout"] == 10
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 10)
        return subprocess.CompletedProcess(command, 1 if failure == "exit" else 0, stdout="not JSON")

    monkeypatch.setattr(step.subprocess, "run", failed_probe)
    meta = run_step("audio_metadata", {"source_path": str(path)}, {})["audio_meta"]
    assert meta["tag_reader"]["status"] == ("unavailable" if failure == "missing" else "error")
    assert meta["tag_reader"]["reason"]
    assert meta["created_utc"]
    assert meta["sample_rate"] == 16000
    assert "tag_time_hints" not in meta


def test_existing_mutagen_date_does_not_require_ffprobe(tmp_path, monkeypatch):
    from cli.step_runner import run_step

    path = _empty_wav(tmp_path / "source.wav")
    prior = {"tags": {"date": "1999-05-01"},
             "tag_time_hints": {"raw": {"date": "1999-05-01"}, "normalized": ["1999-05-01"]}}
    monkeypatch.setattr(step, "_mutagen_tags", lambda _: dict(prior))
    monkeypatch.setattr(step, "_probe_audio", lambda _: {})
    monkeypatch.setattr(step, "_ffprobe_wav_tags", lambda _: pytest.fail("existing date re-probed"))
    meta = run_step("audio_metadata", {"source_path": str(path)}, {})["audio_meta"]
    assert meta["tag_time_hints"] == prior["tag_time_hints"]
    assert meta["tag_reader"]["engine"] == "mutagen"


def test_wav_fallback_preserves_existing_nondate_tags(tmp_path, monkeypatch):
    from cli.step_runner import run_step

    path = _empty_wav(tmp_path / "source.wav")
    monkeypatch.setattr(step, "_mutagen_tags", lambda _: {"tags": {"artist": "Existing artist"}})
    monkeypatch.setattr(step, "_probe_audio", lambda _: {})
    monkeypatch.setattr(ToolResolver, "resolve_tool", lambda _: {"found": True, "path": "ffprobe"})
    monkeypatch.setattr(step.subprocess, "run", lambda command, **_: subprocess.CompletedProcess(
        command, 0, stdout=json.dumps({"format": {"tags": {"date": "2001-12-16", "artist": "Other"}}}),
    ))
    meta = run_step("audio_metadata", {"source_path": str(path)}, {})["audio_meta"]
    assert meta["tags"] == {"date": "2001-12-16", "artist": "Existing artist"}
    assert meta["tag_time_hints"]["normalized"] == ["2001-12-16"]
