from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from steps.audio_transcribe.step import audio_transcribe


class _ModelContext:
    def __enter__(self):
        return object()

    def __exit__(self, *_args):
        return False


class _LifecycleManager:
    model_registry = {"faster_whisper_small": {}}

    def __init__(self, _cfg):
        pass

    def load(self, *_args, **_kwargs):
        return _ModelContext()


def _run_transcription(monkeypatch, tmp_path: Path, results: list[dict | None]):
    source = tmp_path / "source.wav"
    source.write_bytes(b"RIFF")
    chunks = [
        {"start": float(index * 10), "end": float(index * 10 + 10), "speaker": None}
        for index in range(len(results))
    ]

    monkeypatch.setattr("steps.audio_transcribe.step.require_wsl_audio", lambda: False)
    monkeypatch.setattr("steps.audio_transcribe.step.is_baseline", lambda: True)
    monkeypatch.setattr("steps.audio_transcribe.step.require_gpu", lambda: False)
    monkeypatch.setattr("steps.audio_transcribe.step._audio_duration", lambda _path: float(len(chunks) * 10))
    monkeypatch.setattr("steps.audio_transcribe.step._build_chunks", lambda *_args: chunks)
    monkeypatch.setattr("lib.model_lifecycle.ModelLifecycleManager", _LifecycleManager)
    monkeypatch.setattr(
        "steps.common.model_provisioner.ensure_model_cached",
        lambda *_args, **_kwargs: SimpleNamespace(status="ready", local_path=str(tmp_path / "model")),
    )

    chunk_paths = []
    for index in range(len(results)):
        chunk = tmp_path / f"chunk-{index}.wav"
        chunk.write_bytes(b"RIFF")
        chunk_paths.append(chunk)
    monkeypatch.setattr("steps.audio_transcribe.step._slice_to_wav", lambda *_args: str(chunk_paths.pop(0)))
    monkeypatch.setattr("steps.audio_transcribe.step._transcribe_chunk_fw", lambda *_args: results.pop(0))

    return audio_transcribe(
        {"source_path": str(source)},
        {"audio": {"transcribe": {"use_wsl2": False, "model": "small"}}},
    )


def test_empty_tail_chunk_is_explicitly_nonerror_when_transcript_exists(monkeypatch, tmp_path: Path):
    result = _run_transcription(
        monkeypatch,
        tmp_path,
        [
            {"transcript": "Hello there", "segments": [], "engine": "faster-whisper"},
            {"transcript": "", "segments": [], "engine": "faster-whisper"},
        ],
    )

    meta = result["transcript_meta"]

    assert result["transcript"] == "Hello there"
    assert meta["status"] == "ok"
    assert meta["reason"] == "transcript_available"
    assert meta["chunks"][1]["status"] == "empty"
    assert meta["chunks"][1]["reason"] == "no_speech_detected"
    assert meta["chunks"][1]["error"] is None


def test_chunk_execution_error_marks_nonempty_transcript_partial(monkeypatch, tmp_path: Path):
    result = _run_transcription(
        monkeypatch,
        tmp_path,
        [
            {"transcript": "Hello there", "segments": [], "engine": "faster-whisper"},
            None,
        ],
    )

    meta = result["transcript_meta"]

    assert result["transcript"] == "Hello there"
    assert meta["status"] == "partial"
    assert meta["reason"] == "transcript_available_with_chunk_errors"
    assert meta["chunks"][1]["status"] == "error"
    assert meta["chunks"][1]["reason"] == "transcription_backend_no_result"
    assert meta["chunks"][1]["error"] == "transcribe_failed"


def test_missing_source_has_a_terminal_explainable_transcript_receipt(tmp_path: Path):
    result = audio_transcribe(
        {"source_path": str(tmp_path / "missing.wav")},
        {"audio": {"transcribe": {"use_wsl2": False}}},
    )

    meta = result["transcript_meta"]

    assert meta["status"] == "no_file"
    assert meta["reason"] == "source_file_missing"
    assert meta["error"] == "source_file_missing"
    assert meta["engine"] == "hybrid_whisper"
    assert meta["device"] == "none"
