"""Scene sound must survive speech filtering, and failures must not mean silence."""
from contextlib import nullcontext
import sys
import types
from unittest.mock import Mock

import numpy as np
import pytest


@pytest.fixture(autouse=True)
def cpu_only_fault_injection(monkeypatch):
    monkeypatch.setenv("GOODQ_REQUIRE_GPU", "0")
    monkeypatch.setenv("GOODQ_NO_AUTO_GPU", "1")


@pytest.fixture
def scene_worker(monkeypatch, tmp_path):
    from steps.audio_embed_clap import step
    path = tmp_path / "scene.wav"
    path.write_bytes(b"decoder is injected")
    monkeypatch.setattr(step, "_inspect_audio_input", lambda _: None)
    monkeypatch.setattr(step, "_torchaudio_preflight", lambda: True)
    monkeypatch.setattr(step, "_load", lambda _: (True, None))
    monkeypatch.setattr(step, "require_gpu", lambda: False)
    class Embedding:
        def detach(self): return self
        def cpu(self): return self
        def mean(self, **kw): return self
        def numpy(self): return np.ones((1, 512), dtype="float32")
    infer = Mock(return_value=Embedding())
    monkeypatch.setattr(step, "_CLAP", {"device": "cpu", "model": types.SimpleNamespace(get_audio_features=infer),
                                       "proc": lambda **kw: {"input_features": types.SimpleNamespace(to=lambda _: None)}})
    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace(no_grad=nullcontext, cat=lambda chunks, **kw: chunks[0]))
    decode = Mock(return_value=(np.ones(100, dtype="float32"), 48000))
    monkeypatch.setitem(sys.modules, "librosa", types.SimpleNamespace(load=decode))
    monkeypatch.setitem(sys.modules, "soundfile", types.SimpleNamespace(
        info=lambda p: types.SimpleNamespace(frames=45.012 if str(p) == str(path) else .54, samplerate=1)))
    monkeypatch.setitem(sys.modules, "faiss", types.SimpleNamespace())
    monkeypatch.setitem(sys.modules, "steps.text_embed.step", types.SimpleNamespace(_content_fingerprint=lambda _: "unused"))
    monkeypatch.setitem(sys.modules, "steps.common.memory_commit_events", types.SimpleNamespace(
        MemoryCommitEvent=lambda **kw: kw, emit_memory_commit_event=lambda *a: None, utc_now_iso=lambda: "test"))
    vad = Mock(return_value=("speech-only.wav", [(0, .54)]))
    monkeypatch.setitem(sys.modules, "steps.common.vad_preprocessor", types.SimpleNamespace(preprocess_audio_with_vad=vad))
    return step, {"source_path": str(path)}, decode, infer, vad


def test_original_scene_is_used_even_with_vad_enabled(scene_worker):
    step, item, decode, infer, vad = scene_worker
    meta = step.audio_embed_clap(item, {"vad_enabled": True})["clap_meta"]
    vad.assert_not_called()
    assert meta["status"] == "no_index_path"
    assert meta["input_policy"] == "full_scene"
    assert meta["total_duration_s"] == 45.012
    assert meta["chunks_processed"] == 6
    assert [c.kwargs["offset"] for c in decode.call_args_list] == [0, 8, 16, 24, 32, 40]
    assert all(c.args[0] == item["source_path"] for c in decode.call_args_list)


@pytest.mark.parametrize("fault,reason", [("decode", "chunk_decode_failed"), ("empty", "chunk_decode_empty"),
                                         ("infer", "chunk_inference_failed"), ("nan", "invalid_audio_samples")])
def test_failed_window_is_not_reported_as_inactivity(scene_worker, fault, reason):
    step, item, decode, infer, _ = scene_worker
    if fault == "decode": decode.side_effect = RuntimeError("decode failed")
    if fault == "empty": decode.return_value = (np.array([]), 48000)
    if fault == "infer": infer.side_effect = RuntimeError("inference failed")
    if fault == "nan": decode.return_value = (np.array([np.nan]), 48000)
    meta = step.audio_embed_clap(item, {"vad_enabled": False})["clap_meta"]
    assert meta["status"] == "error"
    assert meta["reason"] == reason
    assert meta["failed_offset_s"] == 0


def test_partial_failure_does_not_commit_incomplete_scene(scene_worker):
    step, item, decode, _, _ = scene_worker
    decode.side_effect = [(np.ones(100), 48000), RuntimeError("later decode failed")]
    meta = step.audio_embed_clap(item, {"vad_enabled": False})["clap_meta"]
    assert meta["status"] == "error"
    assert meta["chunks_processed"] == 1
    assert meta["failed_offset_s"] == 8
    assert not meta.get("faiss_committed")


def test_quiet_windows_are_supported_absence(scene_worker):
    step, item, decode, infer, _ = scene_worker
    decode.return_value = (np.zeros(100), 48000)
    meta = step.audio_embed_clap(item, {"vad_enabled": False})["clap_meta"]
    assert meta["reason"] == "audio_silent"
    assert meta["chunks_skipped_silent"] == 6
    infer.assert_not_called()
    from cli.step_runner import _derive_step_log_outcome
    status, error, extra = _derive_step_log_outcome("audio_embed_clap", {"clap_meta": meta}, verbose=False)
    assert status == "not_applicable" and error is None
    assert extra["reason"] == "silence" and not extra["embedding_emitted"]


def test_subsecond_input_is_short_not_inactive(scene_worker, monkeypatch):
    step, item, decode, _, _ = scene_worker
    monkeypatch.setitem(sys.modules, "soundfile", types.SimpleNamespace(info=lambda _: types.SimpleNamespace(frames=.54, samplerate=1)))
    meta = step.audio_embed_clap(item, {"vad_enabled": False})["clap_meta"]
    assert meta["reason"] == "audio_too_short"
    decode.assert_not_called()


@pytest.mark.parametrize("envelope,meta", [
    ("skipped", {"status": "skipped", "reason": "audio_too_short"}),
    ("skipped", {"status": "unavailable", "reason": "model_not_cached"}),
    ("ok", {"status": "skipped", "reason": "audio_silent"}),
    ("error", {"status": "error", "reason": "chunk_decode_failed", "failed_offset_s": 8}),
])
def test_async_scene_caller_keeps_clap_diagnostics(monkeypatch, tmp_path, envelope, meta):
    import asyncio
    from cli import run_ingestion as runner
    wav = tmp_path / "scene.wav"
    wav.write_bytes(b"injected decoder")
    cfg = tmp_path / "config.json"
    cfg.write_text("{}")
    monkeypatch.setattr(runner, "_extract_audio_chunk", lambda *a, **kw: wav)
    monkeypatch.setattr(runner, "_log_audio_to_ucf_ledger", lambda *a, **kw: None)
    monkeypatch.setattr(runner, "log_step_run", lambda *a, **kw: None)
    monkeypatch.setattr(runner, "_record_run_warning", lambda *a, **kw: None)
    async def run_step(env, name, item, cfg, **kwargs):
        if name == "audio_embed_clap":
            return {"status": envelope, "outputs": {"clap_meta": dict(meta), "untrusted_failed_output": True}, "errors": "decoder failure"}
        return {"status": "ok", "outputs": {}}
    monkeypatch.setattr(runner, "_run_step_async", run_step)
    async def run():
        return await runner._process_audio_async(
            cfg, "ffmpeg", tmp_path / "video.mp4", {"index": 0, "start": 0., "end": 5.},
            tmp_path, tmp_path / "artifacts", "video", "scene", asyncio.Lock(), asyncio.Lock(),
            audio_runtime_contract={"selected": "windows", "reason": "test"})
    result = asyncio.run(run())["data"]
    assert result["clap_meta"]["reason"] == meta["reason"]
    assert result["clap_meta"]["status"] == meta["status"]
    if envelope != "ok": assert "untrusted_failed_output" not in result


@pytest.mark.parametrize("amplitude,reason", [(0, "audio_silent"), (2, "audio_silent"), (1000, None)])
def test_pcm_energy_gate_distinguishes_quiet_from_active(tmp_path, amplitude, reason):
    import wave
    from steps.audio_embed_clap.step import _inspect_audio_input
    wav = tmp_path / "energy.wav"
    samples = (amplitude * np.sin(np.arange(32000) * .2)).astype("<i2")
    with wave.open(str(wav), "wb") as stream:
        stream.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        stream.writeframes(samples.tobytes())
    result = _inspect_audio_input(str(wav))
    assert (result or {}).get("reason") == reason


@pytest.mark.parametrize("sample_bytes,amplitude", [(4, 0.), (4, .1), (8, 0.), (8, .1)])
def test_float_wav_is_not_rejected_by_pcm_only_precheck(tmp_path, sample_bytes, amplitude):
    import struct
    from steps.audio_embed_clap.step import _inspect_audio_input
    path = tmp_path / "float.wav"
    samples = (amplitude * np.sin(np.arange(32000) * .2)).astype(f"<f{sample_bytes}").tobytes()
    fmt = struct.pack("<HHIIHH", 3, 1, 16000, 16000 * sample_bytes, sample_bytes, sample_bytes * 8)
    body = b"WAVEfmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(samples)) + samples
    path.write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)
    # This optional fast path only understands integer PCM. The full decoder
    # must still assess float samples, including silence and non-finite values.
    assert _inspect_audio_input(str(path)) is None
