"""Real decoder controls; all media and outputs are disposable generated files."""

from copy import deepcopy
from fractions import Fraction
import hashlib
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
import wave

import pytest

from wsl2_audio import recording_audio as recording
from wsl2_audio.source_clock import SampleSpan


@pytest.fixture(scope="module")
def ffmpeg():
    from steps.common.tool_paths import resolve_ffmpeg

    binary = resolve_ffmpeg({})
    if not binary:
        pytest.skip("FFmpeg is required for the real decoder controls")
    probe = Path(binary).with_name("ffprobe.exe" if Path(binary).suffix == ".exe" else "ffprobe")
    if not probe.is_file() and not shutil.which("ffprobe"):
        pytest.skip("FFprobe is required for the real decoder controls")
    return binary


def write_pcm(path, samples, rate=16000, channels=1):
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(channels)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return path


def write_float(path, samples):
    data = struct.pack(f"<{len(samples)}f", *samples)
    fmt = struct.pack("<HHIIHH", 3, 1, 16000, 64000, 4, 32)
    path.write_bytes(b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt "
                     + struct.pack("<I", 16) + fmt + b"data" + struct.pack("<I", len(data)) + data)
    return path


def request(path, ffmpeg):
    return {
        "source_path": str(path),
        "config": {"config": {"tools": {"ffmpeg_exe": ffmpeg}}},
        "fingerprint": {
            "source_revision": "generated-test", "worker_sha256": "a" * 64,
            "config_sha256": "b" * 64, "models": [],
            "window": {"core_samples": 16000, "context_samples": 8000},
        },
        "limits": {"max_pcm_bytes": 10 * 1024 * 1024, "timeout_seconds": 20},
    }


@pytest.mark.parametrize("rate,count", [(44100, 101), (48000, 80001), (16000, 1)])
def test_decode_preserves_exact_samples_and_short_tail(tmp_path, ffmpeg, rate, count):
    original = [123] * (count - 1) + [1]
    source = write_pcm(tmp_path / "source.wav", original, rate)
    result = recording.prepare_recording(request(source, ffmpeg), tmp_path / "artifacts")
    assert result["status"] == "ok"
    assert result["source"]["sample_rate"] == rate
    assert result["source"]["sample_count"] == count
    assert result["source"]["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    values = recording.read_channel(result, SampleSpan(0, count), 0)
    assert list(values) == [value / 32768 for value in original]
    assert result["decode"]["transform"] == "preserve_rate_and_channels_f64le"


def test_opposing_channels_are_preserved_instead_of_cancelled(tmp_path, ffmpeg):
    source = write_pcm(tmp_path / "stereo.wav", [3276, -3276] * 101, channels=2)
    result = recording.prepare_recording(request(source, ffmpeg), tmp_path / "artifacts")
    assert result["source"]["channels"] == 2
    assert result["decode"]["digital_silence"] is False
    assert list(recording.read_channel(result, SampleSpan(0, 101), 0)) == [3276 / 32768] * 101
    assert list(recording.read_channel(result, SampleSpan(0, 101), 1)) == [-3276 / 32768] * 101


@pytest.mark.parametrize("value,is_silent", [(0.0, True), (1e-12, False)])
def test_quiet_float_is_not_quantized_into_digital_silence(tmp_path, ffmpeg, value, is_silent):
    source = write_float(tmp_path / "quiet.wav", [value] * 101)
    result = recording.prepare_recording(request(source, ffmpeg), tmp_path / "artifacts")
    assert result["decode"]["digital_silence"] is is_silent
    if not is_silent:
        assert all(value != 0 for value in recording.read_channel(result, SampleSpan(0, 101), 0))


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_nonfinite_samples_are_decode_error_not_silence(tmp_path, ffmpeg, value):
    source = write_float(tmp_path / "bad.wav", [value] * 10)
    with pytest.raises(recording.RecordingError, match="nonfinite_pcm"):
        recording.prepare_recording(request(source, ffmpeg), tmp_path / "artifacts")
    assert not list((tmp_path / "artifacts").rglob("recording.json"))


@pytest.mark.parametrize("kind", ["empty", "corrupt"])
def test_empty_and_corrupt_media_are_errors(tmp_path, ffmpeg, kind):
    source = tmp_path / "source.wav"
    if kind == "empty":
        write_pcm(source, [])
    else:
        source.write_bytes(b"not a media file")
    with pytest.raises(recording.RecordingError):
        recording.prepare_recording(request(source, ffmpeg), tmp_path / "artifacts")


def test_video_with_no_audio_is_supported_absence(tmp_path, ffmpeg):
    source = tmp_path / "silent_video.mkv"
    subprocess.run([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                    "-i", "color=s=16x16:r=1", "-frames:v", "1", "-c:v", "ffv1", "-an", str(source)],
                   check=True, capture_output=True, timeout=20)
    result = recording.prepare_recording(request(source, ffmpeg), tmp_path / "artifacts")
    assert result["status"] == "not_applicable"
    assert result["reason"] == "audio_track_absent"
    assert result["pcm"] is None


def test_container_origin_is_retained_without_leading_silence(tmp_path, ffmpeg):
    wav = write_pcm(tmp_path / "original.wav", [32] * 1001, rate=48000)
    source = tmp_path / "offset.nut"
    subprocess.run([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-copyts",
                    "-itsoffset", "1.25", "-i", str(wav), "-c:a", "pcm_s16le", str(source)],
                   check=True, capture_output=True, timeout=20)
    result = recording.prepare_recording(request(source, ffmpeg), tmp_path / "artifacts")
    assert result["source"]["sample_count"] == 1001
    clock = result["source"]
    assert abs(Fraction(clock["origin_num"], clock["origin_den"]) - Fraction(5, 4)) <= Fraction(1, 48000)


def test_matching_checkpoint_is_validated_without_decoding_again(tmp_path, ffmpeg, monkeypatch):
    source = write_pcm(tmp_path / "source.wav", [10] * 101)
    req = request(source, ffmpeg)
    first = recording.prepare_recording(req, tmp_path / "artifacts")
    monkeypatch.setattr(recording, "_decode", lambda *a, **k: pytest.fail("matching decode was repeated"))
    cached = recording.prepare_recording(req, tmp_path / "artifacts")
    assert cached["cache_hit"] is True
    assert first["source"] == cached["source"]
    assert first["checkpoint_key"] == cached["checkpoint_key"]


@pytest.mark.parametrize("changed", ["input", "worker", "config", "model", "window", "revision", "decode"])
def test_changed_immutable_identity_never_reuses_checkpoint(tmp_path, ffmpeg, changed):
    source = write_pcm(tmp_path / "source.wav", [10] * 101)
    req = request(source, ffmpeg)
    first = recording.prepare_recording(req, tmp_path / "artifacts")
    req = deepcopy(req)
    if changed == "input":
        write_pcm(source, [11] * 101)
    elif changed in {"worker", "config"}:
        req["fingerprint"][changed + "_sha256"] = "c" * 64
    elif changed == "model":
        req["fingerprint"]["models"] = [{"id": "test", "revision": "test", "sha256": "d" * 64}]
    elif changed == "window":
        req["fingerprint"]["window"]["context_samples"] = 4000
    elif changed == "revision":
        req["fingerprint"]["source_revision"] = "changed"
    else:
        req["audio_stream_index"] = 0
    second = recording.prepare_recording(req, tmp_path / "artifacts")
    assert second["cache_hit"] is False
    assert second["checkpoint_key"] != first["checkpoint_key"]


def test_corrupt_cached_pcm_is_not_a_cache_hit(tmp_path, ffmpeg):
    source = write_pcm(tmp_path / "source.wav", [10] * 101)
    req = request(source, ffmpeg)
    first = recording.prepare_recording(req, tmp_path / "artifacts")
    Path(first["pcm"]["path"]).write_bytes(b"corrupt")
    with pytest.raises(recording.RecordingError, match="checkpoint_invalid"):
        recording.prepare_recording(req, tmp_path / "artifacts")


def test_decode_budget_failure_does_not_publish_partial_success(tmp_path, ffmpeg):
    source = write_pcm(tmp_path / "source.wav", [10] * 2000)
    req = request(source, ffmpeg)
    req["limits"]["max_pcm_bytes"] = 16
    with pytest.raises(recording.RecordingError, match="pcm_byte_budget"):
        recording.prepare_recording(req, tmp_path / "artifacts")
    assert not list((tmp_path / "artifacts").rglob("recording.json"))


def test_timeline_discontinuity_is_not_silently_stitched():
    timeline = recording.DecodeTimeline(sample_rate=16000, channels=1, time_base=Fraction(1, 16000))
    timeline.add(0, 32000, 160, 16000, 1)
    with pytest.raises(recording.RecordingError, match="timestamp_discontinuity"):
        timeline.add(1, 32400, 160, 16000, 1)


def test_timeline_uses_container_precision_without_accumulating_drift():
    timeline = recording.DecodeTimeline(sample_rate=44100, channels=1, time_base=Fraction(1, 1000))
    timeline.add(0, 0, 1024, 44100, 1)
    timeline.add(1, 1014, 1024, 44100, 1)
    timeline.add(2, 2030, 1024, 44100, 1)
    assert timeline.samples == 3072
    with pytest.raises(recording.RecordingError, match="timestamp_discontinuity"):
        timeline.add(3, 3020, 1024, 44100, 1)


def test_interrupted_evidence_write_preserves_preexisting_complete_artifact(tmp_path, monkeypatch):
    from tests.unit.test_audio_engine_evidence import evidence

    destination = tmp_path / "evidence.json"
    payload = evidence()
    expected = recording.publish_audio_artifact(payload, destination)
    original = destination.read_bytes()
    assert hashlib.sha256(original).hexdigest() == expected

    def interrupted(*args):
        raise OSError("injected publication interruption")

    monkeypatch.setattr(recording.os, "replace", interrupted)
    payload["provenance"]["run_id"] = "next-run"
    with pytest.raises(OSError, match="interruption"):
        recording.publish_audio_artifact(payload, destination)
    assert destination.read_bytes() == original
    assert not list(tmp_path.glob("*.tmp"))


def test_invalid_evidence_is_never_published(tmp_path):
    with pytest.raises(ValueError):
        recording.publish_audio_artifact({"schema_version": 999}, tmp_path / "invalid.json")
    assert not (tmp_path / "invalid.json").exists()


def test_decoder_interruption_leaves_no_reusable_checkpoint_and_can_resume(tmp_path, ffmpeg, monkeypatch):
    source = write_pcm(tmp_path / "source.wav", [10] * 101)
    req = request(source, ffmpeg)
    actual_decode = recording._decode

    def interrupted(source, binary, stream, destination, *args):
        Path(destination).write_bytes(b"partial")
        raise recording.RecordingError("injected_worker_death")

    monkeypatch.setattr(recording, "_decode", interrupted)
    with pytest.raises(recording.RecordingError, match="injected_worker_death"):
        recording.prepare_recording(req, tmp_path / "artifacts")
    assert not list((tmp_path / "artifacts").rglob("recording.json"))
    assert not list((tmp_path / "artifacts").rglob("*.tmp"))
    monkeypatch.setattr(recording, "_decode", actual_decode)
    result = recording.prepare_recording(req, tmp_path / "artifacts")
    assert result["status"] == "ok"
    assert result["cache_hit"] is False


def test_owned_process_timeout_is_bounded():
    started = time.monotonic()
    with pytest.raises(recording.RecordingError, match="decode_timeout"):
        recording._run_process([sys.executable, "-c", "import time; time.sleep(10)"],
                               0.15, lambda value: None, lambda value: None)
    assert time.monotonic() - started < 3


def test_changed_source_during_absence_probe_is_not_published(tmp_path, ffmpeg, monkeypatch):
    source = tmp_path / "no_audio.mkv"
    source.write_bytes(b"original")

    def changed(*args):
        source.write_bytes(b"changed")
        return [{"index": 0, "codec_type": "video"}]

    monkeypatch.setattr(recording, "_probe", changed)
    with pytest.raises(recording.RecordingError, match="source_changed"):
        recording.prepare_recording(request(source, ffmpeg), tmp_path / "artifacts")
    assert not list((tmp_path / "artifacts").rglob("recording.json"))


@pytest.mark.parametrize("suffix", [".ffconcat", ".wav"])
def test_external_reference_input_cannot_create_a_single_source_checkpoint(tmp_path, ffmpeg, suffix):
    write_pcm(tmp_path / "segment.wav", [10] * 101)
    descriptor = tmp_path / ("recording" + suffix)
    descriptor.write_text("ffconcat version 1.0\nfile 'segment.wav'\n", encoding="utf-8")
    with pytest.raises(recording.RecordingError, match="probe_failed"):
        recording.prepare_recording(request(descriptor, ffmpeg), tmp_path / "artifacts")
    assert not list((tmp_path / "artifacts").rglob("recording.json"))


@pytest.mark.parametrize("suffix", [".wav", ".mov"])
def test_recording_probe_does_not_apply_mov_options_to_wav_content(tmp_path, ffmpeg, monkeypatch, suffix):
    source = write_pcm(tmp_path / ("source" + suffix), [123] * 101)
    run_process = recording._run_process

    def older_probe(argv, timeout, stdout_sink, stderr_sink):
        # FFprobe 4.3 rejects unused demuxer options after identifying WAV,
        # even when a misleading file suffix says MOV.
        if "-show_entries" in argv and "-enable_drefs" in argv:
            stderr_sink(b"Option enable_drefs not found.\n")
            return 1
        assert argv[argv.index("-protocol_whitelist") + 1] == "file,pipe"
        assert argv[argv.index("-format_whitelist") + 1] == recording.SELF_CONTAINED_FORMATS
        return run_process(argv, timeout, stdout_sink, stderr_sink)

    monkeypatch.setattr(recording, "_run_process", older_probe)
    result = recording.prepare_recording(request(source, ffmpeg), tmp_path / "artifacts")
    assert list(recording.read_channel(result, SampleSpan(0, 101), 0)) == [123 / 32768] * 101


def test_self_contained_mov_remains_supported_with_external_tracks_disabled(tmp_path, ffmpeg, monkeypatch):
    source = write_pcm(tmp_path / "source.wav", [123] * 1001, rate=48000)
    container = tmp_path / "source.mov"
    subprocess.run([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(source),
                    "-c:a", "pcm_s16le", str(container)], check=True, capture_output=True, timeout=20)
    run_process, calls = recording._run_process, []

    def capture(argv, *args):
        calls.append(argv)
        return run_process(argv, *args)

    monkeypatch.setattr(recording, "_run_process", capture)
    result = recording.prepare_recording(request(container, ffmpeg), tmp_path / "artifacts")
    assert list(recording.read_channel(result, SampleSpan(0, 1001), 0)) == [123 / 32768] * 1001
    probe, decode = calls
    assert "-enable_drefs" not in probe
    assert decode[decode.index("-enable_drefs") + 1] == "0"
    assert decode[decode.index("-use_absolute_path") + 1] == "0"
