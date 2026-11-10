"""Bounded source decode and immutable run artifacts for the candidate engine.

No VAD, resampling, downmix, model loading, service or persistence decisions live
here. Raw interleaved float64 avoids RIFF size limits and integer quantization.
"""

from array import array
from collections import deque
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

from wsl2_audio.evidence_contract import validate_evidence
from wsl2_audio.source_clock import SampleSpan, SourceClock


# A descriptor's hash cannot bind external segment bytes. Do not admit playlist,
# concatenation or linked-track inputs to a single-file source identity.
SELF_CONTAINED_FORMATS = "wav,flac,mp3,ogg,mov,mp4,m4a,3gp,3g2,mj2,matroska,webm,avi,mpeg,mpegts,nut,aiff,asf,aac"


def _input_options(*, mov_options=False):
    options = ["-protocol_whitelist", "file,pipe", "-format_whitelist", SELF_CONTAINED_FORMATS]
    if mov_options:
        options.extend(["-enable_drefs", "0", "-use_absolute_path", "0"])
    return options


class RecordingError(ValueError):
    """A declared decode/checkpoint failure, never supported audio absence."""

    def __init__(self, code, detail=""):
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


def _json_bytes(value):
    return (json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _positive_integer(value, name):
    if type(value) is not int or value <= 0:
        raise RecordingError("invalid_request", f"{name} must be a positive integer")
    return value


def _atomic_json(payload, path):
    contents = _json_bytes(payload)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return hashlib.sha256(contents).hexdigest()


def publish_audio_artifact(payload: dict, path: Path) -> str:
    """Validate evidence before atomic publication; return the published hash."""
    return _atomic_json(validate_evidence(payload), path)


def _run_process(argv, timeout, stdout_sink, stderr_sink):
    """Drain both pipes in fixed buffers and terminate the owned child on failure."""
    process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, creationflags=(
                                   subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0))
    failures = []

    def pump(pipe, sink):
        try:
            while block := pipe.read(65536):
                sink(block)
        except Exception as exc:
            failures.append(exc)
            process.kill()
        finally:
            pipe.close()

    readers = [threading.Thread(target=pump, args=(process.stdout, stdout_sink), daemon=True),
               threading.Thread(target=pump, args=(process.stderr, stderr_sink), daemon=True)]
    for reader in readers:
        reader.start()
    try:
        result = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.wait()
        raise RecordingError("decode_timeout", f"budget={timeout:g}s") from exc
    finally:
        for reader in readers:
            reader.join(timeout=3)
    if any(reader.is_alive() for reader in readers):
        raise RecordingError("decode_pipe_failure", "owned process did not close its streams")
    if failures:
        raise failures[0]
    return result


def _probe(source, binary, timeout):
    output, errors = bytearray(), bytearray()

    def append_bounded(destination, block):
        if len(destination) + len(block) > 1024 * 1024:
            raise RecordingError("probe_output_budget")
        destination.extend(block)

    # The demuxer is not known yet. Older ffprobe rejects MOV-only options
    # when the input is WAV or another format. MOV external references are
    # disabled by default; _decode also sets those options explicitly once
    # probing has identified a MOV container. Keep the common restrictions.
    code = _run_process([
        str(binary), "-v", "error", *_input_options(), "-show_entries",
        "stream=index,codec_type,codec_name,sample_rate,channels,channel_layout,time_base,start_pts:format=format_name",
        "-of", "json", str(source),
    ], timeout, lambda block: append_bounded(output, block), lambda block: append_bounded(errors, block))
    if code:
        raise RecordingError("probe_failed", errors.decode("utf-8", errors="replace")[-4096:])
    try:
        result = json.loads(output)
        if not isinstance(result.get("streams"), list) or not result["streams"]:
            raise ValueError("no media streams")
        format_name = result["format"]["format_name"]
        for stream in result["streams"]:
            stream["container_format"] = format_name
        return result["streams"]
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise RecordingError("invalid_probe_result", str(exc)) from exc


@dataclass
class DecodeTimeline:
    """Check decoded frames against one anchor; never accumulate PTS jitter."""

    sample_rate: int
    channels: int
    time_base: Fraction
    frames: int = 0
    samples: int = 0
    first_pts: int | None = None
    max_residual_samples: int = 0

    def __post_init__(self):
        _positive_integer(self.sample_rate, "sample_rate")
        _positive_integer(self.channels, "channels")
        if self.time_base <= 0:
            raise RecordingError("invalid_time_base")

    @property
    def timestamp_precision_samples(self):
        return max(1, math.ceil(self.time_base * self.sample_rate))

    def add(self, index, pts, count, rate, channels):
        if (index != self.frames or type(pts) is not int or type(count) is not int or count <= 0
                or rate != self.sample_rate or channels != self.channels):
            raise RecordingError("decode_format_changed", "frame order/rate/channels/count mismatch")
        if self.first_pts is None:
            self.first_pts = pts
        residual = abs(pts - self.first_pts - self.samples)
        if residual > self.timestamp_precision_samples:
            raise RecordingError("timestamp_discontinuity", f"frame={index}, residual_samples={residual}")
        self.max_residual_samples = max(self.max_residual_samples, residual)
        self.samples += count
        self.frames += 1


def _decode(source, binary, stream_info, destination, byte_budget, timeout):
    rate, channels = int(stream_info["sample_rate"]), int(stream_info["channels"])
    timeline = DecodeTimeline(rate, channels, Fraction(stream_info["time_base"]))
    diagnostic_tail = deque(maxlen=8)
    line_buffer, sample_buffer = bytearray(), bytearray()
    total_bytes = 0
    channel_peak = [0.0] * channels
    digest = hashlib.sha256()
    frame_bytes = channels * 8

    def stderr(block):
        line_buffer.extend(block)
        while b"\n" in line_buffer:
            raw, _, remainder = line_buffer.partition(b"\n")
            line_buffer[:] = remainder
            if len(raw) > 16384:
                raise RecordingError("decode_diagnostic_budget")
            line = raw.decode("utf-8", errors="replace").strip()
            if "ashowinfo" in line and "nb_samples:" in line:
                fields = dict(re.findall(r"\b(n|pts|rate|channels|nb_samples):([^\s]+)", line))
                try:
                    values = [int(fields[key]) for key in ("n", "pts", "nb_samples", "rate", "channels")]
                except (KeyError, ValueError) as exc:
                    raise RecordingError("invalid_frame_clock", line[-1024:]) from exc
                timeline.add(*values)
            elif line:
                diagnostic_tail.append(line[-1024:])
        if len(line_buffer) > 16384:
            raise RecordingError("decode_diagnostic_budget")

    with Path(destination).open("wb") as output:
        def stdout(block):
            nonlocal total_bytes
            total_bytes += len(block)
            if total_bytes > byte_budget:
                raise RecordingError("pcm_byte_budget", f"maximum={byte_budget}")
            sample_buffer.extend(block)
            complete_bytes = len(sample_buffer) // frame_bytes * frame_bytes
            if complete_bytes:
                data = bytes(sample_buffer[:complete_bytes])
                del sample_buffer[:complete_bytes]
                values = array("d")
                values.frombytes(data)
                if sys.byteorder != "little":
                    values.byteswap()
                for index, value in enumerate(values):
                    if not math.isfinite(value):
                        raise RecordingError("nonfinite_pcm")
                    channel = index % channels
                    channel_peak[channel] = max(channel_peak[channel], abs(value))
                digest.update(data)
                output.write(data)

        code = _run_process([
            str(binary), "-nostdin", "-hide_banner", "-nostats", "-loglevel", "info", "-xerror",
            "-threads", "1", *_input_options(mov_options="mov" in stream_info.get("container_format", "").split(",")),
            "-copyts", "-i", str(source),
            "-map", f"0:{stream_info['index']}", "-vn", "-sn", "-dn", "-threads", "1",
            "-af", "aformat=sample_fmts=dbl,asettb=expr=1/sr,ashowinfo",
            "-c:a", "pcm_f64le", "-f", "f64le", "pipe:1",
        ], timeout, stdout, stderr)
        if code:
            raise RecordingError("decode_failed", "\n".join(diagnostic_tail))
        if sample_buffer or total_bytes != timeline.samples * frame_bytes:
            raise RecordingError("decode_sample_mismatch", "PCM bytes and frame ledger disagree")
        if not timeline.samples:
            raise RecordingError("empty_audio")
        output.flush()
        os.fsync(output.fileno())
    origin = Fraction(timeline.first_pts, rate)
    return {
        "sample_rate": rate, "sample_count": timeline.samples, "channels": channels,
        "origin_num": origin.numerator, "origin_den": origin.denominator,
        "pcm_sha256": digest.hexdigest(),
        "decode": {
            "transform": "preserve_rate_and_channels_f64le", "digital_silence": not any(channel_peak),
            "channel_peak": channel_peak, "channel_layout": stream_info.get("channel_layout", "unspecified"),
            "stream_index": stream_info["index"], "codec": stream_info.get("codec_name"),
            "container_format": stream_info.get("container_format"),
            "container_start_pts": stream_info.get("start_pts"),
            "container_time_base": {"num": timeline.time_base.numerator, "den": timeline.time_base.denominator},
            "timestamp_precision_samples": timeline.timestamp_precision_samples,
            "max_timestamp_residual_samples": timeline.max_residual_samples,
            "frame_count": timeline.frames,
        },
    }


def _load_checkpoint(path, key, source_hash):
    try:
        if path.stat().st_size > 1024 * 1024:
            raise ValueError("oversized checkpoint")
        result = json.loads(path.read_text(encoding="utf-8"))
        expected_hash = result.pop("manifest_sha256")
        if hashlib.sha256(_json_bytes(result)).hexdigest() != expected_hash:
            raise ValueError("manifest hash mismatch")
        if result["checkpoint_key"] != key or result["source"]["sha256"] != source_hash:
            raise ValueError("checkpoint identity mismatch")
        if result["status"] == "ok":
            meta = result["source"]
            SourceClock(meta["sample_rate"], meta["sample_count"], meta["origin_num"], meta["origin_den"])
            pcm = path.parent / "source.f64le"
            if (result["pcm"]["relative_path"] != "source.f64le"
                    or pcm.stat().st_size != meta["sample_count"] * meta["channels"] * 8
                    or _sha_file(pcm) != meta["pcm_sha256"]):
                raise ValueError("PCM hash or format mismatch")
            result["pcm"]["path"] = str(pcm)
        elif result["status"] != "not_applicable" or result["reason"] != "audio_track_absent":
            raise ValueError("unsupported checkpoint outcome")
        result["cache_hit"] = True
        return result
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise RecordingError("checkpoint_invalid", str(exc)) from exc


def prepare_recording(request: dict, artifact_root: Path) -> dict:
    """Decode once into a bounded run-local artifact or validate an exact reuse.

The caller owns artifact_root and supplies immutable code/config/model/window
fingerprints plus explicit byte/time limits. No global configuration is loaded.
"""
    from steps.common.tool_paths import resolve_ffmpeg

    source = Path(request["source_path"]).resolve(strict=True)
    if not source.is_file():
        raise RecordingError("invalid_source")
    limits = request.get("limits", {})
    byte_budget = _positive_integer(limits.get("max_pcm_bytes"), "max_pcm_bytes")
    timeout = limits.get("timeout_seconds")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise RecordingError("invalid_request", "timeout_seconds must be positive and finite")
    fingerprint = request.get("fingerprint")
    if not isinstance(fingerprint, dict) or not fingerprint.get("source_revision"):
        raise RecordingError("invalid_request", "missing immutable source revision")
    for key in ("worker_sha256", "config_sha256"):
        if not isinstance(fingerprint.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint[key]):
            raise RecordingError("invalid_request", f"missing {key}")
    if not isinstance(fingerprint.get("models"), list) or not isinstance(fingerprint.get("window"), dict):
        raise RecordingError("invalid_request", "model and window fingerprints are required")
    selected = request.get("audio_stream_index")
    if selected is not None and (type(selected) is not int or selected < 0):
        raise RecordingError("invalid_request", "invalid audio stream index")
    binary = resolve_ffmpeg(request.get("config", {}))
    if not binary:
        raise RecordingError("decoder_unavailable")
    binary = Path(binary).resolve(strict=True)
    probe = binary.with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
    if not probe.is_file():
        available = shutil.which("ffprobe")
        if not available:
            raise RecordingError("probe_unavailable")
        probe = Path(available).resolve(strict=True)
    source_hash = _sha_file(source)
    identity = {
        "version": 1, "source_sha256": source_hash, "fingerprint": fingerprint,
        "stream_index": selected, "limits": limits,
        "ffmpeg_sha256": _sha_file(binary), "ffprobe_sha256": _sha_file(probe),
        "decoder_sha256": _sha_file(Path(__file__)), "transform": "preserve_rate_and_channels_f64le",
        "input_policy": "self_contained_media_v1",
    }
    key = hashlib.sha256(_json_bytes(identity)).hexdigest()
    destination = Path(artifact_root).resolve() / ("decode-" + key)
    receipt = destination / "recording.json"
    if receipt.is_file():
        return _load_checkpoint(receipt, key, source_hash)
    started = time.monotonic()
    streams = _probe(source, probe, min(timeout, 20))
    audio_streams = [item for item in streams if item.get("codec_type") == "audio"]
    result = {"schema_version": 1, "checkpoint_key": key, "identity": identity,
              "source": {"sha256": source_hash}, "pcm": None}
    if not audio_streams:
        if selected is not None:
            raise RecordingError("requested_audio_stream_absent")
        if _sha_file(source) != source_hash:
            raise RecordingError("source_changed_during_probe")
        result.update(status="not_applicable", reason="audio_track_absent")
    else:
        choices = audio_streams if selected is None else [item for item in audio_streams if item["index"] == selected]
        if not choices:
            raise RecordingError("requested_audio_stream_absent")
        stream = choices[0]
        try:
            if not 0 < int(stream["sample_rate"]) <= 384000 or not 0 < int(stream["channels"]) <= 32:
                raise ValueError("rate/channels outside decoder limits")
            if Fraction(stream["time_base"]) <= 0:
                raise ValueError("nonpositive time base")
        except (ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
            raise RecordingError("unsupported_audio_format", str(exc)) from exc
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise RecordingError("decode_timeout")
        destination.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix="source.", suffix=".tmp", dir=destination)
        os.close(descriptor)
        try:
            decoded = _decode(source, binary, stream, temporary, byte_budget, remaining)
            if _sha_file(source) != source_hash:
                raise RecordingError("source_changed_during_decode")
            result["decode"] = decoded.pop("decode")
            result["source"].update(decoded)
            result.update(status="ok", pcm={"relative_path": "source.f64le", "encoding": "f64le"})
            os.replace(temporary, destination / "source.f64le")
        finally:
            Path(temporary).unlink(missing_ok=True)
    result["manifest_sha256"] = hashlib.sha256(_json_bytes(result)).hexdigest()
    _atomic_json(result, receipt)
    result.pop("manifest_sha256")
    result["cache_hit"] = False
    if result["pcm"] is not None:
        result["pcm"]["path"] = str(destination / "source.f64le")
    return result


def read_channel(recording: dict, span: SampleSpan, channel: int) -> array:
    """Read a caller-bounded window from one retained channel, without downmix."""
    meta = recording["source"]
    SourceClock(meta["sample_rate"], meta["sample_count"], meta["origin_num"], meta["origin_den"]).require_span(span)
    if type(channel) is not int or not 0 <= channel < meta["channels"]:
        raise RecordingError("invalid_channel")
    frame_bytes = meta["channels"] * 8
    size = (span.end - span.start) * frame_bytes
    with Path(recording["pcm"]["path"]).open("rb") as stream:
        stream.seek(span.start * frame_bytes)
        data = stream.read(size)
    if len(data) != size:
        raise RecordingError("pcm_window_truncated")
    values = array("d")
    values.frombytes(data)
    if sys.byteorder != "little":
        values.byteswap()
    return values[channel::meta["channels"]]
